import streamlit as st
import pandas as pd
import json
import os
import re
import altair as alt

def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

def show_mistakes_page():
    st.title("Ошибки")

    if not st.session_state.get("selected_repo"):
        st.info("Сначала выберите репозиторий в боковом меню.")
        return
    
    # Получение названия репозитория
    if "repositories" in st.session_state and "selected_repo_index" in st.session_state:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        repo_name = get_short_repo_name(selected_repo["url"])
    else:
        st.sidebar.warning("Репозиторий не выбран")
        return
    
    # Путь к JSON-файлу с отчетом об ошибках
    json_path = f"storage/{repo_name}/error_report.json"
    
    try:
        # Загрузка данных из JSON
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                error_data = json.load(f)
                
            # Извлечение общей информации
            repo_summary = error_data.get("repository_summary", {})
            total_errors = repo_summary.get("total_issues", 0)
            
            # Вывод общей метрики ошибок
            st.metric("Всего ошибок", total_errors, help="Общее количество ошибок в последнем коммите")
            
            # Получаем данные по файлам для столбчатой диаграммы
            file_reports = error_data.get("file_reports", {})
            
            if file_reports:
                # Создаем DataFrame для построения графика
                files_data = []
                for file_name, report in file_reports.items():
                    metrics = report.get("metrics", {})
                    files_data.append({
                        "Файл": file_name,
                        "Всего": metrics.get("total_issues", 0),  # Переименовано из "Количество"
                        "Высокий приоритет": metrics.get("high_priority", 0),
                        "Средний приоритет": metrics.get("medium_priority", 0),
                        "Низкий приоритет": metrics.get("low_priority", 0),
                        "Error Score": metrics.get("error_score", 0)
                    })
                
                files_df = pd.DataFrame(files_data)
                
                # Сортировка файлов по общему количеству ошибок
                files_df = files_df.sort_values(by="Всего", ascending=False)
                
                # Столбчатая диаграмма с ошибками по файлам
                st.subheader("Распределение ошибок по файлам")
                
                # Создаем таблицу для отображения метрик по файлам
                # Используем другое имя для value_name, чтобы избежать конфликта
                chart_df = pd.melt(files_df, 
                                   id_vars=["Файл"], 
                                   value_vars=["Высокий приоритет", "Средний приоритет", "Низкий приоритет"],
                                   var_name="Приоритет", 
                                   value_name="Число")  # Изменено с "Количество" на "Число"
                
                # Создаем столбчатую диаграмму с использованием Altair
                chart = alt.Chart(chart_df).mark_bar().encode(
                    x=alt.X('Файл:N', sort='-y', title='Файл'),
                    y=alt.Y('Число:Q', title='Количество ошибок'),  # Используем "Число" вместо "Количество"
                    color=alt.Color('Приоритет:N', scale=alt.Scale(
                        domain=['Высокий приоритет', 'Средний приоритет', 'Низкий приоритет'],
                        range=['#FF4B4B', '#FFA500', '#2ECC71']
                    )),
                    tooltip=['Файл', 'Приоритет', 'Число']  # Используем "Число" вместо "Количество"
                ).properties(
                    height=400
                ).interactive()
                
                st.altair_chart(chart, use_container_width=True)                
                # Отображаем таблицу с проблемными файлами
                st.subheader("Проблемные файлы")
                
                # Подготовка данных для отображения в таблице
                table_data = []
                
                for file_name, report in file_reports.items():
                    metrics = report.get("metrics", {})
                    issues = report.get("issues", {})
                    
                    # Формируем список ошибок для файла
                    error_descriptions = []
                    for issue_id, issue_data in issues.items():
                        error_text = issue_data.get("error", "")
                        error_descriptions.append(error_text)
                    
                    # Объединяем описания ошибок в одну строку
                    error_str = ", ".join(error_descriptions[:2])
                    if len(error_descriptions) > 2:
                        error_str += f" и еще {len(error_descriptions) - 2} ошибок"
                    
                    table_data.append({
                        "Файл": file_name,
                        "Количество": metrics.get("total_issues", 0),
                        "Ошибка": error_str
                    })
                
                # Создаем DataFrame для таблицы
                table_df = pd.DataFrame(table_data)
                table_df = table_df.sort_values(by="Количество", ascending=False)
                
                # Устанавливаем выбранную метрику – "Ошибки"
                st.session_state["selected_metric"] = "Ошибки"
                
                # При нажатии на кнопку выбирается первый файл
                if st.button("Подробнее о недочётах"):
                    if not table_df.empty:
                        st.session_state["selected_problem_file"] = table_df["Файл"].iloc[0]
                        st.session_state["selected_main_tab"] = "Проблемные файлы"
                
                # Отображаем таблицу
                st.dataframe(table_df, use_container_width=True)
            else:
                st.info("Нет данных об ошибках в файлах")
        else:
            st.error(f"Файл отчета не найден: {json_path}")
    except Exception as e:
        st.error(f"Ошибка при загрузке или обработке данных: {str(e)}")