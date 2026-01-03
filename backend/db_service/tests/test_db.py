# Run in root directory using: pytest backend/db_service/tests/test_db.py -v
import pytest
from backend.db_service.main import (
    app,
    chunk_text,
    create_collections,
    delete_collections,
    get_all_section_texts,
    preprocess_text
)
from fastapi.testclient import TestClient
from unittest.mock import call, MagicMock, Mock, patch

client = TestClient(app)

class TestPreprocessing:
    """Unit tests for text preprocessing functions."""

    @pytest.mark.parametrize("input_text, expected", [
        ("[[AI|Artificial Intelligence]]", "Artificial Intelligence"),
        ("[[Simple]]", "Simple"),
        ("{{Infobox}} text {{cite}}", "text"),
        ("Text[123]", "Text"),
        ("<ref>Foo</ref>bar", "bar"),
        ("[[File:img.png]]", ""),
        ("{{media:foo}}", ""),
        ("Normal text with [[link|text]].", "Normal text with text."),
        ("", ""),
    ])
    def test_preprocess_text_patterns(self, input_text, expected):
        """Test preprocess_text handles all Wikipedia patterns."""
        result = preprocess_text(input_text)

        assert result == expected, f"Failed: '{input_text}' → '{result}'"

    def test_preprocess_text_preserves_punctuation(self):
        """Ensure punctuation survives preprocessing."""
        text = "Hello, world! It's ML."
        result = preprocess_text(text)

        assert "," in result
        assert "!" in result
        assert "." in result


class TestChunking:
    """Unit tests for text chunking."""
    def test_chunk_text_max_length(self):
        """Respect max_len parameter."""
        long_text = "A" * 600
        chunks = chunk_text(long_text, max_len=500)

        assert len(chunks) == 2  # Should split

    def test_chunk_text_empty(self):
        """Handle empty input."""
        assert len(chunk_text("")) == 0
        assert len(chunk_text("   ")) == 0

    def test_chunk_text_single_sentence(self):
        """Single sentence stays one chunk."""
        text = "One sentence only."
        chunks = chunk_text(text)

        assert len(chunks) == 1
        assert "One sentence only." in chunks[0]

class TestSectionExtraction:
    """Tests for Wikipedia section extraction."""

    @patch('wikipediaapi.WikipediaPage.sections')
    def test_get_all_section_texts(self, mock_sections):
        """Test recursive section extraction."""
        # Mock section structure
        mock_section1 = Mock()
        mock_section1.title = "Valid Section"
        mock_section1.text = "Section text 1"
        mock_section1.sections = []
        
        mock_subsection = Mock()
        mock_subsection.title = "Subsection"
        mock_subsection.text = "Subsection text"
        mock_subsection.sections = []
        
        mock_section2 = Mock()
        mock_section2.title = "References"  # Should be rejected
        mock_section2.text = ""
        mock_section2.sections = []
        
        mock_sections.return_value = [mock_section1, mock_section2]
        mock_section1.sections = [mock_subsection]
        
        result = get_all_section_texts(mock_sections.return_value)

        assert len(result) == 2
        assert "Section text 1" in result[0]
        assert "Subsection text" in result[1]
        assert "References" not in "".join(result)

class TestWeaviateCollections:
    """Tests for collection management (mocked Weaviate)."""

    @patch('backend.db_service.main.client')
    def test_create_collections(self, mock_client):
        """Test collection schema creation."""
        mock_collections = Mock()
        mock_client.collections = mock_collections
        mock_exists = Mock(side_effect=[False, False])
        mock_create = Mock()
        mock_collections.exists = mock_exists
        mock_collections.create = mock_create
        
        create_collections(["Summary", "Chunk"])

        assert mock_create.call_count == 2

    @patch('backend.db_service.main.client')
    def test_delete_collections(self, mock_client):
        """Test collection deletion."""
        mock_collections = Mock()
        mock_client.collections = mock_collections
        
        # Mock delete method
        mock_delete = Mock()
        mock_collections.delete = mock_delete
        
        # Test deletion
        collections_to_delete = ["Summary", "Chunk", "TestCollection"]
        delete_collections(collections_to_delete)
        
        # Verify each collection was deleted
        assert mock_delete.call_count == 3
        mock_delete.assert_has_calls([
            call("Summary"),
            call("Chunk"), 
            call("TestCollection")
        ], any_order=False)

class TestVectorSearchAPI:
    """Tests for the /search endpoint of the DB service."""
    @pytest.mark.parametrize("valid_payload", [
        {"query": "machine learning", "top_k": 3, "min_similarity": 0.7},
        {"query": "What is AI?", "top_k": 1, "min_similarity": 0.5},
        {"query": "test query", "top_k": 5},  # Uses defaults
        {"query": "deep learning models"},  # Minimal valid payload
    ])
    @patch("backend.db_service.main.vector_search")
    def test_search_valid_payloads(self, mock_vector_search, valid_payload):
        # Mock vector_search to return realistic results
        mock_results = [
            (0.85, {"text": "This is a relevant machine learning chunk"}),
            (0.72, {"text": "Another relevant result about AI"}),
            (0.65, {"text": "Third matching document"})
        ]
        mock_vector_search.return_value = mock_results[:valid_payload.get("top_k", 3)]
        
        response = client.post("/search", json=valid_payload)
        
        assert response.status_code == 200

        data = response.json()

        assert data["count"] == len(mock_results[:valid_payload.get("top_k", 3)])
        assert len(data["chunks"]) == data["count"]
        assert all("similarity" in chunk and "text" in chunk for chunk in data["chunks"])
        assert all(chunk["similarity"] > 0 for chunk in data["chunks"])

    @pytest.mark.parametrize("invalid_payload", [
        # Missing query (required field)
        {"top_k": 3, "min_similarity": 0.5},
        
        # Invalid query types
        {"query": 123},  # Not string
        {"query": None},  # None
        {"query": []},   # List
        
        # Invalid top_k
        {"query": "test", "top_k": 0},     # Non-positive
        {"query": "test", "top_k": -1},    # Negative
        {"query": "test", "top_k": "abc"}, # Not int
        {"query": "test", "top_k": 0.5},   # Float
        
        # Invalid min_similarity
        {"query": "test", "min_similarity": -0.1},  # Negative
        {"query": "test", "min_similarity": 2.0},   # > 1.0
        {"query": "test", "min_similarity": "abc"}, # Not float
        {"query": "test", "min_similarity": None},  # None
        
        # Malformed payloads
        {},                           # Empty
        "not a dict",                 # Wrong root type
        [{"query": "test"}],          # List instead of dict
    ])
    def test_search_invalid_payloads(self, invalid_payload):
        response = client.post("/search", json=invalid_payload)

        assert response.status_code == 422  # Pydantic validation error

    @patch("backend.db_service.main.vector_search", side_effect=Exception("Vector search failed"))
    def test_search_handles_exceptions(self, mock_vector_search):
        """Test error handling when vector_search fails."""
        payload = {"query": "test", "top_k": 3}

        response = client.post("/search", json=payload)
        
        assert response.status_code == 500
        assert "Vector search failed" in response.json()["detail"]
