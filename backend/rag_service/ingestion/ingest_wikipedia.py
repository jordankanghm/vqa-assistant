import os
import re
import weaviate
import wikipediaapi
from sentence_transformers import SentenceTransformer
from rag_service.schema.collections import create_collections

def get_weaviate_client():
    """Get Weaviate client based on env."""
    host = os.getenv("WEAVIATE_HOST", "localhost")
    port = int(os.getenv("WEAVIATE_PORT", "8080"))
    grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

    return weaviate.connect_to_local(
        host=host,
        port=port,
        grpc_port=grpc_port,
    )

def chunk_text(text, max_len=500):
    if not text or not text.strip():
        return []
    
    sentences = text.split('. ')
    chunks = []
    chunk = ""

    for sentence in sentences:
        if len(chunk) + len(sentence) + 1 <= max_len:
            chunk += sentence + '. '

        else:
            chunks.append(chunk.strip())
            chunk = sentence + '. '

    if chunk:
        chunks.append(chunk.strip())

    return chunks

def get_all_section_texts(sections):
    rejected = ["see also", "explanatory notes", "references", "other sources", "further reading", "external links"]
    texts = []

    for section in sections:
        section_name = section.title.lower()
        
        # Add current section text if not empty
        if section.text.strip() and section_name not in rejected:
            texts.append(section.text)

        # Recursively add texts from subsections
        texts.extend(get_all_section_texts(section.sections))

    return texts

def preprocess_text(text):
    if not text or not text.strip():
        return ""
    
    # Filter images
    text = re.sub(r'\[\[(?:File|Image|Fichier):[^\]]+\]\]', '', text)
    
    # Filter templates
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    
    # Filter links
    text = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', text)
    
    # Filter citations
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'\[\d+\]', '', text)
    
    # Headers - Only lines starting with ==
    text = re.sub(r'^\s*=+\s*([^=]+?)\s*=+\s*$', r'\1', text, flags=re.MULTILINE)
    
    # Whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def ingest_wikipedia_articles(categories):
    # Connect to Weaviate
    client = get_weaviate_client()

    if not client.is_ready():
        raise RuntimeError("Weaviate not ready!")

    print("Connected to Weaviate")

    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    wiki_wiki = wikipediaapi.Wikipedia(user_agent="jordankanghm@gmail.com", language='en')

    # Create collections
    create_collections(["Summary", "Chunk"], client)

    summaries_collection = client.collections.use("Summary")
    chunks_collection = client.collections.use("Chunk")
    
    for category in categories[:1]:
        print(f"Scraping category: {category}")
        cat = wiki_wiki.page(f"Category:{category}")
        pages = cat.categorymembers

        print(f"Found {len(pages)} category members")
        print(list(pages.keys())[:10])

        for page_title in list(pages.keys())[:20]:
            page = wiki_wiki.page(page_title)

            if not page.exists():
                print(f"Page '{page_title}' not found.")
                continue

            # Store summary embedding
            summary_text = page.summary if page.summary else page.text[:1000]
            summary_embedding = model.encode([summary_text])[0].tolist()

            summary_obj = {
                "title": page_title,
                "text": summary_text,
                "chunkIds": []
            }

            summary_uuid = summaries_collection.data.insert(
                properties=summary_obj,
                vector=summary_embedding
            )

            all_section_texts = get_all_section_texts(page.sections)

            chunk_uuids = []
            for section_text in all_section_texts:
                chunks = chunk_text(section_text)
                chunk_embeddings = model.encode(chunks)

                for chunk_text_piece, chunk_vec in zip(chunks, chunk_embeddings):
                    chunk_text_piece = preprocess_text(chunk_text_piece)

                    if not chunk_text_piece.strip():
                        continue  # skip empty chunks
                    
                    chunk_obj = {
                        "text": chunk_text_piece,
                        "summaryId": summary_uuid
                    }

                    chunk_uuid = chunks_collection.data.insert(
                        properties=chunk_obj,
                        vector=chunk_vec.tolist()
                    )

                    chunk_uuids.append(chunk_uuid)
                    
            summaries_collection.data.update(
                uuid=summary_uuid,
                properties={"chunkIds": chunk_uuids}
            )

    # Close client
    client.close()

if __name__ == "__main__":
    ingest_wikipedia_articles(["Machine learning"])