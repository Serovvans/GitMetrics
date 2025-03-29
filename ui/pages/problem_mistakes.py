import streamlit as st
import json
import os
from streamlit.components.v1 import html
import re


def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"


def load_repository_data(repo_name, selected_metric):
    """
    Load appropriate report data based on selected metric.
    
    Args:
        repo_name (str): Name of the repository being analyzed
        selected_metric (str): Selected metric type ("Сложность кода", "Ошибки", or "Code Smells")
        
    Returns:
        dict: Report data
    """
    report_path = ""
    if selected_metric == "Сложность кода":
        report_path = os.path.join("storage", repo_name, "complexity_report.json")
    elif selected_metric == "Ошибки":
        report_path = os.path.join("storage", repo_name, "error_report.json")
    elif selected_metric == "Code Smells":
        report_path = os.path.join("storage", repo_name, "linters_report.json")
    
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Файл отчета не найден: {report_path}")
        return {}
    except json.JSONDecodeError:
        st.error(f"Ошибка при чтении JSON из файла: {report_path}")
        return {}


def load_source_file(repo_name, file_path):
    """
    Load source code from a file in the repository.
    
    Args:
        repo_name (str): Name of the repository
        file_path (str): Path to the file relative to repository root
        
    Returns:
        str: Content of the file
    """
    full_path = os.path.join("storage", repo_name, "repo", file_path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"Файл с исходным кодом не найден: {full_path}")
        return ""
    except Exception as e:
        st.error(f"Ошибка при чтении файла с исходным кодом: {str(e)}")
        return ""


def extract_base_filename(full_path):
    """Extract the base filename from a full path."""
    return os.path.basename(full_path)


def clean_fixed_code(fixed_code):
    """
    Remove the prefix from fixed code.
    
    Args:
        fixed_code (str): Code with prefix
        
    Returns:
        str: Code without prefix
    """
    if not fixed_code:
        return ""
    
    # Remove prefix pattern: """File filename. Add your description here."""
    pattern = r'^"""File [^.]+\. Add your description here\."""\n\n?'
    return re.sub(pattern, '', fixed_code)


def draw_problem_sidebar(prefix):
    """
    Draw the sidebar with problem files.
    
    Args:
        prefix (str): Prefix for unique keys
    """
    st.sidebar.title("Проблемные файлы")
    
    # Выбор метрики для отображения проблемных файлов
    metrics_options = ["Сложность кода", "Ошибки", "Code Smells"]
    if "selected_metric" not in st.session_state:
        st.session_state["selected_metric"] = metrics_options[0]
    
    selected_metric = st.sidebar.selectbox("Выберите метрику", metrics_options, 
                                          index=metrics_options.index(st.session_state["selected_metric"]), 
                                          key=f"{prefix}_metric")
    st.session_state["selected_metric"] = selected_metric

    st.sidebar.write("---")
    
    if "repositories" in st.session_state and "selected_repo_index" in st.session_state:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        short_name = get_short_repo_name(selected_repo["url"])
        repo_name = short_name
    else:
        st.sidebar.warning("Репозиторий не выбран")
        return
    
    # Загрузить данные отчета в зависимости от выбранной метрики
    report_data = load_repository_data(repo_name, selected_metric)
    
    # Подготовка списка файлов для отображения в сайдбаре
    files_list = []
    
    if selected_metric == "Сложность кода":
        for file_path, file_data in report_data.items():
            # Пропустить файлы без фрагментов с проблемами
            if len(file_data.get("fragments", [])) > 0:
                base_filename = extract_base_filename(file_path)
                files_list.append({
                    "file_name": base_filename,
                    "file_path": file_path,  # Используем относительный путь
                    "issues": len(file_data.get("fragments", [])),
                    "complexity": file_data.get("total_complexity", 0)
                })
    elif selected_metric == "Ошибки":
        if "file_reports" in report_data:
            for file_path, file_data in report_data["file_reports"].items():
                files_list.append({
                    "file_name": file_path,
                    "file_path": file_path,  # Используем относительный путь
                    "issues": file_data.get("metrics", {}).get("total_issues", 0)
                })
    elif selected_metric == "Code Smells":
        # Обработка данных для Code Smells
        for file_data in report_data:
            file_name = file_data.get("file", "")
            error_count = file_data.get("error_count", 0)
            fixed_code = file_data.get("fixed_code", "")
            
            # Добавляем только файлы с ошибками или с исправленным кодом
            if error_count > 0 or fixed_code:
                files_list.append({
                    "file_name": file_name,
                    "file_path": file_name,
                    "issues": error_count,
                    "has_fixed_code": bool(fixed_code)
                })
    
    if not files_list:
        st.sidebar.info("Нет проблемных файлов для выбранной метрики.")
    else:
        # Сортировка файлов по количеству проблем по убыванию
        sorted_files = sorted(files_list, key=lambda x: x["issues"], reverse=True)
    
        for idx, file in enumerate(sorted_files):
            file_name = file["file_name"]
            issues_count = file["issues"]
            
            button_label = f"{file_name} ({issues_count} проблем)"
            if "complexity" in file:
                button_label += f" (сложность: {file['complexity']})"
            elif "has_fixed_code" in file and file["has_fixed_code"]:
                button_label += " (есть исправления)"
                
            if st.sidebar.button(button_label, key=f"{prefix}_file_{idx}"):
                st.session_state["selected_problem_file"] = file["file_path"]
                st.session_state["selected_problem_file_name"] = file_name


