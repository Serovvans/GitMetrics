import streamlit as st
import base64
import json
import os
import re

def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

def get_download_icon():
    # Base64 encoded download icon SVG
    download_svg = '''
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
    '''
    return f"data:image/svg+xml;base64,{base64.b64encode(download_svg.encode()).decode()}"

def create_task_card(task, task_number):
    # Priority colors
    priority_colors = {
        'high': 'rgba(255, 75, 75, 1)',    # Red
        'medium': 'rgba(255, 189, 69, 1)', # Yellow
        'low': 'rgba(9, 171, 59, 1)'       # Green
    }
    
    # Determine priority color
    priority_color = priority_colors.get(task.get('priority', 'medium'), priority_colors['medium'])
    
    st.markdown(f"""
    <div style="
        display: flex; 
        width: 100%; 
        align-items: center; 
        gap: 6px; 
        margin-bottom: 12px;
        border-radius: 12px;">
        <div style="
            display: flex; 
            align-items: center; 
            gap: 20px; 
            padding: 12px 20px; 
            flex-grow: 1; 
            background-color: #ffffff; 
            border-radius: 12px; 
            border: 4px solid #eaeaeb;">
            <div style="
                width: 24px; 
                height: 24px; 
                background-color: {priority_color}; 
                border-radius: 12px;">
            </div>
            <div style="flex-grow: 1;">
                <p style="
                    margin: 0; 
                    font-family: 'Mada', Helvetica; 
                    font-size: 20px; 
                    color: #242938;">
                    {task.get('description', 'Без описания')}
                </p>
                <div style="
                    font-family: 'Mada', Helvetica; 
                    font-size: 16px; 
                    color: #242938;">
                    {task.get('assignee', 'Не назначен')}
                </div>
            </div>
            <img src="{get_download_icon()}" style="width: 32px; height: 32px; cursor: pointer;"/>
        </div>
    </div>
    """, unsafe_allow_html=True)

def show_tasks_page():
    st.title("Задачи")
    
    # Check if a repository is selected
    if not st.session_state.get("selected_repo"):
        st.info("Сначала выберите репозиторий в боковом меню.")
        return
    
    # Get repository name
    if "repositories" in st.session_state and "selected_repo_index" in st.session_state:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        repo_name = get_short_repo_name(selected_repo["url"])
    else:
        st.warning("Репозиторий не выбран")
        return
    
    # Path to JSON file with tasks
    json_path = f"storage/{repo_name}/tasks_report.json"
    
    """
    {
        "tasks": [
            {
                "score": 1,
                "description": "Отсутствие обработки деления на 0",
                "assignee": "Serov Ivan <ivalserov@edu.hse.ru>",
                "priority": "high"
            },
            ...
        ]
    }
    """ 
    try:
        # Load tasks from JSON
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            # Sort tasks by score in descending order
            sorted_tasks = sorted(tasks_data.get('tasks', []), key=lambda x: x.get('score', 0), reverse=True)
            
            # Display tasks in pairs
            for i in range(0, len(sorted_tasks), 2):
                cols = st.columns(2)
                
                # First task in the pair
                with cols[0]:
                    create_task_card(sorted_tasks[i], i+1)
                
                # Second task in the pair (if exists)
                if i + 1 < len(sorted_tasks):
                    with cols[1]:
                        create_task_card(sorted_tasks[i+1], i+2)
        else:
            st.error(f"Файл с задачами не найден: {json_path}")
    
    except Exception as e:
        st.error(f"Ошибка при загрузке или обработке данных: {str(e)}")