from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse
from typing import List, Literal
import os
from pathlib import Path
import nltk

import Moderation
import ReadFile
import mongoDB
from mongoDB import TagStructure, SearchFunction
from CreateTags import TagGenerate


nltk.download('punkt')
nltk.download('stopwords')
app = FastAPI()

UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

tag_structure = TagStructure()

CONTENT_TAGS = list(tag_structure.get_dict_by_name("content_tags_dict").keys())
PROGRAM_TAGS = list(tag_structure.get_dict_by_name("program_tags_dict").keys())
DOC_TYPE_TAGS = list(tag_structure.get_dict_by_name("doc_type_dict").keys())
OTHER_TAGS = tag_structure.get_dict_by_name("other_tags")

def save_file_to_server(file: UploadFile) -> str:
    file_name = Path(file.filename).name
    file_location = os.path.join(UPLOAD_DIRECTORY, file_name)
    file.file.seek(0)
    content = file.file.read()
    with open(file_location, "wb") as buffer:
        buffer.write(content)
    print(f"[DEBUG] Файл сохранен: {file_location} ({len(content)} байт)")
    return file_location



@app.post("/upload_for_moderation", response_model=dict)
async def upload_document_for_moderation(
        file: UploadFile = File(...),
        content_tags: List[str] = Query(
            CONTENT_TAGS,
            description="Выберите теги из списка"
        ),
        program_track_tags: List[str] = Query(
            PROGRAM_TAGS,
            description="Выберите теги из списка"
        ),
        doc_type_tags: List[str] = Query(
            DOC_TYPE_TAGS,
            description="Выберите теги из списка"
        ),
        other_tags: List[str] = Query(
            OTHER_TAGS,
            description="Выберите теги из списка"
        ),
        use_auto_tags: bool = Form(
            True,
            description="Добавить автоматически сгенерированные теги"
        ),
        user: str = Form("student"),
):
    """Загрузить документ на модерацию"""
    try:
        content = ""
        if file.filename.endswith('.pdf'):
            content = await ReadFile.extract_pdf_text(file.file)
        elif file.filename.endswith('.docx'):
            content = await ReadFile.extract_docx_text(file.file)
        elif file.filename.endswith('.xlsx'):
            content = await ReadFile.extract_xlsx_text(file.file)

        content = ReadFile.clean_text(content) if content else ""
        file_path = save_file_to_server(file)

        final_tags = []

        if content_tags:
            final_tags.extend(tag.strip() for tag in content_tags if tag.strip())
        if program_track_tags:
            final_tags.extend(tag.strip() for tag in program_track_tags if tag.strip())
        if doc_type_tags:
            final_tags.extend(tag.strip() for tag in doc_type_tags if tag.strip())
        if other_tags:
            final_tags.extend(tag.strip() for tag in other_tags if tag.strip())

        if use_auto_tags:
            tag_service = TagGenerate()
            auto_tags = tag_service.extract_keywords(content)
            final_tags.extend(tag for tag in auto_tags if tag not in final_tags)

        if not final_tags:
            final_tags.append(Path(file.filename).stem.lower())

        final_tags = list(set(final_tags))

        doc_id = Moderation.upload_document_to_moderation(
            file.filename, content, file_path, user, final_tags
        )
        return {
            "status": "OK",
            "message": "Документ отправлен на модерацию",
            "document_id": str(doc_id),
            "filename": file.filename,
            "tags": final_tags
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/moderation/documents")
async def get_documents_for_moderation(
        status: str = Query(None, description="Статус модерации (pending, approved, rejected)"),
        admin: str = Query(..., description="Имя администратора")
):
    """Получить список документов на модерации"""
    if admin != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    documents = Moderation.get_moderation_documents(status)
    for doc in documents:
        doc["_id"] = str(doc["_id"])
    return JSONResponse(documents)


@app.post("/moderation/approve")
async def approve_moderation_document(
        doc_id: str = Query(...),
        admin: str = Query(...),
        final_tags: List[str] = Query(None)
):
    """Одобрить документ после модерации"""
    if admin != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    success = Moderation.approve_document(doc_id, admin, final_tags)
    if success:
        return {"status": "OK", "message": "Документ одобрен и добавлен в основную базу"}
    else:
        raise HTTPException(status_code=400, detail="Не удалось одобрить документ")


@app.post("/moderation/reject")
async def reject_moderation_document(
        doc_id: str = Query(...),
        moderator: str = Query(...),
        reason: str = Query(None)
):
    """Отклонить документ после модерации"""
    if moderator != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    success = Moderation.reject_document(doc_id, moderator)
    if success:
        return {"status": "OK", "message": "Документ отклонен"}
    else:
        raise HTTPException(status_code=400, detail="Не удалось отклонить документ")

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
        tag_service = TagGenerate()
        auto_tags = tag_service.extract_keywords(content)

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
            CONTENT_TAGS,
            description="Выберите теги из списка"
        ),
        program_track_tags: List[str] = Query(
            PROGRAM_TAGS,
            description="Выберите теги из списка"
        ),
        doc_type_tags: List[str] = Query(
            DOC_TYPE_TAGS,
            description="Выберите теги из списка"
        ),
        other_tags: List[str] = Query(
            OTHER_TAGS,
            description="Выберите теги из списка"
        ),
        use_auto_tags: bool = Form(
            True,
            description="Добавить автоматически сгенерированные теги"
        ),
        user: str = Form("admin"),
):
    """Загрузить документ с выбранными тегами (только для администраторов)"""
    if user != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

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
        tag_service = TagGenerate()
        auto_tags = tag_service.extract_keywords(content)
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


