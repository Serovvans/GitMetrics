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

    # Загружаем отчет о сложности кода
    complexity_report = load_complexity_report(repo_name)
    
    if complexity_report:
        # Вычисляем общую сложность кода по всем файлам
        total_complexity = sum(file_info["total_complexity"] for file_info in complexity_report.values())
        st.metric("Общая сложность кода", total_complexity, help="Сумма сложности всех файлов в репозитории")
        
        # Создаем DataFrame для отображения метрик по файлам
        file_metrics = []
        for file_path, file_info in complexity_report.items():
            file_metrics.append({
                "Файл": file_path,
                "Общая сложность": file_info["total_complexity"],
                "Средняя сложность": round(file_info["average_complexity"], 2),
                "Количество проблемных фрагментов": len(file_info["fragments"])
            })
        
        df = pd.DataFrame(file_metrics)
        
        # Сортируем по общей сложности (от большей к меньшей)
        df = df.sort_values(by="Общая сложность", ascending=False)
        
        # Отображаем столбчатую диаграмму вместо линейного графика
        st.subheader("Метрики сложности по файлам")
        
        # Отбираем только файлы с ненулевой сложностью для диаграммы
        chart_df = df[df["Общая сложность"] > 0]
        
        if not chart_df.empty:
            # Создаем столбчатую диаграмму
            st.bar_chart(
                chart_df.set_index("Файл")["Общая сложность"],
                use_container_width=True
            )
        else:
            st.info("Нет файлов с ненулевой сложностью")
        
        # Подготовка данных для таблицы проблемных файлов
        st.subheader("Проблемные файлы")
        
        # Создаем список файлов, содержащих проблемные фрагменты
        problem_files = []
        for file_path, file_info in complexity_report.items():
            if file_info["fragments"]:
                # Собираем типы ошибок из фрагментов
                error_descriptions = []
                for fragment in file_info["fragments"]:
                    if "description" in fragment:
                        # Берем первое предложение из описания для краткости
                        first_sentence = fragment["description"].split(".")[0] + "."
                        if first_sentence not in error_descriptions:
                            error_descriptions.append(first_sentence)
                
                problem_files.append({
                    "Файл": file_path,
                    "Количество": len(file_info["fragments"]),
                    "Ошибка": ", ".join(error_descriptions) if error_descriptions else "Высокая цикломатическая сложность"
                })
        
        if problem_files:
            problem_df = pd.DataFrame(problem_files)
            problem_df = problem_df.sort_values(by="Количество", ascending=False)
            
            # При нажатии на кнопку выбирается первый файл
            if st.button("Подробнее о недочётах") and not problem_df.empty:
                st.session_state["selected_problem_file"] = problem_df["Файл"].iloc[0]
                st.session_state["selected_main_tab"] = "Проблемные файлы"
            
            # Отображаем таблицу с проблемными файлами
            st.dataframe(problem_df, use_container_width=True)
        else:
            st.info("Проблемных файлов не обнаружено")
    else:
        # Если отчет не найден, показываем сообщение об ошибке
        st.error("Не удалось загрузить отчет о сложности кода. Убедитесь, что он существует в директории storage/{repo_name}/complexity_report.json")