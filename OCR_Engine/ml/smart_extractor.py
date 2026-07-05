"""
Smart regex-based extraction for known Indian document types.
Provides high-accuracy structured extraction WITHOUT needing an LLM.
LLM is only used as fallback for unknown/complex documents.
"""
import re
from typing import Optional
import structlog

log = structlog.get_logger()


def extract_aadhaar(text: str) -> dict:
    """Extract structured fields from Aadhaar card OCR text."""
    result = {
        "name": None,
        "dob": None,
        "gender": None,
        "aadhaar_last4": None,
        "aadhaar_masked": None,
        "vid": None,
        "address": None,
        "father_name": None,
        "issue_date": None,
    }

    lines = text.split("\n")
    text_lower = text.lower()

    # Extract Aadhaar number (12 digits, often spaced as 4-4-4)
    aadhaar_match = re.search(r'\b(\d{4})\s*(\d{4})\s*(\d{4})\b', text)
    if aadhaar_match:
        full_number = aadhaar_match.group(1) + aadhaar_match.group(2) + aadhaar_match.group(3)
        result["aadhaar_last4"] = aadhaar_match.group(3)
        result["aadhaar_masked"] = f"XXXX XXXX {aadhaar_match.group(3)}"

    # Extract VID
    vid_match = re.search(r'VID\s*:\s*(\d{4}\s*\d{4}\s*\d{4}\s*\d{4})', text)
    if vid_match:
        result["vid"] = vid_match.group(1).replace(" ", "")

    # Extract DOB
    dob_match = re.search(r'(?:DOB|D\.O\.B|जन्म\s*तारीख|Date\s*of\s*Birth)\s*[:/]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})', text, re.IGNORECASE)
    if dob_match:
        result["dob"] = dob_match.group(1)
    else:
        # Try alternate format
        dob_match2 = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
        if dob_match2:
            result["dob"] = dob_match2.group(1)

    # Extract Gender
    if re.search(r'\bmale\b', text_lower) and not re.search(r'\bfemale\b', text_lower):
        result["gender"] = "MALE"
    elif re.search(r'\bfemale\b', text_lower):
        result["gender"] = "FEMALE"
    elif re.search(r'पुरुष', text):
        result["gender"] = "MALE"
    elif re.search(r'महिला|स्त्री', text):
        result["gender"] = "FEMALE"

    # Extract Name — usually the line after "Government of India" or before DOB
    name = _extract_name_from_aadhaar(lines, text)
    if name:
        result["name"] = name

    # Extract Issue Date
    issue_match = re.search(r'(?:Issue\s*Date|Download\s*Date)\s*[:/]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})', text, re.IGNORECASE)
    if issue_match:
        result["issue_date"] = issue_match.group(1)

    # Extract Address
    address = _extract_address(text)
    if address:
        result["address"] = address

    # Extract father/husband name
    father_match = re.search(r'(?:S/O|D/O|W/O|son\s*of|daughter\s*of|wife\s*of)\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|\n|$)', text, re.IGNORECASE)
    if father_match:
        result["father_name"] = father_match.group(1).strip()

    # Extract pincode
    pin_match = re.search(r'\b(\d{6})\b', text)
    if pin_match:
        if result.get("address"):
            result["address"] += f", PIN: {pin_match.group(1)}"
        else:
            result["pincode"] = pin_match.group(1)

    return {k: v for k, v in result.items() if v is not None}


def _extract_name_from_aadhaar(lines: list, full_text: str) -> Optional[str]:
    """Extract name from Aadhaar card using multiple heuristics."""
    # Strategy 1: Look for English name (line with only alphabetic words, 2-4 words)
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean:
            continue
        # Name is typically a line with 2-4 capitalized words
        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,3}$', line_clean):
            # Skip known non-name lines
            if any(skip in line_clean.lower() for skip in [
                "government", "india", "authority", "male", "female",
                "download", "issue", "address"
            ]):
                continue
            return line_clean

    # Strategy 2: Look for line right before DOB
    for i, line in enumerate(lines):
        if re.search(r'DOB|जन्म', line, re.IGNORECASE):
            # Check previous lines for a name
            for j in range(max(0, i - 2), i):
                candidate = lines[j].strip()
                if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,3}$', candidate):
                    return candidate

    return None


def _extract_address(text: str) -> Optional[str]:
    """Extract address from document text."""
    # Look for Address: section
    addr_match = re.search(
        r'(?:Address|पत्ता)\s*[:/]?\s*(.+?)(?=\n\n|\d{4}\s*\d{4}|\bVID\b|$)',
        text, re.IGNORECASE | re.DOTALL
    )
    if addr_match:
        address = addr_match.group(1).strip()
        # Clean up the address
        address = re.sub(r'\s+', ' ', address)
        address = address.strip(', ')
        if len(address) > 10:
            return address
    return None


