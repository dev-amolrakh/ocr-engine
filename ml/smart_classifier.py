"""
Smart document classifier using keyword patterns.
Does NOT depend on LLM — uses OCR text patterns for high accuracy.
Falls back to LLM only when no pattern matches.
"""
import re
import structlog

log = structlog.get_logger()

# Keyword patterns for each document type (case-insensitive)
DOCUMENT_PATTERNS = {
    "aadhaar": {
        "keywords": [
            r"aadhaar", r"aadhar", r"unique\s*identification\s*authority",
            r"uidai", r"uid", r"\b\d{4}\s*\d{4}\s*\d{4}\b",
            r"vid\s*:\s*\d{4}", r"uidai\.gov\.in", r"आधार",
            r"mera\s*aadhaar", r"माझे\s*आधार",
        ],
        "min_matches": 2,  # Need at least 2 keyword matches
    },
    "pan_card": {
        "keywords": [
            r"permanent\s*account\s*number", r"income\s*tax\s*department",
            r"\b[A-Z]{5}\d{4}[A-Z]\b",  # PAN format: ABCDE1234F
            r"govt\.?\s*of\s*india", r"pan",
        ],
        "min_matches": 2,
    },
    "invoice": {
        "keywords": [
            r"invoice", r"bill\s*(to|of)", r"gstin", r"gst\s*no",
            r"tax\s*invoice", r"hsn\s*code", r"cgst|sgst|igst",
            r"total\s*amount", r"subtotal",
        ],
        "min_matches": 3,
    },
    "fra_form": {
        "keywords": [
            r"forest\s*rights", r"fra", r"gram\s*sabha",
            r"scheduled\s*tribes", r"van\s*adhikar", r"forest\s*land",
            r"claim\s*form", r"वन\s*अधिकार",
        ],
        "min_matches": 2,
    },
    "land_claim": {
        "keywords": [
            r"land\s*record", r"khasra", r"khatauni", r"survey\s*no",
            r"tahsildar", r"revenue\s*department", r"mutation",
            r"7/12\s*extract", r"भूमि\s*अभिलेख",
        ],
        "min_matches": 2,
    },
    "birth_certificate": {
        "keywords": [
            r"birth\s*certificate", r"date\s*of\s*birth",
            r"registration\s*of\s*birth", r"born\s*on",
            r"municipal\s*corporation", r"janm\s*praman",
        ],
        "min_matches": 2,
    },
    "ration_card": {
        "keywords": [
            r"ration\s*card", r"fair\s*price\s*shop",
            r"public\s*distribution", r"bpl|apl|aay",
            r"food\s*supply", r"राशन\s*कार्ड",
        ],
        "min_matches": 2,
    },
    "certificate": {
        "keywords": [
            r"certificate", r"certif", r"hereby\s*certif",
            r"caste\s*certificate", r"income\s*certificate",
            r"domicile", r"प्रमाणपत्र",
        ],
        "min_matches": 2,
    },
}


def classify_document_by_keywords(ocr_text: str) -> str:
    """
    Classify document type using keyword pattern matching on OCR text.
    Returns the doc_type with highest confidence, or 'unknown'.
    """
    if not ocr_text:
        return "unknown"

    text_lower = ocr_text.lower()
    scores = {}

    for doc_type, config in DOCUMENT_PATTERNS.items():
        match_count = 0
        for pattern in config["keywords"]:
            if re.search(pattern, text_lower):
                match_count += 1

        if match_count >= config["min_matches"]:
            scores[doc_type] = match_count

    if not scores:
        return "unknown"

    # Return the type with most keyword matches
    best_type = max(scores, key=scores.get)
    log.info("keyword_classification", doc_type=best_type,
             score=scores[best_type], all_scores=scores)
    return best_type
