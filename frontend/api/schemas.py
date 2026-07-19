from pydantic import BaseModel

class CompareRequest(BaseModel):
    input: str
    compression_device: str  # "cpu" or "cuda"

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