def prepare_issue_tooltips(repo_name, file_path, selected_metric):
    """
    Prepare tooltips for issues found in the file.
    
    Args:
        repo_name (str): Name of the repository
        file_path (str): Path to the file
        selected_metric (str): Selected metric type
        
    Returns:
        dict: Mapping from line numbers to tooltip content
    """
    tooltips = {}
    report_data = load_repository_data(repo_name, selected_metric)
    
    if selected_metric == "Сложность кода":
        # В отчете о сложности ищем по полному пути
        for path, data in report_data.items():
            if path.endswith(file_path) or extract_base_filename(path) == file_path:
                for fragment in data.get("fragments", []):
                    start_line = fragment.get("start_line", 0)
                    end_line = fragment.get("end_line", 0)
                    
                    for line in range(start_line, end_line + 1):
                        tooltips[line] = {
                            "text": fragment.get("description", ""),
                            "solution": fragment.get("solve", ""),
                            "criticality": fragment.get("criticality", "medium")
                        }
    
    elif selected_metric == "Ошибки":
        # В отчете об ошибках ищем по имени файла
        file_data = report_data.get("file_reports", {}).get(file_path, {})
        
        for issue_id, issue in file_data.get("issues", {}).items():
            rows_str = issue.get("rows", "")
            # Обработка строк вида "34-37"
            match = re.match(r"(\d+)-(\d+)", rows_str)
            if match:
                start_line = int(match.group(1))
                end_line = int(match.group(2))
            else:
                try:
                    start_line = int(rows_str)
                    end_line = start_line
                except ValueError:
                    continue
                
            for line in range(start_line, end_line + 1):
                tooltips[line] = {
                    "text": issue.get("error", ""),
                    "solution": issue.get("solution", ""),
                    "criticality": issue.get("criticality", "medium")
                }
    
    # Для Code Smells нет tooltips с привязкой к строкам, поэтому здесь они не обрабатываются
    
    return tooltips


