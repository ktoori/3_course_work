from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse
from typing import List, Literal
import os
from pathlib import Path
import ReadFile
import mongoDB
import CreateTags
import nltk


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
        list(mongoDB.get_dict_by_name("content_tags_dict").keys()),
        description="Выберите теги из списка"
    ),
    program_track_tags: List[str] = Query(
        list(mongoDB.get_dict_by_name("program_tags_dict").keys()),
        description="Выберите теги из списка"
    ),
    doc_type_tags: List[str] = Query(
        list(mongoDB.get_dict_by_name("doc_type_dict").keys()),
        description="Выберите теги из списка"
    ),
    other_tags: List[str] = Query(
        mongoDB.get_dict_by_name("other_tags"),
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


@app.post("/add_tag", summary="Добавить тег с ассоциациями")
def add_tag(
        dict_name: Literal["other_tags", "content_tags_dict", "program_tags_dict", "doc_type_dict"] = Query(...),
        tag: str = Query(...),
        associations: str = Query("")):
    if dict_name == "other_tags":
        other_tags = mongoDB.get_dict_by_name("other_tags")
        if tag not in other_tags:
            # Проверяем лимит
            total_tags = mongoDB.get_total_tag_count()
            limit = mongoDB.get_global_tag_limit()
            if limit is not None and total_tags >= limit:
                raise HTTPException(status_code=400, detail="Global tag limit exceeded")
            other_tags.append(tag)
            mongoDB.set_dict_by_name("other_tags", other_tags)
            result = mongoDB.sync_tags_collection()
            return {"message": "Tag added to other_tags", "data": other_tags, "r": result}
        else:
            return {"message": "Tag already exists in other_tags", "data": other_tags}

    tag_dict = mongoDB.get_dict_by_name(dict_name)
    if not isinstance(tag_dict, dict):
        raise HTTPException(status_code=400, detail="Target dictionary is not a dict")

    total_tags = mongoDB.get_total_tag_count()
    limit = mongoDB.get_global_tag_limit()
    is_new = tag not in tag_dict
    if limit is not None and total_tags >= limit and is_new:
        raise HTTPException(status_code=400, detail="Global tag limit exceeded")

    assoc_list = associations.split() if associations else []

    if tag in tag_dict:
        for v in assoc_list:
            if v not in tag_dict[tag]:
                tag_dict[tag].append(v)
    else:
        tag_dict[tag] = assoc_list

    mongoDB.set_dict_by_name(dict_name, tag_dict)
    result = mongoDB.sync_tags_collection()
    return {"message": "Tag added successfully", "data": tag_dict, "r": result}


@app.delete("/delete_tags")
def delete_tags(
        dict_name: Literal["other_tags", "content_tags_dict", "program_tags_dict", "doc_type_dict"] = Query(...),
        tags: str = Query(...)):
    tag_dict = mongoDB.get_dict_by_name(dict_name)
    tags_to_delete = tags.split()

    if isinstance(tag_dict, dict):
        for tag in tags_to_delete:
            tag_dict.pop(tag, None)
        mongoDB.set_dict_by_name(dict_name, tag_dict)
        return {"message": "Tags deleted successfully", "data": tag_dict}
    elif isinstance(tag_dict, list):
        tag_dict = [t for t in tag_dict if t not in tags_to_delete]
        mongoDB.set_dict_by_name(dict_name, tag_dict)
        return {"message": "Tags deleted successfully", "data": tag_dict}
    else:
        raise HTTPException(status_code=400, detail="Unsupported tag storage type")


@app.get("/get_tags")
def get_tags():
    config = mongoDB.get_config()
    return {
        "content_tags": config.get("content_tags_dict", {}),
        "program_tags": config.get("program_tags_dict", {}),
        "doc_type": config.get("doc_type_dict", {}),
        "other_tags": config.get("other_tags", []),
        "global_tag_limit": config.get("global_tag_limit")
    }


@app.post("/set_limit", summary="Установить глобальный лимит на количество тегов")
def set_limit(limit: int):
    mongoDB.set_global_tag_limit(limit)
    return {"message": "Global limit updated", "limit": limit}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)