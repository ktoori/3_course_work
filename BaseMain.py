from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse
from typing import List
import os
from pathlib import Path
import ReadFile
import mongoDB
import CreateTags
import nltk
import Dictionaries

nltk.download('punkt')
nltk.download('stopwords')
app = FastAPI()

UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

def save_file_to_server(file: UploadFile) -> str:
    file_name = Path(file.filename).name
    file_location = os.path.join(UPLOAD_DIRECTORY, file_name)
    file.file.seek(0)
    content = file.file.read()
    with open(file_location, "wb") as buffer:
        buffer.write(content)
    print(f"[DEBUG] Файл сохранен: {file_location} ({len(content)} байт)")
    return file_location


@app.post("/generate_tags")
async def document_tags(file: UploadFile = File(...)):
    """Анализирует документ и возвращает список тегов"""
    try:
        content = ""
        if file.filename.endswith('.pdf'):
            content = await ReadFile.extract_pdf_text(file.file)
        elif file.filename.endswith('.docx'):
            content = await ReadFile.extract_docx_text(file.file)
        elif file.filename.endswith('.xlsx'):
            content = await ReadFile.extract_xlsx_text(file.file)

        content = ReadFile.clean_text(content) if content else ""
        auto_tags = CreateTags.extract_keywords(content)

        return JSONResponse({
            "filename": file.filename,
            "content_length": len(content),
            "auto_tags": auto_tags
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),

    content_tags: List[str] = Query(
        Dictionaries.content_tags,
        description="Выберите теги из списка"
    ),
    program_track_tags: List[str] = Query(
        Dictionaries.program_track_tags,
        description="Выберите теги из списка"
    ),
    doc_type_tags: List[str] = Query(
        Dictionaries.doc_type_tags,
        description="Выберите теги из списка"
    ),
    other_tags: List[str] = Query(
        Dictionaries.other_tags,
        description="Выберите теги из списка"
    ),
    use_auto_tags: bool = Form(
        True,
        description="Добавить автоматически сгенерированные теги"
    ),
    user: str = Form("student"),
):
    """Загрузить документ с выбранными тегами"""
    content = ""
    if file.filename.endswith('.pdf'):
        content = await ReadFile.extract_pdf_text(file.file)
    elif file.filename.endswith('.docx'):
        content = await ReadFile.extract_docx_text(file.file)
    elif file.filename.endswith('.xlsx'):
        content = await ReadFile.extract_xlsx_text(file.file)

    content = ReadFile.clean_text(content) if content else ""
    file_path = save_file_to_server(file)
    # Определяем итоговые теги
    final_tags = []

    # Добавляем выбранные теги
    if content_tags:
        final_tags.extend(tag.strip() for tag in content_tags if tag.strip())
    if program_track_tags:
        final_tags.extend(tag.strip() for tag in program_track_tags if tag.strip())
    if doc_type_tags:
        final_tags.extend(tag.strip() for tag in doc_type_tags if tag.strip())
    if other_tags:
        final_tags.extend(tag.strip() for tag in other_tags if tag.strip())
    selected_tags= [final_tags]
    # Добавляем автоматические теги (если включено)
    if use_auto_tags:
        auto_tags = CreateTags.extract_keywords(content)
        final_tags.extend(tag for tag in auto_tags if tag not in final_tags)

    # Если нет тегов - используем имя файла
    if not final_tags:
        final_tags.append(Path(file.filename).stem.lower())

    # Удаляем дубликаты
    final_tags = list(set(final_tags))

    # Сохраняем в БД (моделируем вызов)
    doc_id = mongoDB.upload_document_to_db(file.filename, content, file_path, user=user,
                                           tags=final_tags)
    if not doc_id:
        raise HTTPException(status_code=400, detail="Документ уже существует в базе данных")
    return {
        "status": "success",
        "document_id": str(doc_id),
        "filename": file.filename,
        "selected_tags": selected_tags,
        "auto_tags_used": use_auto_tags,
        "final_tags": final_tags
    }


@app.get("/search")
async def search(query: str):
    result = mongoDB.search_by_tag(query)
    return ' '.join(result)


@app.get("/get_document")
async def get_document(file_id: str):
    doc = mongoDB.get_document_db(file_id)
    if doc:
        return doc.get("content")
    else:
        raise HTTPException(status_code=404, detail="Документ не найден")

@app.get("/download_document")        #через swagger работает
async def download_document(file_id: str):
    document = mongoDB.get_document_db(file_id)
    if document and os.path.exists(document['file_path']):
        return FileResponse(document['file_path'], filename=document['title'])
    else:
        raise HTTPException(status_code=404, detail="Файл не найден")

@app.delete("/delete_document")
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


@app.put("/update_document")
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
        tags = CreateTags.extract_keywords(content)
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