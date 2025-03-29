import streamlit as st
import pandas as pd
import json
import os
import re

def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

def load_complexity_report(repo_name):
    """Load the complexity report JSON file for the selected repository."""
    file_path = f"storage/{repo_name}/complexity_report.json"
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        else:
            st.warning(f"Файл отчета не найден: {file_path}")
            return None
    except Exception as e:
        st.error(f"Ошибка при загрузке отчета: {e}")
        return None

def show_complexity_page():
    st.title("Сложность кода")

    if not st.session_state.get("selected_repo"):
        st.info("Сначала выберите репозиторий в боковом меню.")
        return

    # Получаем название репозитория
    if "repositories" in st.session_state and "selected_repo_index" in st.session_state:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        short_name = get_short_repo_name(selected_repo["url"])
        repo_name = short_name
    else:
        st.sidebar.warning("Репозиторий не выбран")
        return

    # Устанавливаем выбранную метрику
    st.session_state["selected_metric"] = "Сложность кода"

    try:
        linters_data = load_complexity_report(repo_name)
        
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
        
        # Фильтруем файлы с ненулевым количеством ошибок
        chart_df = df[df["Количество ошибок"] > 0]
        
        if not chart_df.empty:
            # Создаем столбчатую диаграмму
            st.bar_chart(
                chart_df.set_index("Файл")["Количество ошибок"],
                use_container_width=True
            )
        else:
            st.info("Нет файлов с ошибками")
        
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
        st.dataframe(df[["Файл", "Количество ошибок"]], use_container_width=True)
        
    except Exception as e:
        st.error(f"Ошибка при обработке данных: {str(e)}")