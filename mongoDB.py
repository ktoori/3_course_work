# mongoDB.py
from pymongo import MongoClient
from datetime import datetime
import CreateTags
import pytz
import SimilarText
import Dictionaries
from fastapi import HTTPException

client = MongoClient("mongodb://localhost:27017/")
db = client['database']

docs_collection = db["documents"]
tags_collection = db['tags']
config_collection = db['config']

def load_or_init_config():
    config = config_collection.find_one({'_id': 'global_config'})
    if not config:
        config = {
            '_id': 'global_config',
            'global_tag_limit': Dictionaries.global_tag_limit,
            'other_tags': Dictionaries.other_tags,
            'content_tags_dict': Dictionaries.content_tags_dict,
            'program_tags_dict': Dictionaries.program_tags_dict,
            'doc_type_dict': Dictionaries.doc_type_dict
        }
        config_collection.insert_one(config)
    return config

config = load_or_init_config()

association_set = set()
for dic in (Dictionaries.content_tags_dict, Dictionaries.program_tags_dict, Dictionaries.doc_type_dict):
    association_set.update(dic.keys())
    for values in dic.values():
        association_set.update(values)

const_tags = list(Dictionaries.content_tags_dict.keys()) + list(Dictionaries.program_tags_dict.keys()) + list(Dictionaries.doc_type_dict.keys())

if tags_collection.count_documents({}) == 0:
    tags_collection.insert_many([{"name": tag.lower(), "documents": []} for tag in const_tags])

def upload_document_to_db(title, content,file_path, user, tags=None):
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

    moscow_tz = pytz.timezone('Europe/Moscow')
    current_time_msk = datetime.now(moscow_tz)
    formatted_time = current_time_msk.strftime('%Y-%m-%d %H:%M:%S')

    document = {
        "title": title,
        "content": content,
        "file_path": file_path,  # Путь к файлу на сервере
        "user": user,             # students, teacher
        "tags": lower_tags if lower_tags else [],
        "created_at": formatted_time
    }

    document_id = docs_collection.insert_one(document).inserted_id

    use_flag = 0
    for tag in lower_tags:
        if tag in association_set:
            use_flag = 1
            for const_tag, related_tags in Dictionaries.tag_associations.items():
                if any(SimilarText.is_similar(rt.lower(), tag, threshold=100) for rt in related_tags):
                    tags_collection.update_one(
                        {'name': const_tag},
                        {'$addToSet': {'documents': {'_id': document_id, 'file_path': file_path}}}
                    )
                    docs_collection.update_one(
                        {"_id": document_id},
                        {"$addToSet": {"tags": const_tag}}
                    )
    if use_flag == 0:
        tags_collection.insert_one({"name": tags[0], "documents": [{'_id': document_id, 'file_path': file_path}]})

    return document_id


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
        tags = []
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

def update_document_db(doc_id,new_content,new_file_path, new_tags=None, new_title=None):
    from bson import ObjectId
    try:
        doc_id = ObjectId(doc_id)
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time_msk = datetime.now(moscow_tz)
        formatted_time = current_time_msk.strftime('%Y-%m-%d %H:%M:%S')
        update_data = {
            "file_path": new_file_path,
            "content": new_content,
            "tags": new_tags,
            "updated_at": formatted_time
        }
        if new_title:
            update_data["title"] = new_title
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

    query_words = CreateTags.to_nominative_case(query).split()
    keyword_set = set(query_words)

    matched_keys = set()
    for word in query_words:
        for key, values in Dictionaries.tag_associations.items():
            if word in values:
                matched_keys.add(key)

    relevance_scores = []
    seen_ids = set()

    for key in matched_keys:
        word_docs = get_documents_by_tag(key)
        if word_docs:
            for doc_id in word_docs:
                if str(doc_id['_id']) not in seen_ids:
                    seen_ids.add(str(doc_id['_id']))
                    doc = docs_collection.find_one({"_id": doc_id['_id']})
                    doc_tags_set = set(doc['tags'])
                    matches = keyword_set.intersection(doc_tags_set)
                    date = datetime.strptime(doc['created_at'], '%Y-%m-%d %H:%M:%S')
                    if matches:
                        relevance_scores.append((str(doc_id['_id']), len(matches), date))
                        if len(relevance_scores) > 20:
                            relevance_scores.sort(key=lambda x: (x[1], x[2]))
                            relevance_scores.pop(0)

    sorted_documents = sorted(relevance_scores,  key=lambda x: (x[1], x[2]), reverse=True)
    result = []
    for case in sorted_documents:
        result.append((case[0], case[2].strftime("%d.%m.%Y %H:%M")))
    return result

def get_config():
    config = config_collection.find_one({'_id': 'global_config'})
    if not config:
        raise HTTPException(status_code=500, detail="Config not found in DB")
    return config

def update_config_field(field_name, value):
    config_collection.update_one({'_id': 'global_config'}, {'$set': {field_name: value}})

def get_dict_by_name(dict_name):
    config = get_config()
    if dict_name == "other_tags":
        return config.get('other_tags', [])
    elif dict_name == "content_tags_dict":
        return config.get('content_tags_dict', {})
    elif dict_name == "program_tags_dict":
        return config.get('program_tags_dict', {})
    elif dict_name == "doc_type_dict":
        return config.get('doc_type_dict', {})
    else:
        raise HTTPException(status_code=400, detail="Unknown dictionary name")

def set_dict_by_name(dict_name, new_value):
    if dict_name == "other_tags":
        update_config_field('other_tags', new_value)
    elif dict_name == "content_tags_dict":
        update_config_field('content_tags_dict', new_value)
    elif dict_name == "program_tags_dict":
        update_config_field('program_tags_dict', new_value)
    elif dict_name == "doc_type_dict":
        update_config_field('doc_type_dict', new_value)
    else:
        raise HTTPException(status_code=400, detail="Unknown dictionary name")

def get_global_tag_limit():
    config = get_config()
    return config.get('global_tag_limit')

def set_global_tag_limit(limit):
    update_config_field('global_tag_limit', limit)

def get_total_tag_count():
    config = get_config()
    total = 0
    # Считаем все теги из словарей и из other_tags
    for dname in ['content_tags_dict', 'program_tags_dict', 'doc_type_dict']:
        d = config.get(dname, {})
        total += len(d)
    other = config.get('other_tags', [])
    total += len(other)
    return total
