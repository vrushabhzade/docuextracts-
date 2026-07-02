import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Verhoeff tables
# Multiplication table d
D_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

# Permutation table p
P_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]

# Inverse table
INV_TABLE = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

def validate_verhoeff(number: str) -> bool:
    """
    Validates a number string using the Verhoeff checksum algorithm.
    Used for 12-digit Aadhaar numbers.
    """
    # Clean the input to get digits only
    digits_only = "".join(char for char in number if char.isdigit())
    
    if len(digits_only) != 12:
        return False
        
    c = 0
    # Reverse digits and convert to ints
    reversed_digits = [int(x) for x in reversed(digits_only)]
    
    for i, digit in enumerate(reversed_digits):
        permuted = P_TABLE[i % 8][digit]
        c = D_TABLE[c][permuted]
        
    return c == 0

def validate_pincode(pincode_val: Any) -> bool:
    """
    Validates an Indian Pincode.
    Must be 6 digits, cannot start with 0.
    """
    if pincode_val is None:
        return False
        
    pin_str = "".join(char for char in str(pincode_val) if char.isdigit())
    if len(pin_str) != 6:
        return False
        
    # Match pattern: starts with 1-9, followed by 5 digits
    return bool(re.match(r"^[1-9]\d{5}$", pin_str))

def validate_phone_number(phone_val: Any) -> bool:
    """
    Validates an Indian Phone/Mobile Number.
    Must be 10 digits, starts with 6, 7, 8, or 9.
    Handles optional country code '+91' or '0' prefix.
    """
    if phone_val is None:
        return False
        
    phone_str = str(phone_val).strip()
    
    # Strip common prefixes
    if phone_str.startswith("+91"):
        phone_str = phone_str[3:]
    elif phone_str.startswith("0"):
        phone_str = phone_str[1:]
        
    # Clean non-digits
    digits_only = "".join(char for char in phone_str if char.isdigit())
    
    if len(digits_only) != 10:
        return False
        
    # Indian mobile prefix rule: starts with 6, 7, 8, 9
    return bool(re.match(r"^[6-9]\d{9}$", digits_only))

def validate_date(date_val: Any) -> Tuple[bool, bool]:
    """
    Validates dates (e.g. dob, exam_date).
    Attempts to parse multiple common date formats.
    
    Returns:
        A tuple of (is_valid_format, is_future_date)
    """
    if not date_val:
        return False, False
        
    date_str = str(date_val).strip()
    
    # Common Indian date formats
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d %B %Y", "%d %b %Y"
    ]
    
    parsed_date = None
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
            
    if not parsed_date:
        return False, False
        
    # Check if the parsed date is in the future
    is_future = parsed_date > datetime.now()
    return True, is_future

def validate_and_enrich_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates each extracted field based on rules and computes overall confidence:
    - Aadhaar: Verhoeff checksum
    - Pincode: 6 digits starting with 1-9
    - Phone: 10 digits starting with 6-9
    - Date: format & future check
    
    Updates confidence level to 'high', 'medium', or 'low'.
    """
    enriched_fields = []
    
    for field in fields:
        name = field["name"].lower()
        val = field["value"]
        ocr_conf = field.get("ocr_confidence", 75.0)
        bbox = field.get("bbox")
        
        # Default flags
        validation_applies = False
        validation_passed = True
        
        # 1. Aadhaar Number Validation
        if "aadhaar" in name or "adhaar" in name or "aadhar" in name:
            validation_applies = True
            if val:
                validation_passed = validate_verhoeff(str(val))
            else:
                validation_passed = False
                
        # 2. Pincode Validation
        elif "pincode" in name or "pin_code" in name or "pin" in name:
            # Avoid matching subjects or common words containing 'pin' by doing strict check or regex
            if name == "pincode" or name == "pin_code" or name.endswith("_pincode") or name.endswith("_pin"):
                validation_applies = True
                validation_passed = validate_pincode(val)
                
        # 3. Phone Number Validation
        elif "phone" in name or "mobile" in name or "contact" in name:
            validation_applies = True
            validation_passed = validate_phone_number(val)
            
        # 4. Date Validation
        elif "date" in name or "dob" in name:
            validation_applies = True
            if val:
                is_valid_fmt, is_future = validate_date(val)
                # Fail validation if format is invalid or it's a future date (which is suspicious)
                validation_passed = is_valid_fmt and not is_future
            else:
                validation_passed = False

        # Calculate final confidence
        if validation_applies:
            if not validation_passed:
                # Format check failed -> Automatic low confidence
                confidence = "low"
            else:
                # Passed validation. Check OCR word confidence.
                if ocr_conf >= 80.0:
                    confidence = "high"
                elif ocr_conf >= 50.0:
                    confidence = "medium"
                else:
                    confidence = "low"
        else:
            # Generic text fields (no format validation applies)
            # Evaluate strictly based on OCR word confidence
            if ocr_conf >= 80.0:
                confidence = "high"
            elif ocr_conf >= 55.0:
                confidence = "medium"
            else:
                confidence = "low"
                
        enriched_fields.append({
            "name": field["name"],
            "value": val,
            "confidence": confidence,
            "bbox": bbox
        })
        
    return enriched_fields
