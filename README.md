## Требования

- Docker
- Docker Compose

## Настройка .env файла

Создайте файл `.env` в корневой директории проекта и добавьте в него ваши переменные окружения:

```
# Пример .env файла
GROQ_API_KEY=
HF_TOKEN=
LANGSMITH_API_KEY=
```

## Установка модели векторизации

Необходимо перед запуском установить модель.
Для этого выполните команду:
```bash
python download_model.py
```

## Запуск приложения

1. Создайте файл `.env` с вашими переменными окружения
2. Убедитесь, что в файле `requirements.txt` указаны все необходимые зависимости, включая `streamlit`
3. Запустите приложение с помощью Docker Compose:


**Не забудьте включить VPN для работы Groq**

```bash
docker-compose up --build
```

Приложение будет доступно по адресу: `http://localhost:8501`

## Остановка приложения

Для остановки приложения используйте:

```bash
docker-compose down
```

## Сторонние ресурсы
emb_model - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (HuggingFace)