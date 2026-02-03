# Run using: uvicorn rag_service.main:app --reload --port 8002
import os
import weaviate
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from rag_service.schema.collections import create_collections
from sentence_transformers import SentenceTransformer
from typing import Annotated, List
from weaviate.classes.query import Filter

client, model = None, None

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
        
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize client, model, and create collections."""
    global client, model
    
    # Connect to Weaviate
    client = get_weaviate_client()

    if not client.is_ready():
        raise RuntimeError("Weaviate not ready!")
    
    print("Connected to Weaviate")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Create collections
    create_collections(["Summary", "Chunk"], client)
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
    summary_id = top_summary.uuid
    cosine_sim = 1.0 - top_summary.metadata.distance
    print(f"Top Summary (cosine={cosine_sim:.3f}): {top_summary.properties['title']}")

    # Vector search chunks belonging to that summary
    chunk_results = chunks_collection.query.near_vector(
        near_vector=query_vector,
        limit=top_k,
        filters=Filter.by_property("summaryId").equal(summary_id),
        return_properties=["text"],
        return_metadata=["distance"]
    )

    results = []

    for obj in chunk_results.objects:
        similarity = 1.0 - obj.metadata.distance

        if similarity >= min_similarity:
            results.append((similarity, obj.properties["text"]))

    return results

class SearchRequest(BaseModel):
    query: str
    top_k: Annotated[int, Field(gt=0, default=3)]
    min_similarity: Annotated[float, Field(gt=0.0, le=1.0, default=0.5)]

class SearchResponse(BaseModel):
    chunks: List[dict]
    count: int

@app.post("/search")
async def db_vector_search(req: SearchRequest):
    """Perform Weaviate vector search."""
    try:
        results = vector_search(req.query, req.top_k, req.min_similarity)
        chunks = [{"similarity": sim, "text": text} for sim, text in results]
        
        return SearchResponse(chunks=chunks, count=len(chunks))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
