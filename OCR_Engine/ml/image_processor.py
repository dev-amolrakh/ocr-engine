import cv2
import numpy as np
from pathlib import Path
from config import settings
import structlog

log = structlog.get_logger()


def preprocess_for_ocr(image_path: str, output_path: str,
                       is_handwritten_hint: bool = False) -> str:
    """
    Full preprocessing pipeline optimized for handwritten + printed text.
    Returns path to the preprocessed image.

    Pipeline order (each step depends on the previous):
      1. Load + normalize resolution
      2. Grayscale conversion (weighted luminosity)
      3. Noise removal (Non-Local Means)
      4. Shadow / uneven illumination removal
      5. Contrast enhancement (CLAHE)
      6. Adaptive binarization
      7. Deskew
      8. Morphological cleanup
      9. Border removal
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Step 1: Normalize resolution — upscale small images to 300 DPI equivalent
    h, w = img.shape[:2]
    target_width = 2480  # A4 at 300 DPI
    if w < target_width:
        scale = target_width / w
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        log.debug("image_upscaled", scale=round(scale, 2))

    # Step 2: Grayscale using weighted luminosity (preserves ink contrast for colored pens/faded ink)
    if len(img.shape) == 3:
        gray = np.dot(img[..., ::-1], [0.07, 0.72, 0.21]).astype(np.uint8)
    else:
        gray = img

    # Step 3: Non-Local Means denoising — preserves handwriting stroke edges
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Step 4: Shadow/background illumination normalization
    blur_bg = cv2.GaussianBlur(denoised, (91, 91), 0)
    norm = cv2.divide(denoised, blur_bg, scale=255)

    # Step 5: CLAHE — handles local contrast variations in faded/carbon-copy docs
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(norm)

    # Step 6: Adaptive binarization (MEAN_C for handwriting, GAUSSIAN_C for print)
    method = cv2.ADAPTIVE_THRESH_MEAN_C if is_handwritten_hint else cv2.ADAPTIVE_THRESH_GAUSSIAN_C
    binary = cv2.adaptiveThreshold(
        enhanced, 255, method,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10
    )

    # Step 7: Deskew
    binary = _deskew(binary)

    # Step 8: Morphological cleanup
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
    if not is_handwritten_hint:
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)

    # Step 9: Border removal (black borders confuse OCR line detection)
    border = 10
    cleaned[0:border, :] = 255
    cleaned[-border:, :] = 255
    cleaned[:, 0:border] = 255
    cleaned[:, -border:] = 255

    cv2.imwrite(output_path, cleaned)

    if settings.PREPROCESS_SAVE_INTERMEDIATE:
        _save_debug_steps(image_path, gray, denoised, norm, enhanced, binary, cleaned)

    return output_path


def _deskew(image: np.ndarray) -> np.ndarray:
    """Detect and correct skew using minAreaRect on dark pixels."""
    coords = np.column_stack(np.where(image < 128))
    if len(coords) < 10:
        return image

    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = -(90 - angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return image

    (h, w) = image.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255
    )
    return rotated


def detect_handwriting(image_path: str) -> bool:
    """
    Heuristic: estimate if image contains handwriting based on
    Laplacian variance (handwriting has lower, more variable contrast).
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False

    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    return bool(laplacian_var < 300)


def _save_debug_steps(image_path: str, *steps) -> None:
    """Save intermediate steps for debugging when PREPROCESS_SAVE_INTERMEDIATE=True."""
    base = Path(image_path)
    debug_dir = base.parent / "debug"
    debug_dir.mkdir(exist_ok=True, parents=True)
    step_names = ["gray", "denoised", "norm", "enhanced", "binary", "cleaned"]
    for name, img in zip(step_names, steps):
        cv2.imwrite(str(debug_dir / f"{base.stem}_{name}.png"), img)
