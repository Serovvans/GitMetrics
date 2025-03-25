import streamlit as st
import requests
import time
import os
from ai.graphs.error_analysis_graph import error_analysis_graph
from ai.graphs.complexity_graph import complexity_analysis_graph
from ai.tools.rag_tool import initialize_vector_db_from_github
import git

def is_private_repository(repo_url):
    """Проверяет, является ли репозиторий приватным."""
    try:
        repo_parts = repo_url.rstrip("/").split("/")
        if len(repo_parts) < 5:
            return True  # Некорректный URL считается приватным
        
        user, repo = repo_parts[-2], repo_parts[-1]
        api_url = f"https://api.github.com/repos/{user}/{repo}"
        
        response = requests.get(api_url)
        return response.status_code == 404  # 404 означает, что репозиторий приватный
    except:
        return True  # Если ошибка сети или формат неверный, считаем его приватным

def get_branches(repo_url):
    """Получает список веток репозитория."""
    try:
        repo_parts = repo_url.rstrip("/").split("/")
        user, repo = repo_parts[-2], repo_parts[-1]
        api_url = f"https://api.github.com/repos/{user}/{repo}/branches"
        
        # Получение списка веток с обработкой ошибок
        response = requests.get(api_url)
        
        # Логируем статус ответа
        if response.status_code == 200:
            return [branch["name"] for branch in response.json()]
        else:
            st.error(f"Ошибка при получении веток: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"Ошибка при выполнении запроса: {str(e)}")
        return []

def run_all_analyses(repo_url):
    """Запускает все анализы для репозитория."""
    # Извлекаем имя репозитория из URL
    repo_name = repo_url.split("/")[-1]
    
    # Создаем директорию для хранения результатов
    storage_dir = f"storage/{repo_name}"
    os.makedirs(storage_dir, exist_ok=True)
    
    try:
        git.Repo.clone_from(repo_url, storage_dir + "/repo/")
    except git.exc.GitCommandError:
        pass
    initialize_vector_db_from_github(repo_url)
    
    # Пути к файлам отчетов
    error_report_path = f"{storage_dir}/error_report.json"
    complexity_report_path = f"{storage_dir}/complexity_report.json"
    
    # Запуск анализа ошибок
    error_result = error_analysis_graph.invoke({
        "repo_url": repo_url,
        "output_file_path": error_report_path,
    }, {"recursion_limit": 500})
    
    # Запуск анализа сложности
    complexity_result = complexity_analysis_graph.invoke({
        "repo_url": repo_url,
        "output_json": complexity_report_path,
        "use_llm": True
    }, {"recursion_limit": 500})
    
    
    return {
        "error_analysis": error_result,
        "complexity_analysis": complexity_result,
        "storage_dir": storage_dir
    }

def show_add_repository_page():
    st.title("Добавить репозиторий")
    
    if "repositories" not in st.session_state:
        st.session_state["repositories"] = []
    
    repo_link = st.text_input("Ссылка на репозиторий", key="add_repo_link", value="")
    
    if repo_link.strip():
        if is_private_repository(repo_link):
            st.error("Ошибка: репозиторий приватный, доступ не получен.")
        else:
            branches = get_branches(repo_link)
            if not branches:
                st.error("Ошибка: невозможно получить список веток.")
                return
            
            branch = st.selectbox("Ветка для анализа", branches, key="add_repo_branch")
            add_repo_btn = st.button("Добавить репозиторий")
            
            if add_repo_btn:
                short_name = repo_link.split("/")[-1]
                st.session_state["repositories"].append({
                    "repo_name": short_name,
                    "branch": branch,
                    "url": repo_link
                })
                st.session_state["selected_repo_index"] = len(st.session_state["repositories"]) - 1
                st.success(f"Репозиторий {short_name} успешно добавлен!")
                st.session_state["analysis_ready"] = True
    
    if st.session_state.get("analysis_ready"):
        analyze_btn = st.button("Анализ")
        if analyze_btn:
            with st.spinner("Производим анализ..."):
                # Получаем URL текущего выбранного репозитория
                current_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
                repo_url = current_repo["url"]
                
                # Запускаем все анализы
                analysis_results = run_all_analyses(repo_url)
                
                # Сохраняем результаты в session_state для доступа на других вкладках
                if "analysis_results" not in st.session_state:
                    st.session_state["analysis_results"] = {}
                
                st.session_state["analysis_results"][repo_url] = analysis_results
                st.session_state["analysis_completed"] = True
            
            # Переходим на вкладку "Метрики"
            st.session_state["selected_main_tab"] = "Метрики"
            st.rerun()
    else:
        st.button("Анализ", disabled=True)