@app.get("/search",  summary="Найти документ по запросу")
async def search(query: str):
    _search = SearchFunction()
    result = _search.search_by_tag(query)
    return result


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
        tag_service = TagGenerate()
        tags = tag_service.extract_keywords(content)
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
        associations: str = Query("")
):
    """
    Добавляет тег в словари в config
    :param dict_name: название словаря
    :param tag: добавляемый тег (название категории)
    :param associations: ассоциации с тегом
    """
    tag_structure = TagStructure()
    if dict_name == "other_tags":
        other_tags = tag_structure.get_dict_by_name("other_tags")
        if tag not in other_tags:
            total_tags = tag_structure.get_total_tag_count()
            limit = tag_structure.get_global_tag_limit()
            if (limit is not None) and (total_tags >= limit):
                raise HTTPException(status_code=400, detail="Tag limit exceeded")
            other_tags.append(tag)
            tag_structure.set_dict_by_name("other_tags", other_tags)
            result = tag_structure.sync_tags_collection()
            return {"message": "Tag added to other_tags", "result": result}
        else:
            return {"message": "Tag already in other_tags", "other_tags": other_tags}

    tag_dict = tag_structure.get_dict_by_name(dict_name)
    if not tag_dict:
        raise HTTPException(status_code=400, detail="Dict not found")
    total_tags = tag_structure.get_total_tag_count()
    limit = tag_structure.get_global_tag_limit()
    if (tag not in tag_dict) and (limit is not None) and total_tags >= limit:
        raise HTTPException(status_code=400, detail="Tag limit exceeded")

    associations_list = []
    if associations:
        associations_list = associations.split()

    if tag in tag_dict:
        for assoc_tag in associations_list:
            if assoc_tag not in tag_dict[tag]:
                tag_dict[tag].append(assoc_tag)
    else:
        tag_dict[tag] = associations_list

    tag_structure.set_dict_by_name(dict_name, tag_dict)
    result = tag_structure.sync_tags_collection()
    return {"message": "Tag added successfully", "result": result}


@app.delete("/delete_tags", summary="Удалить тег из указанного словаря dict")
def delete_tags(
        dict_name: Literal["other_tags", "content_tags_dict", "program_tags_dict", "doc_type_dict"] = Query(...),
        tags: str = Query(...)
):
    """
    Удаляет теги из словаря
    :param dict_name: название словаря
    :param tags: теги для удаления
    """
    tag_structure = TagStructure()
    tag_dict = tag_structure.get_dict_by_name(dict_name)
    tags_to_delete = tags.split()

    if tag_dict == "other_tags":
        tag_dict = []
        for tag in tag_dict:
            if tag not in tags_to_delete:
                tag_dict.append(tag)
        tag_structure.set_dict_by_name(dict_name, tag_dict)
        result = tag_structure.sync_tags_collection()
        return {"message": "Tags deleted successfully", "result": result}
    else:
        for tag in tags_to_delete:
            tag_dict.pop(tag, None)
        tag_structure.set_dict_by_name(dict_name, tag_dict)
        result = tag_structure.sync_tags_collection()
        return {"message": "Tags deleted successfully", "result": result}


@app.get("/get_structure_information", summary="Получить все словари тегов и установленный лимит")
def get_structure_information():
    """
    Возвращает все словари и лимит тегов из config
    """
    tag_structure = TagStructure()
    config = tag_structure.get_config()
    return {
        "content_tags": config.get("content_tags_dict", {}),
        "program_tags": config.get("program_tags_dict", {}),
        "doc_type": config.get("doc_type_dict", {}),
        "other_tags": config.get("other_tags", []),
        "global_tag_limit": config.get("global_tag_limit")
    }


@app.post("/set_limit", summary="Установить глобальный лимит на количество тегов")
def set_limit(limit: int):
    """
    Устанавливает лимит тегов
    :param limit: лимит тегов
    """
    tag_structure = TagStructure()
    tag_structure.set_global_tag_limit(limit)
    return {"message": "Global limit updated", "limit": limit}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
