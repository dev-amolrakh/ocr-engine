from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    RENDERING = "rendering"
    PREPROCESSING = "preprocessing"
    OCR = "ocr"
    LANG_DETECTION = "lang_detection"
    TRANSLATION = "translation"
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DocumentType(str, Enum):
    INVOICE = "invoice"
    AADHAAR = "aadhaar"
    FRA_FORM = "fra_form"
    LAND_CLAIM = "land_claim"
    CERTIFICATE = "certificate"
    PAN_CARD = "pan_card"
    RATION_CARD = "ration_card"
    BIRTH_CERTIFICATE = "birth_certificate"
    UNKNOWN = "unknown"


class Language(str, Enum):
    HINDI = "hi"
    MARATHI = "mr"
    TAMIL = "ta"
    TELUGU = "te"
    KANNADA = "kn"
    BENGALI = "bn"
    ENGLISH = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class OCRSource(str, Enum):
    PADDLE = "paddle"
    QWEN_VL = "qwen_vl"
    UNKNOWN = "unknown"