def show_problem_file(repo_name):
    """
    Show the selected problem file with tooltips and suggested fixes.
    
    Args:
        repo_name (str): Name of the repository
    """
    if "selected_problem_file" not in st.session_state:
        st.info("Выберите файл из списка проблемных файлов в сайдбаре.")
        return
    
    file_path = st.session_state["selected_problem_file"]
    file_name = st.session_state.get("selected_problem_file_name", file_path)
    selected_metric = st.session_state.get("selected_metric", "Сложность кода")
    
    st.title(f"Анализ файла: {file_name}")
    st.write(f"Метрика: {selected_metric}")
    
    if "repositories" in st.session_state and "selected_repo_index" in st.session_state:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        short_name = get_short_repo_name(selected_repo["url"])
        repo_name = short_name
    
    # Специальная обработка для Code Smells
    if selected_metric == "Code Smells":
        report_data = load_repository_data(repo_name, selected_metric)
        
        # Найти данные выбранного файла
        file_data = None
        for item in report_data:
            if item.get("file") == file_path:
                file_data = item
                break
        
        if file_data:
            # Если есть исправленный код, отобразить его
            fixed_code = file_data.get("fixed_code", "")
            if fixed_code:
                # Удаляем префикс из исправленного кода
                cleaned_code = clean_fixed_code(fixed_code)
                
                st.subheader("Исправленный код:")
                st.code(cleaned_code, language="python")
                
                # Показать всплывающее окно с кнопкой
                button_clicked = st.button("В чат")
                if button_clicked:
                    st.session_state["selected_main_tab"] = "Кастомные метрики"
            else:
                st.warning(f"Для файла {file_name} отсутствует исправленный код.")
        else:
            st.error(f"Данные для файла {file_name} не найдены.")
        
        return
    
    # Загрузка исходного кода файла для других метрик
    st.write(f"Попытка загрузить файл: {repo_name}, {file_path}")
    source_code = load_source_file(repo_name, file_path)
    
    # Подготовка всплывающих подсказок для проблемных строк
    tooltips = prepare_issue_tooltips(repo_name, file_path, selected_metric)
    
    # Если есть подсказки, создаем JS структуру для них
    tooltips_json = json.dumps(tooltips)
    
    # Показать всплывающее окно с кнопкой
    button_clicked = st.button("В чат")
    if button_clicked:
        st.session_state["selected_main_tab"] = "Кастомные метрики"

    # Escape special characters in source code for JavaScript
    source_code_escaped = json.dumps(source_code)
    
    # HTML+JS с Ace Editor и обработчиком события hover
    ace_editor_html = f"""
    <html>
    <head>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.14/ace.js"></script>
      <style>
        #editor-container {{
          position: relative;
          width: 100%;
          height: 500px;
        }}
        #editor {{
          position: absolute;
          top: 0;
          right: 0;
          bottom: 0;
          left: 0;
          font-size: 14px;
          border: 1px solid #ddd;
        }}
        .tooltip {{
          position: absolute;
          background-color: #333;
          color: #fff;
          padding: 10px 15px;
          border-radius: 4px;
          font-size: 14px;
          display: none;
          z-index: 1000;
          max-width: 400px;
          white-space: pre-wrap;
        }}
        .solution-tooltip {{
          background-color: #2a6496;
          margin-top: 10px;
        }}
        /* Стили для подсветки проблемных строк */
        .ace_marker-layer .tooltip-highlight-high {{
          position: absolute;
          background-color: rgba(255,200,200,0.5) !important;
        }}
        .ace_marker-layer .tooltip-highlight-medium {{
          position: absolute;
          background-color: rgba(255,235,156,0.5) !important;
        }}
        .ace_marker-layer .tooltip-highlight-low {{
          position: absolute;
          background-color: rgba(200,255,200,0.5) !important;
        }}
      </style>
    </head>
    <body>
      <div id="editor-container">
        <div id="editor"></div>
        <div id="tooltip" class="tooltip"></div>
        <div id="solution-tooltip" class="tooltip solution-tooltip"></div>
      </div>
      <script>
        // Инициализация редактора
        var editor = ace.edit("editor");
        editor.setTheme("ace/theme/github");
        editor.session.setMode("ace/mode/python");
        editor.setReadOnly(true);
        editor.setShowPrintMargin(false);
        editor.setOptions({{
            fontSize: "14px"
        }});
        
        // Установка исходного кода
        var code = {source_code_escaped};
        editor.setValue(code, -1);
        
        // Получение данных о проблемных местах
        var tooltipsData = {tooltips_json};
        
        // Создание маркеров для выделения проблемных строк
        var Range = ace.require('ace/range').Range;
        var markers = [];
        
        for (var line in tooltipsData) {{
            var criticality = tooltipsData[line].criticality || "medium";
            var markerClass = "";
            if (criticality === "high") {{
                markerClass = "tooltip-highlight-high";
            }} else if (criticality === "low") {{
                markerClass = "tooltip-highlight-low";
            }} else {{
                markerClass = "tooltip-highlight-medium";
            }}
            
            var markerRange = new Range(parseInt(line) - 1, 0, parseInt(line) - 1, Infinity);
            // Добавляем маркер с нужным классом для выделения всей строки
            editor.session.addMarker(markerRange, markerClass, "fullLine", false);
        }}
        
        // Получение и настройка всплывающих подсказок
        var tooltip = document.getElementById("tooltip");
        var solutionTooltip = document.getElementById("solution-tooltip");
        
        // Добавление обработчика движения мыши по редактору
        editor.container.addEventListener("mousemove", function(e) {{
            var position = editor.renderer.screenToTextCoordinates(e.clientX, e.clientY);
            var lineNumber = position.row + 1;  // Ace использует 0-index
            if (tooltipsData[lineNumber]) {{
                tooltip.innerHTML = tooltipsData[lineNumber].text;
                tooltip.style.left = e.clientX + 10 + "px";
                tooltip.style.top = e.clientY + 10 + "px";
                tooltip.style.display = "block";
                
                if (tooltipsData[lineNumber].solution) {{
                    solutionTooltip.innerHTML = "Решение: " + tooltipsData[lineNumber].solution.replace(/```python\\n|```/g, '');
                    solutionTooltip.style.left = e.clientX + 10 + "px";
                    solutionTooltip.style.top = (e.clientY + tooltip.offsetHeight + 20) + "px";
                    solutionTooltip.style.display = "block";
                }} else {{
                    solutionTooltip.style.display = "none";
                }}
            }} else {{
                tooltip.style.display = "none";
                solutionTooltip.style.display = "none";
            }}
        }});
        
        // Скрытие подсказок при выходе мыши за пределы редактора
        editor.container.addEventListener("mouseout", function() {{
            tooltip.style.display = "none";
            solutionTooltip.style.display = "none";
        }});
      </script>
    </body>
    </html>
    """

    # Отображаем редактор с поддержкой tooltip
    html(ace_editor_html, height=520, scrolling=True)