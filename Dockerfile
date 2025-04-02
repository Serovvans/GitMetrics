### Dockerfile
FROM python:3.11

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Запуск приложения Streamlit с указанием переменных окружения
CMD ["sh", "-c", "streamlit run main_app.py"]
