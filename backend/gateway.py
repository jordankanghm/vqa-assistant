from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

GATEWAY_PORT = 8000
INFERENCE_SERVICE_URL = "http://localhost:8001/inference"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = httpx.AsyncClient()

@app.post("/inference")
async def proxy_inference(request: Request):
    try:
        body = await request.json()
        response = await client.post(INFERENCE_SERVICE_URL, json=body)
        response.raise_for_status()
        content = await response.json()
        
        return JSONResponse(status_code=response.status_code, content=content)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

# Run using uvicorn gateway:app --reload --port 8000
