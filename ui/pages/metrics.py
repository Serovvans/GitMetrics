import streamlit as st
import re
import json
import os

def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

def load_json(filepath: str):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    return None

def calculate_average_complexity(complexity_data):
    if not complexity_data:
        return "N/A"
    complexities = [file_data["average_complexity"] for file_data in complexity_data.values()]
    return round(sum(complexities) / len(complexities), 2) if complexities else "N/A"

def get_error_score(error_data):
    return error_data.get("repository_summary", {}).get("total_issues", "N/A") if error_data else "N/A"

def show_metrics_page():
    st.title("📊 Метрики")

    if "repositories" not in st.session_state:
        st.session_state["repositories"] = []
    if "selected_repo_index" not in st.session_state:
        st.session_state["selected_repo_index"] = None

    if st.session_state["selected_repo_index"] is not None and st.session_state["repositories"]:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        short_name = get_short_repo_name(selected_repo["url"])
        st.caption(f"Текущий репозиторий: {short_name} ({selected_repo['branch']})")
    else:
        st.error("Репозиторий не выбран.")
        return
    
    complexity_path = f"storage/{short_name}/complexity_report.json"
    error_path = f"storage/{short_name}/error_report.json"

    complexity_data = load_json(complexity_path)
    error_data = load_json(error_path)

    avg_complexity = calculate_average_complexity(complexity_data) if complexity_data else "N/A"
    error_score = get_error_score(error_data) if error_data else "N/A"
    
    st.markdown("""
        <style>
            .card {
                border-radius: 10px;
                padding: 20px;
                box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                width: 350px;
                margin: 20px;
                transition: transform 0.2s;
            }
            .card:hover {
                transform: scale(1.05);
            }
            .complexity { background-color: #E0F7FA; }
            .errors { background-color: #FFEBEE; }
            .metric {
                font-size: 40px;
                font-weight: bold;
                color: #FF5252;
            }
            .circle {
                font-size: 50px;
                font-weight: bold;
                color: #26C6DA;
            }
            .card p {
                margin: 0;
            }
        </style>
    """, unsafe_allow_html=True)

    cols = st.columns(3)

    with cols[0]:
        st.markdown(
            f'<div class="card complexity"><p>Сложность кода</p><div class="circle">{avg_complexity}</div></div>',
            unsafe_allow_html=True
        )
    
    with cols[1]:
        st.markdown(
            '<div class="card code_smells">'
            '<h3>Code Smells</h3>'
            '<div class="circle">25%</div>'
            '<p>Наши специальные линтеры говорят...</p>'
            '</div>',
            unsafe_allow_html=True
        )
    with cols[2]:
        st.markdown(
            '<div class="card errors">'
            '<h3>Ошибки</h3>'
            f'<div class="metric">{error_score}</div>'
            '<p>В последнем коммите найдено ошибок</p>'
            '</div>',
            unsafe_allow_html=True
        )
