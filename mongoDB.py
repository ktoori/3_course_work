from pymongo import MongoClient
from datetime import datetime
import pytz
from fastapi import HTTPException

import Dictionaries
import SimilarText

client = MongoClient("mongodb://localhost:27017/")
db = client['database']

docs_collection = db["documents"]
tags_collection = db['tags']
config_collection = db['config']


class TagStructure:
    """
    Класс функций по изменению структуры тегов
    """

    def __init__(self):
        self.init_cofig()

        self.association_set = set()
        for dic in (self.get_dict_by_name("content_tags_dict"), self.get_dict_by_name("program_tags_dict"),
                    self.get_dict_by_name("doc_type_dict")):
            self.association_set.update(dic.keys())
            for values in dic.values():
                self.association_set.update(values)
        self.const_tags = list(self.get_dict_by_name("content_tags_dict").keys()) + list(
            self.get_dict_by_name("program_tags_dict").keys()) + list(self.get_dict_by_name("doc_type_dict").keys())
        if tags_collection.count_documents({}) == 0:
            tags_collection.insert_many([{"name": tag.lower(), "documents": []} for tag in self.const_tags])
        self.tag_associations = self.get_dict_by_name("content_tags_dict") | self.get_dict_by_name("program_tags_dict") | self.get_dict_by_name("doc_type_dict")


    def init_cofig(self):
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


    def get_config(self):
        config = config_collection.find_one({'_id': 'global_config'})
        if not config:
            raise HTTPException(status_code=500, detail="config not found in DB")
        return config


    def sync_tags_collection(self):
        """
        Оюновляет коллекцию тегов в базе данных
        :return: возвращает результат работы
        """
        config = self.get_config()
        current_tags = set(list(config.get("content_tags_dict", {}).keys()) + list(config.get("program_tags_dict", {}).keys()) + list(config.get("doc_type_dict", {}).keys()))
        existing_tags_cursor = tags_collection.find({}, {"name": 1, "_id": 0})
        existing_tags = set(doc["name"] for doc in existing_tags_cursor)

        tags_to_add = current_tags - existing_tags
        tags_to_remove = existing_tags - current_tags

        if tags_to_add:
            for tag in tags_to_add:
                tags_collection.update_one(
                    {"name": tag.lower()},
                    {"$setOnInsert": {"documents": []}},
                    upsert = True
                )

        if tags_to_remove:
            tags_collection.delete_many({"name": {"$in": list(tags_to_remove)}})
        return {
            "tags_added": list(tags_to_add),
            "tags_removed": list(tags_to_remove)
        }


    def update_config_field(self, field_name, value):
        config_collection.update_one({'_id': 'global_config'}, {'$set': {field_name: value}})


    def get_dict_by_name(self, dict_name):
        """
        Возвращает значения словаря по названию
        :param dict_name: название словаря
        :return: массив или словарь значений
        """
        config = self.get_config()
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


    def set_dict_by_name(self, dict_name, new_value):
        """
        Обновить словарь тегов
        :param dict_name: название словаря
        :param new_value: новые значения
        :return:
        """
        if dict_name == "other_tags":
            self.update_config_field('other_tags', new_value)
        elif dict_name == "content_tags_dict":
            self.update_config_field('content_tags_dict', new_value)
        elif dict_name == "program_tags_dict":
            self.update_config_field('program_tags_dict', new_value)
        elif dict_name == "doc_type_dict":
            self.update_config_field('doc_type_dict', new_value)
        else:
            raise HTTPException(status_code=400, detail="Unknown dictionary name")


    def get_global_tag_limit(self):
        """
        Получить лимит тегов
        :return: значение лимита
        """
        config = self.get_config()
        return  config.get('global_tag_limit')


    def set_global_tag_limit(self, limit):
        """
        Установить лимит тегов
        :param limit: значение для лимита
        """
        self.update_config_field('global_tag_limit', limit)


    def get_total_tag_count(self):
        """
        Получить количество всех тегов
        :return: количество тегов
        """
        config = self.get_config()
        total = 0

        for dict_name in ['content_tags_dict', 'program_tags_dict', 'doc_type_dict']:
            dict = config.get(dict_name, {})
            total += len(dict)
        tag_arr = config.get('other_tags', [])
        total += len(tag_arr)

        return total


    def get_documents_by_tag(self, tag_name):
        """
        Получить список документов, связанных с тегом
        :param tag_name: тег
        :return: массив ID документов
        """
        tag = tags_collection.find_one({"name": tag_name}, {"documents": 1})
        if tag:
            return tag.get("documents", [])
        else:
            return None


