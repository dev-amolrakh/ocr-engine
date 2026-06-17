import structlog
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field

from workers.base_worker import BaseWorker
from mq.streams import STREAM_EXTRACTION_QUEUE, STREAM_VALIDATION_QUEUE
from mq.producer import push_to_stream
from db.mongo import get_db

log = structlog.get_logger()


# ── Validation Schemas ──────────────────────────────────────────────────────

class FRAFormData(BaseModel):
    claimant_name: str
    village: str
    district: str
    survey_number: Optional[str] = None
    area_acres: Optional[float] = Field(None, gt=0, lt=1000)
    claim_date: Optional[date] = None
    claim_number: Optional[str] = None


class LandClaimData(BaseModel):
    claimant_name: str
    village: str
    district: str
    survey_number: Optional[str] = None
    area_acres: Optional[float] = Field(None, gt=0)


class InvoiceData(BaseModel):
    invoice_number: str
    vendor_name: str
    total_amount: float = Field(gt=0)
    invoice_date: Optional[date] = None


class AadhaarData(BaseModel):
    name: str
    aadhaar_last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    dob: Optional[str] = None
    gender: Optional[str] = None


DOC_TYPE_VALIDATORS = {
    "fra_form": FRAFormData,
    "land_claim": LandClaimData,
    "invoice": InvoiceData,
    "aadhaar": AadhaarData,
}


# ── Worker ──────────────────────────────────────────────────────────────────

class ValidationWorker(BaseWorker):
    consumer_stream = STREAM_EXTRACTION_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg["job_id"]
        page = int(msg["page"])
        doc_type = msg.get("doc_type", "unknown")

        db = get_db()

        # Get the extracted data for this job
        extraction = await db.extracted_data.find_one({"job_id": job_id})
        if not extraction:
            log.warning("no_extraction_found", job_id=job_id)
            return

        # Merge page extractions into a single dict for validation
        page_extractions = extraction.get("page_extractions", [])
        merged_data = {}
        for pe in page_extractions:
            if isinstance(pe.get("data"), dict):
                merged_data.update(pe["data"])

        # Validate against schema if one exists for this doc_type
        validation_errors = []
        validated = False

        validator_class = DOC_TYPE_VALIDATORS.get(doc_type)
        if validator_class:
            try:
                validator_class.model_validate(merged_data)
                validated = True
            except Exception as e:
                validation_errors = [str(err) for err in e.errors()] if hasattr(e, "errors") else [str(e)]
                log.warning("validation_failed", job_id=job_id,
                            doc_type=doc_type, errors=validation_errors)
        else:
            # No validator for this doc_type — pass through
            validated = True

        # Update extraction document
        await db.extracted_data.update_one(
            {"job_id": job_id},
            {"$set": {
                "extracted_data": merged_data,
                "validated": validated,
                "validation_errors": validation_errors,
                "confidence": 1.0 if validated else 0.5,
            }}
        )

        # Update page + job status
        await db.ocr_pages.update_one(
            {"job_id": job_id, "page": page},
            {"$set": {"status": "completed", "processed_at": datetime.utcnow()}},
            upsert=True
        )

        # Check if all pages are complete
        job = await db.jobs.find_one({"job_id": job_id})
        total_pages = job.get("total_pages", 0) if job else 0
        completed_pages = await db.ocr_pages.count_documents(
            {"job_id": job_id, "status": "completed"}
        )

        if completed_pages >= total_pages and total_pages > 0:
            await db.jobs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "processed_pages": completed_pages,
                }}
            )
            log.info("job_completed", job_id=job_id, pages=completed_pages)
        else:
            await db.jobs.update_one(
                {"job_id": job_id},
                {"$inc": {"processed_pages": 1}, "$set": {"status": "validation"}}
            )

        log.info("validation_complete", job_id=job_id, page=page,
                 validated=validated, errors_count=len(validation_errors))
