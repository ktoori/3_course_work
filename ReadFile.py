import re
import PyPDF2
import pandas as pd
from docx import Document

# удаляем лишние пробелы и nan
def clean_text(text: str) -> str:
    cleaned_text = re.sub(r'\bnan*\b', '', text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return cleaned_text if cleaned_text else ""

def extract_pdf_text(file):
    reader = PyPDF2.PdfReader(file)
    number_of_pages = len(reader.pages)
    text = ""
    for page in range(number_of_pages):
        text += reader.pages[page].extract_text()
    return clean_text(text)

def extract_docx_text(file):
    doc = Document(file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text += cell.text
    return clean_text(text)

def extract_xlsx_text(file):
    df = pd.read_excel(file)
    text = ""
    for index, row in df.iterrows():
        text += " ".join(str(cell) for cell in row) + "\n"
    return clean_text(text)