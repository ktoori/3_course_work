from pymongo import MongoClient
from datetime import datetime

# Подключение к MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client['database']
collection = db["documents"]


def upload_document_to_db(title, content,file_path, user, category, tags=None):
    """
    Добавляет документ в MongoDB с указанием пути к файлу.
    """
    duplicate = collection.find_one({
        "$or": [
            {"title": title},
            {"file_path": file_path},
            {"content": content}
        ]
    })

    if duplicate:
        print(f"Документ уже существует в базе данных: {title}")
        return None

    document = {
        "title": title,
        "content": content,
        "file_path": file_path,  # Путь к файлу на сервере
        "user": user,             # students, teacher
        "category": category,     # schedule, template, manual, instructions
        "tags": tags if tags else [],
        "created_at": datetime.utcnow()
    }

    result = collection.insert_one(document)
    print(f"Документ успешно загружен. ID: {result.inserted_id}")
    return result.inserted_id

def get_document_db(doc_id):
    """
    Получает документ из MongoDB по его ID.
    """
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        document = collection.find_one({"_id": doc_id})
        if document:
            return document
        else:
            print("Документ не найден.")
            return None
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return None

def delete_document_db(doc_id):
    """
    Удаляет документ из MongoDB по его ID.
    """
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        result = collection.delete_one({"_id": doc_id})
        if result.deleted_count > 0:
            print("Документ успешно удален.")
        else:
            print("Документ не найден.")
        return result.deleted_count
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return 0

def update_document_db(doc_id,new_content,new_file_path, new_tags=None, new_title=None, new_category=None):
    """
    Обновляет документ в MongoDB, включая путь к файлу.
    """
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        update_data = {
            "file_path": new_file_path,
            "content": new_content,
            "tags": new_tags,
            "updated_at": datetime.utcnow()
        }
        if new_title:
            update_data["title"] = new_title
        if new_category:
            update_data["category"] = new_category
        if new_tags:
            update_data["tags"] = new_tags
        result = collection.update_one({"_id": doc_id}, {"$set": update_data})
        if result.modified_count > 0:
            print("Документ успешно обновлен.")
        else:
            print("Документ не найден.")
        return result.modified_count
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return 0