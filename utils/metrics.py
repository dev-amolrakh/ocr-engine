from prometheus_client import Counter, Histogram, Gauge

# Upload metrics
jobs_uploaded_total = Counter(
    "ocr_jobs_uploaded_total", "Total jobs uploaded", ["mime_type"])
jobs_completed_total = Counter(
    "ocr_jobs_completed_total", "Total jobs completed", ["doc_type"])
jobs_failed_total = Counter(
    "ocr_jobs_failed_total", "Total jobs failed", ["stage"])

# OCR engine usage
ocr_paddle_pages_total = Counter(
    "ocr_paddle_pages_total", "Pages processed by PaddleOCR")
ocr_qwen_vl_pages_total = Counter(
    "ocr_qwen_vl_pages_total", "Pages processed by Qwen-VL")
ocr_handwritten_pages_total = Counter(
    "ocr_handwritten_pages_total", "Handwritten pages detected")

# Latency
ocr_duration_seconds = Histogram(
    "ocr_duration_seconds", "OCR processing time per page",
    buckets=[0.5, 1, 2, 5, 10, 30, 60])
upload_duration_seconds = Histogram(
    "upload_duration_seconds", "Upload endpoint response time")

# Queue health
queue_depth = Gauge(
    "ocr_queue_depth", "Current stream depth", ["stream"])

# Confidence distribution
paddle_confidence = Histogram(
    "paddle_confidence_score", "PaddleOCR confidence distribution",
    buckets=[0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 0.95, 1.0])
