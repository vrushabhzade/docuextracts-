import cv2
import numpy as np
import base64
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def get_skew_angle(gray_img: np.ndarray) -> float:
    """
    Estimates the skew angle of the document image.
    Uses OTSU thresholding, dilation to connect text elements, 
    and contour minAreaRect analysis.
    """
    try:
        # Threshold the image (OTSU binarization on inverted image)
        _, thresh = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Dilate horizontally to connect letters/words into text lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        angles = []
        for c in contours:
            # Filter out very small noise contours
            if cv2.contourArea(c) < 100:
                continue
                
            rect = cv2.minAreaRect(c)
            angle = rect[-1]
            
            # minAreaRect angle rules vary by OpenCV version.
            # We normalize angle to the range [-45, 45] degrees.
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = 90 - angle
                
            # Exclude extreme angles (they are probably vertical margins or noise)
            if abs(angle) > 0.1 and abs(angle) < 40.0:
                angles.append(angle)
                
        if not angles:
            return 0.0
            
        # Use median angle to avoid outliers
        median_angle = float(np.median(angles))
        logger.info(f"Estimated skew angle: {median_angle:.2f} degrees")
        return median_angle
    except Exception as e:
        logger.warning(f"Error estimating skew angle: {e}. Defaulting to 0.0.")
        return 0.0

def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """
    Rotates the image by a given angle (in degrees).
    Uses BorderReplicate to avoid black margins.
    """
    if abs(angle) < 0.2:  # Don't rotate for trivial angles
        return image
        
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    
    # Get rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Perform rotation
    rotated = cv2.warpAffine(
        image, 
        M, 
        (w, h), 
        flags=cv2.INTER_CUBIC, 
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated

def preprocess_image(image_bytes: bytes) -> Tuple[bytes, str]:
    """
    Performs image preprocessing pipeline:
    1. Read image bytes into numpy array
    2. Convert to Grayscale
    3. Estimate skew and rotate (Deskew)
    4. Denoise (fastNlMeansDenoising)
    5. Adaptive thresholding for contrast normalization
    
    Returns:
        A tuple of (processed_png_bytes, base64_preview_string)
    """
    try:
        # 1. Decode image bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image format or corrupted bytes.")
            
        # Optimization: Downscale high-resolution images to a maximum width/height of 1600px.
        # This reduces computation times for OCR, OpenCV deskewing, and denoising by up to 10x
        # while keeping resolution perfectly sufficient for clear text extraction.
        h, w = img.shape[:2]
        max_dim = 1600
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            logger.info(f"High-resolution image downscaled from {w}x{h} to {int(w * scale)}x{int(h * scale)}")

        # 2. Grayscale conversion
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. Deskewing
        angle = get_skew_angle(gray)
        deskewed = rotate_image(gray, angle)
        
        # 4. Denoising
        # Optimized: Replace slow fastNlMeansDenoising (takes seconds) with Gaussian blur (takes milliseconds)
        # to dramatically reduce latency and server load.
        denoised = cv2.GaussianBlur(deskewed, (3, 3), 0)
        
        # 5. Adaptive Thresholding
        # Handles uneven lighting and shadows, common in mobile photos
        processed = cv2.adaptiveThreshold(
            denoised, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            15, 
            4
        )
        
        # 6. Encode processed image to PNG bytes
        success, encoded_img = cv2.imencode(".png", processed)
        if not success:
            raise RuntimeError("Failed to encode processed image to PNG.")
            
        processed_bytes = encoded_img.tobytes()
        
        # 7. Generate base64 string preview for frontend
        base64_preview = base64.b64encode(processed_bytes).decode("utf-8")
        
        return processed_bytes, f"data:image/png;base64,{base64_preview}"
        
    except Exception as e:
        logger.error(f"Image preprocessing pipeline failed: {e}")
        raise RuntimeError(f"Image preprocessing failed: {e}")
