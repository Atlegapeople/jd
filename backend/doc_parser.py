import os
import io
import tempfile
import logging
import pytesseract
from pdf2image import convert_from_bytes
from docx import Document
import win32com.client
import pythoncom
import fitz  # PyMuPDF
from PIL import Image
from difflib import SequenceMatcher
from datetime import datetime
from anthropic import Anthropic

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def extract_text_from_pdf(file_bytes):
    try:
        logger.info("Extracting text from PDF")
        is_image_based = False
        text = ""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text()
            if len(text.strip()) < 100:
                logger.info("Limited text found in PDF, trying OCR...")
                is_image_based = True
                images = convert_from_bytes(file_bytes)
                text = ""
                for i, img in enumerate(images):
                    text += pytesseract.image_to_string(img)
                    logger.info(f"OCR processed page {i+1}/{len(images)}")
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {str(e)}, falling back to OCR")
            is_image_based = True
            images = convert_from_bytes(file_bytes)
            text = ""
            for i, img in enumerate(images):
                text += pytesseract.image_to_string(img)
                logger.info(f"OCR processed page {i+1}/{len(images)}")

        logger.info(f"PDF extraction completed: {'image-based' if is_image_based else 'text-based'}")
        return text, is_image_based

    except Exception as e:
        logger.error(f"PDF text extraction failed: {str(e)}")
        raise

def extract_text_from_docx(file_bytes):
    try:
        logger.info("Extracting text from DOCX")
        doc = Document(io.BytesIO(file_bytes))
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + " "
                text += "\n"
        return text, False
    except Exception as e:
        logger.error(f"DOCX text extraction failed: {str(e)}")
        return "", False

def extract_image_text(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        logger.warning(f"Image OCR error: {str(e)}")
        return ""

def convert_docx_to_pdf(docx_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as docx_temp:
            docx_path = docx_temp.name
            docx_temp.write(docx_bytes)

        pdf_path = docx_path.replace('.docx', '.pdf')
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(docx_path)
            doc.SaveAs(pdf_path, FileFormat=17)
            doc.Close()
            with open(pdf_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()
            return pdf_bytes
        finally:
            word.Quit()
            try:
                os.unlink(docx_path)
                os.unlink(pdf_path)
            except:
                pass
    except Exception as e:
        logger.error(f"DOCX to PDF conversion failed: {str(e)}")
        return None

def remove_duplicates(text: str, threshold: float = 0.92) -> str:
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    unique_paragraphs = []
    for p in paragraphs:
        if len(p) < 15:
            unique_paragraphs.append(p)
            continue
        is_duplicate = False
        for existing in unique_paragraphs:
            if len(existing) < 15:
                continue
            if SequenceMatcher(None, p, existing).ratio() > threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_paragraphs.append(p)
    return '\n\n'.join(unique_paragraphs)

def calculate_parse_score(text):
    if not text:
        return 0
    word_count = len(text.split())
    if word_count < 50:
        return max(10, int(word_count / 5))
    paragraphs = text.split('\n\n')
    unique_words = set(word.lower() for word in text.split())
    vocab_richness = len(unique_words) / word_count if word_count else 0
    job_terms = ['experience', 'skills', 'requirements', 'responsibilities', 'qualifications', 
                 'education', 'salary', 'benefits', 'position', 'job', 'work', 'team']
    term_matches = sum(1 for term in job_terms if term.lower() in text.lower())
    term_score = min(40, term_matches * 4)
    structure_score = min(30, len(paragraphs))
    vocab_score = min(20, int(vocab_richness * 100))
    return max(10, min(100, term_score + structure_score + vocab_score))

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    text = ' '.join(text.split())
    text = ''.join(char for char in text if char.isprintable() or char == '\n')
    replacements = {
        '\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '*', '\u2026': '...'
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.encode('ascii', 'ignore').decode()

from anthropic.types import Message

def format_with_claude(text: str) -> str:
    if not anthropic:
        logger.warning("Anthropic not initialized. Skipping formatting.")
        return text

    try:
        logger.info("Sending text to Claude for formatting")
        response: Message = anthropic.messages.create(
            model="claude-3-sonnet-20240229",
            temperature=0.2,
            max_tokens=4000,
            system="You are an assistant that formats job descriptions for clarity and structure. Do not rewrite or change meaning.",
            messages=[
                {"role": "user", "content": f"Format this job description cleanly without changing its content:\n\n{text}"}
            ]
        )

        if response and hasattr(response, "content") and isinstance(response.content, list):
            formatted_blocks = [part.text.strip() for part in response.content if part.type == "text"]
            formatted_text = "\n\n".join(formatted_blocks)
            logger.info("Received formatted text from Claude")
            return formatted_text if formatted_text else text

        logger.warning("Claude response was empty or malformed")
        return text

    except Exception as e:
        logger.error(f"Claude formatting failed: {e}")
        return text

async def parse_document(file_bytes: bytes, content_type: str) -> dict:
    logger.info(f"Parsing document with content type: {content_type}")
    text = ""
    is_image_based = False
    formatted_text = ""
    if content_type == "application/pdf":
        text, is_image_based = extract_text_from_pdf(file_bytes)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            logger.info("Converting DOCX to PDF for flattening")
            pdf_bytes = convert_docx_to_pdf(file_bytes)
            if pdf_bytes:
                text, is_image_based = extract_text_from_pdf(pdf_bytes)
            else:
                logger.warning("PDF conversion failed, falling back to direct DOCX extraction")
                text, _ = extract_text_from_docx(file_bytes)
        except Exception as e:
            logger.warning(f"Fallback to direct DOCX extraction: {str(e)}")
            text, _ = extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")
    if not text:
        raise Exception("No extractable text")
    logger.info("Cleaning and deduplicating extracted text")
    cleaned = clean_text(remove_duplicates(text))
    if not cleaned:
        logger.warning("Text cleaning resulted in empty text, using original")
        cleaned = text
    word_count = len(cleaned.split())
    parse_score = calculate_parse_score(cleaned)
    preview = cleaned[:200] + "..." if len(cleaned) > 200 else cleaned
    logger.info(f"Parse score: {parse_score} | Word count: {word_count}")
    try:
        formatted_text = format_with_claude(cleaned)
    except Exception as e:
        logger.error(f"Claude formatting failed, using cleaned text: {str(e)}")
        formatted_text = cleaned
    if not formatted_text:
        formatted_text = cleaned
    return {
        "text": cleaned,
        "formatted_text": formatted_text,
        "word_count": word_count,
        "parse_score": parse_score,
        "preview": preview,
        "is_image_based": is_image_based,
        "timestamp": datetime.utcnow().isoformat(),
        "detected_format": content_type
    }