class SearchFunction:
    """
    Класс функций для поиска по тегам
    """

    def search_by_tag(self, query):
        """
        Поиск документа по запросу
        :param query: запрос
        :return: массив релевантных документов
        """
        from CreateTags import TagGenerate
        tag_methods = TagGenerate()
        tag_structure = TagStructure()
        query_words = tag_methods.to_nominative_case(query).split()
        keyword_set = set(query_words)

        tag_associations = (tag_structure.get_dict_by_name("content_tags_dict") |
                            tag_structure.get_dict_by_name("program_tags_dict") |
                            tag_structure.get_dict_by_name("doc_type_dict"))

        matched_keys = set()
        for word in query_words:
            for key, values in tag_associations.items():
                if word in values:
                    matched_keys.add(key)

        relevance_score = []
        seen_ids = set()

        for key in matched_keys:
            word_docs = tag_structure.get_documents_by_tag(key)
            if word_docs:
                for doc_id in word_docs:
                    if str(doc_id['_id']) not in seen_ids:
                        seen_ids.add(str(doc_id['_id']))
                        doc = docs_collection.find_one({"_id":doc_id['_id']})
                        doc_tags_set = set(doc['tags'])
                        matches = keyword_set.intersection(doc_tags_set)
                        date = datetime.strptime(doc['created_at'], '%Y-%m-%d %H:%M:%S')
                        if matches:
                            relevance_score.append((str(doc_id['_id']), len(matches), date))
                            if len(relevance_score) > 20:
                                relevance_score.sort(key=lambda x: (x[1], x[2]))
                                relevance_score.pop(0)

        sorted_documents = sorted(relevance_score, key=lambda x: (x[1], x[2]), reverse=True)
        result = []
        for case in sorted_documents:
            result.append((case[0], case[2].strftime("%d.%m.%Y %H:%M")))
        return result


class TagCollectionChange:
    """
    Класс функций по обновлению коллекции tags при добавлении, удалении и редактировании документа в documents
    """

    def upload_document(self, document_id, lower_tags, file_path):
        """
        Функция связывающая доумент и тег при добавлении документа в базу данных
        :param document_id: ID добавленного документа
        :param lower_tags: массив тегов документа
        :param file_path: путь хранения документа
        """

        tag_structure = TagStructure()
        tag_associations = tag_structure.tag_associations
        association_set = tag_structure.association_set
        use_flag = 0

        for tag in lower_tags:
            if tag in association_set:
                use_flag = 1
                for const_tag, sim_tags in tag_associations.items():
                    if any(SimilarText.is_similar(st.lower(), tag, threshold=95) for st in sim_tags):
                        tags_collection.update_one(
                            {'name': const_tag},
                            {'$addToSet': {'documents': {'_id': document_id, 'file_path': file_path}}}
                        )
                        docs_collection.update_one(
                            {"_id": document_id},
                            {"$addToSet": {"tags": const_tag}}
                        )

        if use_flag == 0:
            raise HTTPException(status_code=400, detail="Tags are not found")


    def delete_document(self, result, doc_id, tags):
        """
        Удаляет связь тегов с удаляемым документом
        :param result: результат удаления документа из documents
        :param doc_id: ID удаляемого документа
        :param tags: массив тегов документа
        """

        tag_structure = TagStructure()
        const_tags = tag_structure.const_tags

        if result.deleted_count > 0:
            for tag in tags:
                if tag in const_tags:
                    tags_collection.update_one(
                        {'name': tag},
                        {'$pull': {'documents': {'_id': doc_id}}}
                    )
        else:
            HTTPException(status_code=400, detail="Document is not found")


    def update_document(self, doc_id, old_tags, new_tags, file_path):
        """
        Функция обновляет связь документа с тегами, если список тегов был изменен
        :param doc_id: ID измененного документа
        :param old_tags: старые теги
        :param new_tags: новые теги
        :param file_path: путь к хранению документа
        """

        tag_structure = TagStructure()
        tag_associations = tag_structure.tag_associations
        association_set = tag_structure.association_set
        const_tags = tag_structure.const_tags
        use_flag = 0

        for tag in old_tags:
            if tag in const_tags:
                tags_collection.update_one(
                    {'name': tag},
                    {'$pull': {'documnets': {'_id': doc_id}}}
                )

        for tag in new_tags:
            if tag in association_set:
                use_flag = 1
                for const_tag, sim_tags in tag_associations.items():
                    if any(SimilarText.is_similar(st.lower(), tag, threshold=80) for st in sim_tags):
                        tags_collection.update_one(
                            {'name': const_tag},
                            {'$addToSet': {'documents': {'_id': doc_id, 'file_path': file_path}}}
                        )
                        docs_collection.update_one(
                            {"_id": doc_id},
                            {"$addToSet": {"tags": const_tag}}
                        )

        if use_flag == 0:
            raise HTTPException(status_code=400, detail="Tags are not found")


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

    tags_coll_change = TagCollectionChange()
    tags_coll_change.upload_document(document_id, lower_tags, file_path)

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

        tags_coll_change = TagCollectionChange()
        tags_coll_change.delete_document(result, doc_id, tags)

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

        document = docs_collection.find_one({"_id": doc_id})
        old_tags = document.get("tags")

        result = docs_collection.update_one({"_id": doc_id}, {"$set": update_data})

        tags_coll_change = TagCollectionChange()
        if new_tags:
            tags_coll_change.update_document(doc_id, old_tags, new_tags, new_file_path)

        if result.modified_count > 0:
            print("Документ успешно обновлен.")
        else:
            print("Документ не найден.")
        return result.modified_count
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return 0