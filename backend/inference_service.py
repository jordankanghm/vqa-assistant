from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class InferenceRequest(BaseModel):
    text: Optional[str] = None
    image: Optional[str] = None

class InferenceResponse(BaseModel):
    answer: str
    image: Optional[str] = None

@app.post("/inference", response_model=InferenceResponse)
async def inference(req: InferenceRequest):
    # Replace with LangChain inference pipeline
    answer = f"LangChain result for: {req.text}"
    
    return InferenceResponse(answer=answer, image=req.image)

# Run using uvicorn inference_service:app --reload --port 8001
