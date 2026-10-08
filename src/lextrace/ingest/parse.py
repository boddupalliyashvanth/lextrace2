import unicodedata

import fitz  # PyMuPDF
import pytesseract

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

def repair_hyphenation(text: str) -> str:
    return text.replace("-\n", "")

def normalize_text(text: str) -> str:
    return unicodedata.normalize('NFKC', text)

def parse_pdf(file_path: str):
    full_text = ""
    pages = []
    
    try:
        doc = fitz.open(file_path)
        for page_num, page in enumerate(doc):
            text = page.get_text() or ""
            
            if len(text.strip()) < 50 and convert_from_path:
                try:
                    images = convert_from_path(file_path, first_page=page_num+1, last_page=page_num+1)
                    if images:
                        ocr_text = pytesseract.image_to_string(images[0])
                        text = ocr_text
                except Exception as e:
                    print(f"OCR failed for page {page_num}: {e}")
            
            text = normalize_text(repair_hyphenation(text))
            start_idx = len(full_text)
            full_text += text + "\n"
            pages.append({"page_num": page_num, "char_start": start_idx, "char_end": len(full_text)-1})
    except Exception as e:
        print(f"Error parsing PDF {file_path}: {e}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                text = normalize_text(repair_hyphenation(text))
                full_text = text + "\n"
                pages.append({"page_num": 0, "char_start": 0, "char_end": len(full_text)-1})
        except Exception:
            pass
        
    return full_text, pages

