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
import json

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

def extract_candidate_info(text: str) -> dict:
    """
    Extract structured candidate information from CV text using Claude.
    
    Args:
        text: The extracted text from the CV
        
    Returns:
        dict: Structured candidate information
    """
    if not anthropic:
        logger.warning("Anthropic client not available, returning empty candidate info")
        return post_process_extracted_info({})
    
    try:
        prompt = f"""Extract candidate information from the following CV text and return it in the specified JSON schema. 
If a field is missing from the CV, still include it with null, "", or [] as appropriate. Do not skip any fields.

CV Text:
{text}

Return the information in this exact JSON schema:
{{
    "full_name": "string or null",
    "email": "string or null",
    "phone": "string or null",
    "location": "string or null",
    "linkedin": "string or null",
    "github": "string or null",
    "summary": "string or null",
    "skills": ["string"],
    "education": [
        {{
            "degree": "string",
            "institution": "string",
            "year_completed": "string"
        }}
    ],
    "experience": [
        {{
            "job_title": "string",
            "company": "string",
            "duration": "string",
            "responsibilities": ["string"]
        }}
    ],
    "certifications": [
        {{
            "name": "string",
            "issuer": "string",
            "year": "string"
        }}
    ],
    "languages": ["string"],
    "availability": "string or null"
}}

Return only the JSON object, no other text or explanation."""

        response = anthropic.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        if not response.content:
            logger.warning("Empty response from Claude for candidate info extraction")
            return post_process_extracted_info({})
            
        try:
            # Extract the JSON from the response
            content = response.content[0].text
            # Find the first { and last } to extract the JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                logger.warning("No JSON found in Claude response")
                return post_process_extracted_info({})
                
            json_str = content[start:end]
            extracted_info = json.loads(json_str)
            return post_process_extracted_info(extracted_info)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            return post_process_extracted_info({})
            
    except Exception as e:
        logger.error(f"Error extracting candidate info with Claude: {e}")
        return post_process_extracted_info({})

def post_process_extracted_info(info: dict) -> dict:
    """
    Ensure all expected fields exist in the extracted candidate information.
    
    Args:
        info: The extracted candidate information
        
    Returns:
        dict: Post-processed candidate information with all fields
    """
    default_info = {
        "full_name": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin": None,
        "github": None,
        "summary": None,
        "skills": [],
        "education": [],
        "experience": [],
        "certifications": [],
        "languages": [],
        "availability": None
    }
    
    # Update with any existing values from info
    for key, value in info.items():
        if key in default_info:
            if isinstance(value, list):
                # Ensure list items have the correct structure
                if key == "education":
                    default_info[key] = [
                        {
                            "degree": item.get("degree", ""),
                            "institution": item.get("institution", ""),
                            "year_completed": item.get("year_completed", "")
                        }
                        for item in value
                    ]
                elif key == "experience":
                    default_info[key] = [
                        {
                            "job_title": item.get("job_title", ""),
                            "company": item.get("company", ""),
                            "duration": item.get("duration", ""),
                            "responsibilities": item.get("responsibilities", [])
                        }
                        for item in value
                    ]
                elif key == "certifications":
                    default_info[key] = [
                        {
                            "name": item.get("name", ""),
                            "issuer": item.get("issuer", ""),
                            "year": item.get("year", "")
                        }
                        for item in value
                    ]
                else:
                    default_info[key] = value
            else:
                default_info[key] = value
    
    return default_info

def parse_document(file_bytes: bytes, content_type: str) -> dict:
    """
    Parse a document and extract its text content.
    
    Args:
        file_bytes: The file content as bytes
        content_type: The MIME type of the file
        
    Returns:
        dict: Parsed document information
    """
    logger.info(f"Parsing document with content type: {content_type}")
    extracted_text = ""
    formatted_text = ""
    
    try:
        if content_type == "application/pdf":
            text_result = extract_text_from_pdf(file_bytes)
            if isinstance(text_result, tuple):
                extracted_text = text_result[0]  # Get the text from the tuple
            else:
                extracted_text = text_result
        elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            try:
                # Try converting to PDF first
                pdf_bytes = convert_docx_to_pdf(file_bytes)
                if pdf_bytes:
                    text_result = extract_text_from_pdf(pdf_bytes)
                    if isinstance(text_result, tuple):
                        extracted_text = text_result[0]  # Get the text from the tuple
                    else:
                        extracted_text = text_result
                else:
                    logger.warning("PDF conversion failed, falling back to direct DOCX extraction")
                    extracted_text = extract_text_from_docx(file_bytes)
            except Exception as e:
                logger.warning(f"PDF conversion failed, falling back to direct DOCX extraction: {e}")
                extracted_text = extract_text_from_docx(file_bytes)
        else:
            raise ValueError(f"Unsupported content type: {content_type}")
            
        if not extracted_text:
            raise Exception("No text could be extracted from the document")
            
        # Clean and deduplicate the text
        cleaned_text = clean_text(extracted_text)
        deduplicated_text = remove_duplicates(cleaned_text)
        
        # Calculate word count and parse score
        word_count = len(deduplicated_text.split())
        parse_score = calculate_parse_score(deduplicated_text)
        
        # Create preview (first 500 characters)
        preview = deduplicated_text[:500] + "..." if len(deduplicated_text) > 500 else deduplicated_text
        
        # Extract structured candidate information
        extracted_info = extract_candidate_info(deduplicated_text)
        
        # Try to format with Claude
        try:
            formatted_text = format_with_claude(deduplicated_text)
            if not formatted_text:
                logger.warning("Empty result from Claude formatting, using cleaned text")
                formatted_text = deduplicated_text
        except Exception as e:
            logger.error(f"Error formatting with Claude: {e}")
            formatted_text = deduplicated_text
            
        return {
            "text": formatted_text,
            "word_count": word_count,
            "parse_score": parse_score,
            "preview": preview,
            "extracted_info": extracted_info
        }
        
    except Exception as e:
        logger.error(f"Error parsing document: {e}")
        raise
