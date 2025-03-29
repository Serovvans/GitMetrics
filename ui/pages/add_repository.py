import streamlit as st
import requests
import time
import os
from ai.tools.rag_tool import initialize_vector_db_from_github
import git
from ai.graphs.code_analyse import integrated_code_analysis_graph


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

def get_latest_commit(storage_repo_path):
    """Возвращает хеш последнего коммита в локальном репозитории."""
    try:
        repo = git.Repo(storage_repo_path)
        return repo.head.commit.hexsha
    except (git.exc.InvalidGitRepositoryError, ValueError):
        return None

def run_all_analyses(repo_url):
    """Запускает все анализы для репозитория при необходимости."""
    repo_name = repo_url.split("/")[-1]
    storage_dir = f"storage/{repo_name}"
    repo_path = os.path.join(storage_dir, "repo")
    
    # Пути к файлам отчетов
    error_report_path = os.path.join(storage_dir, "error_report.json")
    complexity_report_path = os.path.join(storage_dir, "complexity_report.json")
    linters_report_path = os.path.join(storage_dir, "linters_report.json")
    
    # Проверка существования репозитория
    if os.path.exists(repo_path):
        latest_commit = get_latest_commit(repo_path)
        
        # Проверка удаленного репозитория на новый коммит
        try:
            temp_repo = git.Repo.clone_from(repo_url, "temp_repo", depth=1)
            remote_commit = temp_repo.head.commit.hexsha
            temp_repo.close()
            os.system("rm -rf temp_repo")  # Удаление временного клона
        except git.exc.GitCommandError:
            remote_commit = None
        
        if latest_commit == remote_commit and all(os.path.exists(p) for p in [error_report_path, complexity_report_path, linters_report_path]):
            return {"result": "Анализ не требуется", "storage_dir": storage_dir}
    
    # Если нет репозитория, или есть новый коммит, или нет отчетов - анализируем
    os.makedirs(storage_dir, exist_ok=True)
    if os.path.exists(repo_path):
        os.system(f"rm -rf {repo_path}")  # Удаление старого репозитория перед клонированием
    
    try:
        git.Repo.clone_from(repo_url, repo_path)
    except git.exc.GitCommandError:
        return {"result": "Ошибка при клонировании репозитория", "storage_dir": storage_dir}
    
    initialize_vector_db_from_github(repo_url)
    
    input_state = {
        "repo_url": repo_url,
        "use_llm": True,
        "output_linter_path": linters_report_path,
        "output_complexity_path": complexity_report_path,
        "output_error_path": error_report_path
    }
    result = integrated_code_analysis_graph.invoke(input_state)
    
    return {"result": result, "storage_dir": storage_dir}

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