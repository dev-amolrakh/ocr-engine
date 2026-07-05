from fastapi import APIRouter, HTTPException

from services.result_service import get_job_results

router = APIRouter()


@router.get("/results/{job_id}")
async def get_results(job_id: str):
    """Get final extracted structured data for a completed job."""
    result = await get_job_results(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return result
