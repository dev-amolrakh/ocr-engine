from fastapi import APIRouter, HTTPException, Query

from services.result_service import get_page_result, get_all_pages

router = APIRouter()


@router.get("/pages/{job_id}")
async def list_pages(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Get all OCR pages for a job with pagination."""
    result = await get_all_pages(job_id, page=page, limit=limit)
    if result["total"] == 0:
        raise HTTPException(status_code=404, detail=f"No pages found for job: {job_id}")
    return result


@router.get("/pages/{job_id}/{page_num}")
async def get_page(job_id: str, page_num: int):
    """Get OCR result for a single page."""
    result = await get_page_result(job_id, page_num)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_num} not found for job: {job_id}"
        )
    return result
