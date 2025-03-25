import streamlit as st
import re
import os
from ai.graphs.custom_criteria_graph import custom_criteria_graph

def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

def generate_report(repo_url, criteria):
    repo_name = get_short_repo_name(repo_url)
    folder_path = f"storage/{repo_name}"
    os.makedirs(folder_path, exist_ok=True)
    
    report = custom_criteria_graph.invoke({
        "repo_url": repo_url,
        "criteria": criteria,
        "folder_path": folder_path
    }, {"recursion_limit": 500})
    
    report_path = os.path.join(folder_path, "summary_report.md")
    
    return report_path

def show_custom_page():
    st.title("Кастомные метрики")
    
    if "selected_repo" not in st.session_state:
        st.session_state.selected_repo = None
    if "report_path" not in st.session_state:
        st.session_state.report_path = None
    
    if not st.session_state.get("selected_repo"):
        st.info("Сначала выберите репозиторий в боковом меню.")
        return
    
    repo_url = st.session_state["selected_repo"]["url"]
    st.write(f"Текущий репозиторий: **{get_short_repo_name(repo_url)}**")
    
    criteria = st.text_input("Введите критерий анализа", "Обработка крайних случаев")
    if st.button("Сгенерировать отчет"):
        with st.spinner("Создание отчета..."):
            report_path = generate_report(repo_url, criteria)
            st.session_state.report_path = report_path
        st.success("Отчет создан!")
    
    if st.session_state.report_path:
        with open(st.session_state.report_path, "r", encoding="utf-8") as file:
            report_content = file.read()
            st.text_area("Содержимое отчета", report_content, height=300)
            
            with open(st.session_state.report_path, "rb") as download_file:
                st.download_button(
                    label="Скачать отчет",
                    data=download_file,
                    file_name="report.md",
                    mime="text/markdown"
                )
