from fastapi import FastAPI, UploadFile, File
import ReadFile
import mongoDB

app = FastAPI()

@app.post("/upload")
async def upload_document(file: UploadFile):
    content = ""
    if file.filename.endswith('.pdf'):
        content = ReadFile.extract_pdf_text(file.file)
    elif file.filename.endswith('.docx'):
        content = ReadFile.extract_docx_text(file.file)
    elif file.filename.endswith('.xlsx'):
        content = ReadFile.extract_xlsx_text(file.file)
    title = file.filename
    mongoDB.upload_document_to_db(title, content, user="students", category="manual")

    return {"message": "Document upload successfully"}

@app.get("/search")
def search(query: str):
    #results = search_documents(query)
    results = "Документ найден"
    return results

@app.get("/document/{id}")
def get_document(file_id: str):
    doc = mongoDB.get_document_db(file_id)
    return doc.get("content")

@app.delete("/document/{id}")
async def delete_document(file_id: str):
    mongoDB.delete_document_db(file_id)
    return {"message": "Document deleted successfully"}

@app.post("/update/{id}")
async def update_document(file_id: str, file: UploadFile):
    content = ""
    if file.filename.endswith('.pdf'):
        content = ReadFile.extract_pdf_text(file.file)
    elif file.filename.endswith('.docx'):
        content = ReadFile.extract_docx_text(file.file)
    elif file.filename.endswith('.xlsx'):
        content = ReadFile.extract_xlsx_text(file.file)
    mongoDB.update_document_db(file_id, content)
    return {"message": "Document update successfully"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)