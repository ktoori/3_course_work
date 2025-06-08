import PyPDF2
from docx import Document
import pandas as pd
import re
from fastapi import UploadFile
from typing import BinaryIO
import io


# удаляем лишние пробелы и nan
def clean_text(text: str) -> str:
    cleaned_text = re.sub(r'\bnan*\b', '', text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return cleaned_text if cleaned_text else ""

async def extract_pdf_text(file: BinaryIO) -> str:
    content = file.read()
    with io.BytesIO(content) as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        return clean_text(" ".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        ))

async def extract_docx_text(file: BinaryIO) -> str:
    content = file.read()
    with io.BytesIO(content) as docx_file:
        doc = Document(docx_file)
        return clean_text(" ".join(
            para.text for para in doc.paragraphs if para.text.strip()
        ))

async def extract_xlsx_text(file: BinaryIO) -> str:
    content =  file.read()
    with io.BytesIO(content) as xlsx_file:
        df = pd.read_excel(xlsx_file)
        return clean_text(" ".join(
            str(cell) for row in df.values for cell in row
            if pd.notna(cell) and str(cell).strip()
        ))

async def extract_content(file: UploadFile) -> str:
    if file.filename.endswith('.pdf'):
        return await extract_pdf_text(file.file)
    elif file.filename.endswith('.docx'):
        return await extract_docx_text(file.file)
    elif file.filename.endswith('.xlsx'):
        return await extract_xlsx_text(file.file)
    raise ValueError("Unsupported file format")