import streamlit as st
import pandas as pd

def show_code_smells_page():
    st.title("Code Smells")

    if not st.session_state.get("selected_repo"):
        st.info("Сначала выберите репозиторий в боковом меню.")
        return

    # Устанавливаем выбранную метрику
    st.session_state["selected_metric"] = "Code Smells"

    # Вывод общей метрики Code Smells
    total_code_smells = 60  # заглушка
    st.metric("Всего Code Smells", total_code_smells, help="Общее количество проблем, обнаруженных в последнем коммите")

    # График (заглушка)
    st.line_chart({
        "commits": [1, 2, 3, 4, 5],
        "code_smells": [40, 50, 60, 55, 60]
    })

    st.subheader("Проблемные файлы")
    
    # Данные для таблицы (заглушка)
    data = {
        "Файл": ["utils.py", "save_model.py", "generate_widget.py"],
        "Количество": [20, 11, 8],
        "Ошибка": ["Ошибка 1", "Ошибка 1", "Ошибка 1, Ошибка 2"]
    }
    df = pd.DataFrame(data)
    
    # При нажатии на кнопку "Подробнее о Code Smells" выбирается первый файл
    if st.button("Подробнее о недочётах"):
        st.session_state["selected_problem_file"] = df["Файл"].iloc[0]
        st.session_state["selected_main_tab"] = "Проблемные файлы"
    
    # Отображаем таблицу с проблемными файлами
    st.dataframe(df, use_container_width=True)
