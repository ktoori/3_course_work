from pymongo import MongoClient
from datetime import datetime
import CreateTags2

client = MongoClient("mongodb://localhost:27017/")
db = client['database']
docs_collection = db["documents"]
tags_collection = db['tags']

const_tags = ['Расписание', 'ПИ', 'ПМИ', 'Курсовая работа', '3 курс', 'Заявление']
const_tags = [tag.lower() for tag in const_tags]

if tags_collection.count_documents({}) == 0:
    tags_collection.insert_many([{"name": tag.lower(), "documents": []} for tag in const_tags])


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

    lower_tags = [tag.lower() for tag in tags]

    document = {
        "title": title,
        "content": content,
        "file_path": file_path,  # Путь к файлу на сервере
        "user": user,             # students, teacher
        "category": category,     # schedule, template, manual, instructions
        "tags": lower_tags if lower_tags else [],
        "created_at": datetime.utcnow()
    }

    documnet_id = docs_collection.insert_one(document).inserted_id

    use_flag = 0
    for tag in lower_tags:
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

def get_documents_by_tag(tag_name):
    tag = tags_collection.find_one({"name": tag_name}, {"documents": 1})
    if tag:
        return tag.get("documents", [])
    else:
        return None


def search_by_tag(query):

    query_words = CreateTags2.to_nominative_case(query).split()
    keyword_set = set(query_words)
    relevance_scores = []
    seen_ids = set()

    for word in query_words:
        word_docs = get_documents_by_tag(word)
        if word_docs:
            for doc_id in word_docs:
                if str(doc_id) not in seen_ids:
                    seen_ids.add(str(doc_id))
                else:
                    continue
                doc = docs_collection.find_one({"_id": doc_id['_id']})
                doc_tags_set = set(doc['tags'])
                matches = keyword_set.intersection(doc_tags_set)
                relevance_scores.append((str(doc_id['_id']), len(matches)))

    sorted_documents = sorted(relevance_scores, key=lambda x: x[1], reverse=True)
    result = []
    for case in sorted_documents:
        result.append(case[0])
    return result