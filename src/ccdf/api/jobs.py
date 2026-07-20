import uuid
import asyncio
from typing import Dict, Any, List

class JobManager:
    def __init__(self):
        self.active_job_id = None
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def create_job(self) -> str:
        async with self.lock:
            if self.active_job_id is not None:
                raise ValueError("A comparison job is already active")
            
            job_id = str(uuid.uuid4())
            self.active_job_id = job_id
            self.jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "events": [],
                "results": {},
                "summary": None,
            }
            return job_id

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        async with self.lock:
            return self.jobs.get(job_id)

    async def complete_job(self, job_id: str):
        async with self.lock:
            if self.active_job_id == job_id:
                self.active_job_id = None

    async def is_busy(self) -> bool:
        async with self.lock:
            return self.active_job_id is not None

job_manager = JobManager()
