<h3 align="center"> Установка и запуск: </h3>

1. Скачать репозиторий
2. Убедитесь, что виртуальное окружение активировано:
venv\Scripts\activate
3. pip install -r requirements.txt - установить все зависимости
4. Рабочая версия python: 3.11 - 3.12. Если возникнет конфликт с numpy:  pip install numpy==1.26.4
5. Запуск программы в терминале: uvicorn BaseMain:app --reload
6. Документация Swagger: http://127.0.0.1:8000/docs

<h3 align="center"> API-методы: </h3>
POST /upload– загрузка документа в основное хранилище
(доступно для администратора).

DELETE /delete_document – удаление документа (доступно для
администратора).

PUT /update_document– редактирование документа (доступно для
администратора).

GET /search – релевантный поиск.

POST /generate_tags – генерация тегов.

GET /get_structure_information – информация о структуре тегов.

POST /add_tagиDELETE /delete_tags – работа с тегами.

POST / set_limit – установка лимита по количеству тегов.

POST /upload_for_moderation – загрузка документа на модерацию
для пользователей.

GET /moderation/documents–получение списока документов на
модерации (доступно для администратора)

POST /moderation/approve – одобрение документа (доступно для
администратора)

POST /moderation/reject - отклонение документа (доступно для
администратора)