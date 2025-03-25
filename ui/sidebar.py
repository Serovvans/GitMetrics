import streamlit as st

def draw_common_sidebar(prefix):
    st.sidebar.title("Репозитории")
    
    if "repositories" not in st.session_state:
        st.session_state["repositories"] = []
    if "selected_repo_index" not in st.session_state:
        st.session_state["selected_repo_index"] = None

    for idx, repo in enumerate(st.session_state["repositories"]):
        repo_name = repo.get("repo_name", repo.get("url", "unknown"))
        branch = repo.get("branch", "main")
        button_label = f"{repo_name} ({branch})"
        # Если этот репозиторий выбран, кнопка делается неактивной
        if idx == st.session_state.get("selected_repo_index"):
            st.sidebar.button(button_label, key=f"{prefix}_repo_{idx}", disabled=True)
        else:
            if st.sidebar.button(button_label, key=f"{prefix}_repo_{idx}"):
                st.session_state["selected_repo_index"] = idx

    st.sidebar.write("---")

def draw_problem_sidebar(prefix):
    st.sidebar.title("Проблемные файлы")
    
    # Если в session_state нет данных о проблемных файлах, создаём заглушку
    if "problem_files" not in st.session_state:
        st.session_state["problem_files"] = {
            "Сложность кода": [
                {"file_name": "utils.py", "issues": 23},
                {"file_name": "save_model.py", "issues": 18},
                {"file_name": "generate_widget.py", "issues": 17}
            ],
            "Code Smells": [
                {"file_name": "utils.py", "issues": 20},
                {"file_name": "save_model.py", "issues": 11},
                {"file_name": "generate_widget.py", "issues": 8}
            ],
            "Ошибки": [
                {"file_name": "utils.py", "issues": 23},
                {"file_name": "save_model.py", "issues": 15},
                {"file_name": "generate_widget.py", "issues": 10}
            ]
        }
    
    # Выбор метрики для отображения проблемных файлов
    metrics_options = ["Сложность кода", "Code Smells", "Ошибки"]
    if "selected_metric" not in st.session_state:
        st.session_state["selected_metric"] = metrics_options[0]
    
    selected_metric = st.sidebar.selectbox("Выберите метрику", metrics_options, 
                                             index=metrics_options.index(st.session_state["selected_metric"]), 
                                             key=f"{prefix}_metric")
    st.session_state["selected_metric"] = selected_metric

    st.sidebar.write("---")
    
    # Получаем список файлов для выбранной метрики
    files_list = st.session_state["problem_files"].get(selected_metric, [])
    
    if not files_list:
        st.sidebar.info("Нет проблемных файлов для выбранной метрики.")
    else:
        # Сортировка файлов по количеству проблем по убыванию
        sorted_files = sorted(files_list, key=lambda x: x["issues"], reverse=True)
    
        for idx, file in enumerate(sorted_files):
            file_name = file["file_name"]
            issues_count = file["issues"]
            button_label = f"{file_name} ({issues_count} проблем)"
            if st.sidebar.button(button_label, key=f"{prefix}_file_{idx}"):
                st.session_state["selected_problem_file"] = file_name
