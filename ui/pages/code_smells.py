import streamlit as st
import pandas as pd
import json
import os
import re
import matplotlib.pyplot as plt

def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

def show_code_smells_page():
    st.title("Code Smells")

    if not st.session_state["repositories"][st.session_state["selected_repo_index"]]:
        st.info("Сначала выберите репозиторий в боковом меню.")
        return

    # Устанавливаем выбранную метрику
    st.session_state["selected_metric"] = "Code Smells"

    # Получаем короткое имя репозитория из URL
    selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
    repo_url = selected_repo["url"]
    repo_name = get_short_repo_name(repo_url)
    
    # Формируем путь к JSON-файлу с отчетом
    json_path = f"./storage/{repo_name}/linters_report.json"
    
    # Проверяем существование файла
    if not os.path.exists(json_path):
        st.error(f"Файл с отчетом не найден: {json_path}")
        return
    
    try:
        # Загружаем данные из JSON-файла
        with open(json_path, 'r') as file:
            linters_data = json.load(file)
        
        # Рассчитываем общее количество ошибок
        total_code_smells = sum(item['error_count'] for item in linters_data)
        
        # Выводим общую метрику Code Smells
        st.metric("Всего Code Smells", total_code_smells, 
                 help="Общее количество проблем, обнаруженных в последнем коммите")
        
        # Формируем данные для визуализации
        files = [item['file'] for item in linters_data]
        error_counts = [item['error_count'] for item in linters_data]
        
        # Создаем DataFrame для таблицы и диаграммы
        df = pd.DataFrame({
            "Файл": files,
            "Количество ошибок": error_counts
        })
        
        # Сортируем по количеству ошибок (по убыванию)
        df = df.sort_values(by="Количество ошибок", ascending=False)
        
        # Отображаем столбчатую диаграмму
        st.subheader("Распределение ошибок по файлам")
        
        st.bar_chart(df.set_index("Файл")["Количество ошибок"], use_container_width=True)
        
        # Отображаем таблицу с проблемными файлами
        st.subheader("Проблемные файлы")
        
        # При нажатии на кнопку "Подробнее о Code Smells" выбирается первый файл с ошибками
        if st.button("Подробнее о недочётах"):
            # Находим первый файл с ошибками
            for file in files:
                file_data = next((item for item in linters_data if item['file'] == file and item['error_count'] > 0), None)
                if file_data:
                    st.session_state["selected_problem_file"] = file
                    st.session_state["selected_main_tab"] = "Проблемные файлы"
                    break
        
        # Отображаем таблицу
        st.dataframe(df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Ошибка при обработке данных: {str(e)}")