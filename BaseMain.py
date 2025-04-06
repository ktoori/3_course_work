from fastapi import FastAPI, UploadFile, File, HTTPException, Form
import nltk
from starlette.responses import FileResponse
import os
import ReadFile
import mongoDB
import CreateTags2
from typing import Optional, List, Dict, Any

nltk.download('punkt_tab')

app = FastAPI()

# Директория для хранения файлов
UPLOAD_DIRECTORY = "uploads"

# Создаем директорию для загрузки файлов, если она не существует
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

# Функция для сохранения файла на сервере
def save_file_to_server(file: UploadFile) -> str:
    file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
    with open(file_location, "wb") as buffer:
        buffer.write(file.file.read())
    return file_location

@app.post("/upload")
async def upload_document(file: UploadFile = File(...), tags: Optional[str] = Form(None)):
    content = ""
    if file.filename.endswith('.pdf'):
        content = ReadFile.extract_pdf_text(file.file)
    elif file.filename.endswith('.docx'):
        content = ReadFile.extract_docx_text(file.file)
    elif file.filename.endswith('.xlsx'):
        content = ReadFile.extract_xlsx_text(file.file)
    file_path = save_file_to_server(file)
    title = file.filename
    if not tags:
        tags = CreateTags2.extract_keywords(content)
        tags.append(file.filename)
    else:
        tags = tags.split(",")
    #doc_id = mongoDB.upload_document_to_db(title, content,file_path, user="students", category="manual", tags= tags)
    doc_id = mongoDB.upload_document_to_db(title, content, file_path, user="students", category="manual", tags=tags)
    if not doc_id:
        raise HTTPException(status_code=400, detail="Документ уже существует в базе данных")

    return {"message": "Документ успешно загружен", "file_id": str(doc_id)}

@app.get("/search")
async def search(query: str):
    result = mongoDB.search_by_tag(query)
    if result == 11:
        raise HTTPException(status_code=404, detail="Тег не найден")
    elif result == 22:
        raise HTTPException(status_code=404, detail="Документ не найден")
    else:
        answer = []
        for docs in result:
            object_id = docs[1]["_id"]
            answer.append(str(object_id))
        return ' '.join(answer)


@app.get("/document/{id}")
async def get_document(file_id: str):
    doc = mongoDB.get_document_db(file_id)
    if doc:
        return doc.get("content")
    else:
        raise HTTPException(status_code=404, detail="Документ не найден")

@app.get("/download/{doc_id}")        #через swagger работает
async def download_document(doc_id: str):
    document = mongoDB.get_document_db(doc_id)
    if document and os.path.exists(document['file_path']):
        return FileResponse(document['file_path'], filename=document['title'])
    else:
        raise HTTPException(status_code=404, detail="Файл не найден")

@app.delete("/document/{id}")
async def delete_document(file_id: str):
    document = mongoDB.get_document_db(file_id)
    if document:
        # Удаляем файл с сервера
        if os.path.exists(document['file_path']):
            os.remove(document['file_path'])
        # Удаляем документ из MongoDB
        deleted_count = mongoDB.delete_document_db(file_id)
        if deleted_count > 0:
            return {"message": "Документ успешно удален"}
        else:
            raise HTTPException(status_code=404, detail="Документ не найден")
    else:
        raise HTTPException(status_code=404, detail="Документ не найден")


@app.post("/update/{id}")
async def update_document(file_id: str, file: UploadFile):
    document = mongoDB.get_document_db(file_id)
    if document:
        content = ""
        if file.filename.endswith('.pdf'):
            content = ReadFile.extract_pdf_text(file.file)
        elif file.filename.endswith('.docx'):
            content = ReadFile.extract_docx_text(file.file)
        elif file.filename.endswith('.xlsx'):
            content = ReadFile.extract_xlsx_text(file.file)
        tags = CreateTags2.extract_keywords(content)
        # Удаляем старый файл с сервера
        if os.path.exists(document['file_path']):
            os.remove(document['file_path'])

        # Сохраняем новый файл на сервере
        new_file_path = save_file_to_server(file)

        # Обновляем документ в MongoDB
        modified_count = mongoDB.update_document_db(file_id, content, new_file_path, tags)
        if modified_count > 0:
            return {"message": "Документ успешно обновлен"}
        else:
            raise HTTPException(status_code=404, detail="Документ не найден")
    else:
        raise HTTPException(status_code=404, detail="Документ не найден")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)