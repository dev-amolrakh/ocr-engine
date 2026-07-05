from fastapi import APIRouter, HTTPException

from services.job_service import get_job_status, get_bulk_status, retry_job, delete_job
from schemas.request import BulkStatusRequest
from schemas.response import JobStatusResponse

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
    """Get job status and OCR engine statistics."""
    result = await get_job_status(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return result


@router.post("/jobs/status")
async def bulk_status(body: BulkStatusRequest):
    """Get status for multiple jobs (max 100)."""
    results = await get_bulk_status(body.job_ids)
    return {"jobs": results}


@router.post("/jobs/{job_id}/retry")
async def retry(job_id: str):
    """Retry a failed job. Resets and re-queues."""
    result = await retry_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return result


@router.delete("/jobs/{job_id}")
async def delete(job_id: str):
    """Delete a job and archive its file."""
    deleted = await delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"message": f"Job {job_id} deleted", "archived": True}
