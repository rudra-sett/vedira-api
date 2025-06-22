import json
import base64
import io
import os
import logging

# Try to import docx and PyPDF2, handle cases where they might not be installed
try:
    from docx import Document
except ImportError:
    Document = None
    logging.warning("python-docx not installed. DOCX parsing will not be available.")

try:
    import pymupdf # PyMuPDF
except ImportError:
    pymupdf = None
    logging.warning("PyMuPDF not installed. PDF parsing will not be available.")

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

def extract_text_from_pdf(file_stream):
    """Extracts text from a PDF file stream using PyMuPDF."""
    if pymupdf is None:
        raise ImportError("PyMuPDF is not installed. Cannot process PDF files.")
    
    text = ""
    try:
        # PyMuPDF can open directly from a bytes stream
        doc = pymupdf.open(stream=file_stream.read(), filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        logger.error(f"Error extracting text from PDF with PyMuPDF: {e}")
        raise
    return text

def extract_text_from_docx(file_stream):
    """Extracts text from a DOCX file stream."""
    if Document is None:
        raise ImportError("python-docx is not installed. Cannot process DOCX files.")
    
    text = ""
    try:
        document = Document(file_stream)
        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        raise
    return text

def lambda_handler(event, context):
    """
    Lambda function to extract text from various document types.
    Expects a JSON body with 'document_content' (base64 encoded) and 'content_type'.
    """
    try:        
        print("Received event:", json.dumps(event, indent=2))
        document_content_b64 = event.get('document_content')
        content_type = event.get('content_type', '').lower()

        if not document_content_b64:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing document_content in request body'})
            }

        document_bytes = base64.b64decode(document_content_b64)
        file_stream = io.BytesIO(document_bytes)

        extracted_text = ""
        if "application/pdf" in content_type:
            extracted_text = extract_text_from_pdf(file_stream)
        elif "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type:
            extracted_text = extract_text_from_docx(file_stream)
        else:
            return {
                'statusCode': 415, # Unsupported Media Type
                'body': json.dumps({'error': f'Unsupported content type: {content_type}. Only PDF and DOCX are supported.'})
            }

        return {
            'statusCode': 200,
            'body': json.dumps({'extracted_text': extracted_text})
        }

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Server error: {e}. Please ensure required libraries are installed.'})
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'An unexpected error occurred: {str(e)}'})
        }
