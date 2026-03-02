# app/logic/ocr.py
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re

def preprocess_image(image_path):
    """Preprocesses the image for better OCR results."""
    # Read image with OpenCV
    img = cv2.imread(image_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply threshold to get black and white image
    # Using Otsu's thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Resize image to improve OCR accuracy (make it 2x larger)
    width = int(thresh.shape[1] * 2)
    height = int(thresh.shape[0] * 2)
    dim = (width, height)
    resized = cv2.resize(thresh, dim, interpolation=cv2.INTER_CUBIC)
    
    return resized

def extract_text_from_image(image_path):
    """Extracts raw text from the image using Tesseract OCR."""
    try:
        processed_img = preprocess_image(image_path)
        # Convert OpenCV image to PIL image
        pil_img = Image.fromarray(processed_img)
        # Run Tesseract
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(pil_img, config=custom_config)
        return text
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""

def parse_bill_data(raw_text):
    """
    Parses the raw OCR text to extract specific electricity bill fields.
    Returns a dictionary of extracted values.
    """
    data = {
        "Consumer Name": None,
        "Reference No": None,
        "Tariff Category": None,
        "Units Consumed": 0,
        "Issue Date": None,
        "Due Date": None,
        "Billing Month": None,
        "Load (kW)": None,
        "Phase": None,
        "Energy Charges": 0,
        "Fixed Charges": 0,
        "FPA": 0,
        "QTA": 0,
        "GST": 0,
        "Arrears": 0,
        "Late Payment Surcharge": 0,
        "Total Amount": 0
    }
    
    if not raw_text:
        return data

    lines = raw_text.split('\n')
    
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # Reference No extraction
        if "REFERENCE" in line_upper or "REF NO" in line_upper:
            # Look for typical 14 digit reference numbers
            match = re.search(r'\b\d{2}\s?\d{4}\s?\d{7}\s?[UuRr]\b', line_upper)
            if match:
                data["Reference No"] = match.group(0).replace(" ", "")

        # Units Consumed extraction
        if "UNITS" in line_upper and "CONSUMED" in line_upper:
            match = re.search(r'(\d+)', line_upper)
            if match:
                data["Units Consumed"] = int(match.group(1))

        # Total Amount extraction
        if "PAYABLE" in line_upper and "WITHIN DUE DATE" in line_upper:
            match = re.search(r'(\d+)', line_upper)
            if match:
                 data["Total Amount"] = int(match.group(1))
        
        # FPA
        if "FPA" in line_upper and "ADJUSTMENT" in line_upper:
             match = re.search(r'(\d+)', line_upper)
             if match:
                  data["FPA"] = int(match.group(1))
                  
        # Arrears
        if "ARREARS" in line_upper:
             match = re.search(r'(\d+)', line_upper)
             if match:
                  data["Arrears"] = int(match.group(1))

    return data
