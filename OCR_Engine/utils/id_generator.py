from uuid import uuid4


def generate_job_id() -> str:
    """Generate a unique job ID in format JOB-XXXXXXXXXXXX."""
    return f"JOB-{uuid4().hex[:12].upper()}"


def generate_page_id(job_id: str, page: int) -> str:
    """Generate a unique page ID."""
    return f"{job_id}-P{page:04d}"
