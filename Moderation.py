from pymongo import MongoClient
from datetime import datetime
import pytz

import mongoDB

client = MongoClient("mongodb://localhost:27017/")
db = client['database']
moderation_collection = db["moderation_documents"]

def upload_document_to_moderation(title, content, file_path, user, tags=None):
    lower_tags = [tag.lower() for tag in tags] if tags else []

    moscow_tz = pytz.timezone('Europe/Moscow')
    current_time_msk = datetime.now(moscow_tz)
    formatted_time = current_time_msk.strftime('%Y-%m-%d %H:%M:%S')

    document = {
        "title": title,
        "content": content,
        "file_path": file_path,
        "user": user,
        "tags": lower_tags,
        "status": "pending",  # pending, approved, rejected
        "created_at": formatted_time,
        "moderated_at": None,
        "moderator": None,
        "final_tags": None
    }

    return moderation_collection.insert_one(document).inserted_id


def get_moderation_documents(status=None):
    query = {}
    if status:
        query["status"] = status
    return list(moderation_collection.find(query))


def get_moderation_document(doc_id):
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        return moderation_collection.find_one({"_id": doc_id})
    except:
        return None


def approve_document(doc_id, moderator, final_tags=None):
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)

        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time_msk = datetime.now(moscow_tz)
        formatted_time = current_time_msk.strftime('%Y-%m-%d %H:%M:%S')

        doc = moderation_collection.find_one({"_id": doc_id})
        if not doc:
            return False
        if doc["status"]!="pending":
            return False
        result = mongoDB.upload_document_to_db(
            title=doc["title"],
            content=doc["content"],
            file_path=doc["file_path"],
            user=doc["user"],
            tags=final_tags if final_tags else doc["tags"]
        )

        if result:
            moderation_collection.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "status": "approved",
                        "moderated_at": formatted_time,
                        "moderator": moderator,
                        "final_tags": final_tags if final_tags else doc["tags"]
                    }
                }
            )
            return True
        return False
    except Exception as e:
        return False


def reject_document(doc_id, moderator):
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time_msk = datetime.now(moscow_tz)
        formatted_time = current_time_msk.strftime('%Y-%m-%d %H:%M:%S')
        doc = moderation_collection.find_one({"_id": doc_id})
        if not doc:
            return False
        if doc["status"] != "pending":
            return False
        update_data = {
            "status": "rejected",
            "moderated_at": formatted_time,
            "moderator": moderator
        }

        result = moderation_collection.update_one(
            {"_id": doc_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error rejecting document: {str(e)}")
        return False