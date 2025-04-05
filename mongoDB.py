from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client['database']
docs_collection = db["documents"]
tags_collection = db['tags']

const_tags = ['Расписание']
tags_collection.delete_many({})
tags_collection.insert_many([{"name": tag, "documents": []} for tag in const_tags])


def upload_document_to_db(title, content,file_path, user, category, tags=None):
    duplicate = docs_collection.find_one({
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

    documnet_id = docs_collection.insert_one(document).inserted_id
    #print(f"Документ успешно загружен. ID: {documnet_id}")

    use_flag = 0
    for tag in tags:
        if tag in const_tags:
            use_flag = 1
            tags_collection.update_one(
                {'name': tag},
                {'$push': {'documents': {'_id': documnet_id, 'file_path': file_path}}}
            )
    if use_flag == 0:
        tags_collection.insert_one({"name": tags[0], "documents": [{'_id': documnet_id, 'file_path': file_path}]})

    return documnet_id

def get_document_db(doc_id):
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        document = docs_collection.find_one({"_id": doc_id})
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
        document = docs_collection.find_one({"_id": doc_id})
        if document:
            tags = document.get("tags")
        result = docs_collection.delete_one({"_id": doc_id})
        if result.deleted_count > 0:
            print("Документ успешно удален.")
            for tag in tags:
                if tag in const_tags:
                    tags_collection.update_one(
                        {'name': tag},
                        {'$pull': {'documents': {'_id': doc_id}}}
                    )
        else:
            print("Документ не найден.")
        return result.deleted_count
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return 0

def update_document_db(doc_id,new_content,new_file_path, new_tags=None, new_title=None, new_category=None):
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
        result = docs_collection.update_one({"_id": doc_id}, {"$set": update_data})
        if result.modified_count > 0:
            print("Документ успешно обновлен.")
        else:
            print("Документ не найден.")
        return result.modified_count
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return 0