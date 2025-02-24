from pymongo import MongoClient
from datetime import datetime

# Подключение к MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client['database']
collection = db["documents"]

def upload_document_to_db(title, content, user, category, tags=None):
    duplicate = collection.find_one({
        "$or": [
            {"title": title},
            {"content": content}
        ]
    })

    if duplicate:
        print(f"Документ уже существует в базе данных: {title}")
        return None

    document = {
        "title": title,
        "content": content,
        "user": user,             #students, teacher
        "category": category,     #schedule, template, manual, instructions
        "tags": tags if tags else [],
        "created_at": datetime.utcnow()
    }

    result = collection.insert_one(document)
    print(f"Документ успешно загружен. ID: {result.inserted_id}")
    return result.inserted_id


def get_document_db(doc_id):
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


def update_document_db(doc_id, new_content, new_tags, new_title=None, new_category=None):
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        update_data = {
            "content": new_content,
            "tags": new_tags,
            "updated_at": datetime.utcnow()
        }
        if new_title:
            update_data["title"] = new_title
        if new_category:
            update_data["category"] = new_category
        result = collection.update_one({"_id": doc_id}, {"$set": update_data})
        if result.modified_count > 0:
            print("Документ успешно обновлен.")
        else:
            print("Документ не найден.")
        return result.modified_count
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return 0