def extract_pan_card(text: str) -> dict:
    """Extract structured fields from PAN card OCR text."""
    result = {}

    # PAN number (ABCDE1234F format)
    pan_match = re.search(r'\b([A-Z]{5}\d{4}[A-Z])\b', text)
    if pan_match:
        result["pan_number"] = pan_match.group(1)

    # Name
    name_match = re.search(r'(?:Name|नाम)\s*[:/]?\s*([A-Z][A-Za-z\s]+)', text)
    if name_match:
        result["name"] = name_match.group(1).strip()

    # Father's name
    father_match = re.search(r"(?:Father|पिता)\s*[:'s]*\s*(?:Name)?\s*[:/]?\s*([A-Z][A-Za-z\s]+)", text, re.IGNORECASE)
    if father_match:
        result["father_name"] = father_match.group(1).strip()

    # DOB
    dob_match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
    if dob_match:
        result["dob"] = dob_match.group(1)

    return result


def extract_invoice(text: str) -> dict:
    """Extract structured fields from invoice OCR text."""
    result = {}

    # Invoice number
    inv_match = re.search(r'(?:Invoice|Bill)\s*(?:No|Number|#)\s*[.:/]?\s*([A-Za-z0-9\-/]+)', text, re.IGNORECASE)
    if inv_match:
        result["invoice_number"] = inv_match.group(1)

    # Date
    date_match = re.search(r'(?:Date|Dated)\s*[:/]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', text, re.IGNORECASE)
    if date_match:
        result["invoice_date"] = date_match.group(1)

    # GSTIN
    gstin_match = re.search(r'(?:GSTIN|GST\s*No)\s*[:/]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d][A-Z])', text, re.IGNORECASE)
    if gstin_match:
        result["gstin"] = gstin_match.group(1)

    # Total amount
    total_match = re.search(r'(?:Total|Grand\s*Total|Amount)\s*[:/]?\s*(?:Rs\.?|₹)?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if total_match:
        result["total_amount"] = total_match.group(1).replace(",", "")

    return result


def extract_fra_form(text: str) -> dict:
    """Extract fields from FRA claim form."""
    result = {}

    # Claimant name
    name_match = re.search(r'(?:Name|नाव|नाम)\s*[:/]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if name_match:
        result["claimant_name"] = name_match.group(1).strip()

    # Village
    village_match = re.search(r'(?:Village|गाव|ग्राम)\s*[:/]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if village_match:
        result["village"] = village_match.group(1).strip()

    # District
    dist_match = re.search(r'(?:District|जिल्हा|जिला)\s*[:/]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if dist_match:
        result["district"] = dist_match.group(1).strip()

    # Survey number
    survey_match = re.search(r'(?:Survey|Gut|गट)\s*(?:No|Number)?\s*[:/]?\s*([A-Za-z0-9/\-]+)', text, re.IGNORECASE)
    if survey_match:
        result["survey_number"] = survey_match.group(1)

    # Area
    area_match = re.search(r'(?:Area|क्षेत्रफळ)\s*[:/]?\s*([\d.]+)\s*(?:acres|hectare|एकर)?', text, re.IGNORECASE)
    if area_match:
        result["area_acres"] = float(area_match.group(1))

    return result


def extract_land_claim(text: str) -> dict:
    """Extract fields from land claim/record documents."""
    result = {}

    name_match = re.search(r'(?:Name|Owner|Claimant)\s*[:/]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if name_match:
        result["claimant_name"] = name_match.group(1).strip()

    survey_match = re.search(r'(?:Survey|Khasra)\s*(?:No)?\s*[:/]?\s*([A-Za-z0-9/\-]+)', text, re.IGNORECASE)
    if survey_match:
        result["survey_number"] = survey_match.group(1)

    village_match = re.search(r'(?:Village|Mouza)\s*[:/]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if village_match:
        result["village"] = village_match.group(1).strip()

    dist_match = re.search(r'(?:District|Tehsil)\s*[:/]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if dist_match:
        result["district"] = dist_match.group(1).strip()

    return result


# Registry of extractors by document type
SMART_EXTRACTORS = {
    "aadhaar": extract_aadhaar,
    "pan_card": extract_pan_card,
    "invoice": extract_invoice,
    "fra_form": extract_fra_form,
    "land_claim": extract_land_claim,
}


def smart_extract(text: str, doc_type: str) -> dict | None:
    """
    Run rule-based extraction for known document types.
    Returns extracted dict or None if no extractor exists for this type.
    """
    extractor = SMART_EXTRACTORS.get(doc_type)
    if extractor is None:
        return None

    try:
        result = extractor(text)
        log.info("smart_extraction_complete", doc_type=doc_type,
                 fields_extracted=len(result))
        return result
    except Exception as e:
        log.error("smart_extraction_error", doc_type=doc_type, error=str(e))
        return None
