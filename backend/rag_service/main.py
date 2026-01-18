# Run in current directory using: uvicorn main:app --reload --port 8002
import heapq
import os
import re
import weaviate
import wikipediaapi
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Annotated, List
from weaviate.classes.config import Configure, DataType, Property, VectorDistances

client, model, wiki_wiki = None, None, None

def get_weaviate_client():
    """Get Weaviate client based on env."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        return weaviate.connect_to_local(host="localhost", port=8080, grpc_port=50051)
    
    else:
        return weaviate.connect_to_local(host="127.0.0.1", port=8080, grpc_port=50051)
        
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize client, model, and create collections."""
    global client, model, wiki_wiki
    
    # Connect to Weaviate
    client = get_weaviate_client()

    if not client.is_ready():
        raise RuntimeError("Weaviate not ready!")
    
    print("Connected to Weaviate")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    wiki_wiki = wikipediaapi.Wikipedia(user_agent="jordankanghm@gmail.com", language='en')
    
    # Create collections
    create_collections(["Summary", "Chunk"])
    print("Collections ready")

    yield

    if client:
        client.close()
        print("Weaviate client closed")
        
app = FastAPI(title="DB Service",
              version="1.0.0",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_collections(collections):
    for cls_name in collections:
        if not client.collections.exists(cls_name):
            print(f"Creating {cls_name}")
            
            if cls_name == "Summary":
                properties = [
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="chunkIds", data_type=DataType.TEXT_ARRAY),
                ]

            else:  # Chunk
                properties = [
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="summaryId", data_type=DataType.TEXT),
                ]
            
            client.collections.create(
                name=cls_name,
                properties=properties,
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE
                )
            )
            print(f"Created {cls_name} with vector index")

        else:
            print(f"Collection {cls_name} exists")

def delete_collections(collections):
    for collection_name in collections:
        client.collections.delete(
            collection_name
        )

        print(f"Deleted collection: {collection_name}")

    print(f"Collections deleted: {collections}")

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
    summaries_collection = client.collections.use("Summary")
    chunks_collection = client.collections.use("Chunk")
    
    for category in categories[:1]:
        print(f"Scraping category: {category}")
        cat = wiki_wiki.page(f"Category:{category}")
        pages = cat.categorymembers

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

# Retrieves the most relevant summary based on the query, then retrieves the top_k chunks from that summary most similar to the query.
def vector_search(query, top_k=3, min_similarity=0.5):
    summaries_collection = client.collections.use("Summary")
    chunks_collection = client.collections.use("Chunk")

    # Encode the query to get its vector representation
    query_vector = model.encode([query])[0].tolist()

    # Search for the most relevant summaries
    summary_results = summaries_collection.query.near_vector(
        near_vector=query_vector,
        limit=1,
        return_metadata=["distance"],
        return_properties=["title", "text", "chunkIds"]
    )
    
    if not summary_results.objects:
        print(f"No summaries found")
        return []
    
    top_summary = summary_results.objects[0]
    cosine_sim = 1.0 - top_summary.metadata.distance
    print(f"Top Summary (cosine={cosine_sim:.3f}): {top_summary.properties['title']}")

    chunk_ids = top_summary.properties.get("chunkIds", [])

    if not chunk_ids:
        print("No chunks associated with the top summary.")
        return []

    # Retrieve chunk objects based on chunk IDs
    chunks = []
    for chunk_id in chunk_ids:
        chunk_obj = chunks_collection.query.fetch_object_by_id(uuid=chunk_id)

        if chunk_obj and chunk_obj.properties:
            chunks.append(chunk_obj.properties)

        else:
            print(f"Chunk {chunk_id} not found.")
    
    if not chunks:
        return []
    
    # Find top_k chunks most similar to the query
    top_k_heap = []
    high_similarity_chunks = 0
    
    for chunk in chunks:
        chunk_vec = model.encode([chunk['text']])[0].tolist()
        similarity = cosine_similarity([query_vector], [chunk_vec])[0][0]
        
        # Filter chunks below threshold
        if similarity >= min_similarity:
            heapq.heappush(top_k_heap, (similarity, chunk))
            high_similarity_chunks += 1
            
            # Keep heap size <= top_k
            if len(top_k_heap) > top_k:
                heapq.heappop(top_k_heap)
    
    print(f"Found {high_similarity_chunks} chunks above {min_similarity} similarity")
    
    if not top_k_heap:
        print(f"No chunks above {min_similarity} similarity threshold")
        return []
    
    # Extract top_k chunks
    top_chunks = [(similarity_score, chunk) for similarity_score, chunk in sorted(top_k_heap, reverse=True)]
    return top_chunks

class IngestRequest(BaseModel):
    categories: List[str]
    limit_pages: int = 20

class SearchRequest(BaseModel):
    query: str
    top_k: Annotated[int, Field(gt=0, default=3)]
    min_similarity: Annotated[float, Field(gt=0.0, le=1.0, default=0.5)]

class SearchResponse(BaseModel):
    chunks: List[dict]
    count: int

@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection."""
    delete_collections([collection_name])

    return {"status": f"deleted {collection_name}"}

@app.post("/ingest-wikipedia", status_code=202)
async def ingest_wikipedia(background_tasks: BackgroundTasks, req: IngestRequest):
    """Ingest Wikipedia articles asynchronously."""
    background_tasks.add_task(ingest_wikipedia_articles, req.categories)

    return {"status": "ingestion_started", "categories": req.categories}

@app.post("/search")
async def db_vector_search(req: SearchRequest):
    """Perform Weaviate vector search."""
    try:
        results = vector_search(req.query, req.top_k, req.min_similarity)
        chunks = [{"similarity": sim, "text": chunk["text"]} for sim, chunk in results]

        return SearchResponse(chunks=chunks, count=len(chunks))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
