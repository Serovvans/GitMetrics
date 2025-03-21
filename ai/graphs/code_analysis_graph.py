import tempfile
import git
import re
from pathlib import Path
from typing import TypedDict, List, Dict, Union, Literal
import yaml

from langgraph.graph import StateGraph, END
from ai.agents.ErrorsSearcher import ErrorSearcher


class RepoAnalysisState(TypedDict):
    repo_url: str
    root_path: str
    file_paths: List[str]
    current_file_index: int
    current_file: str
    current_analysis: str
    analysis_results: Dict[str, Dict[str, Union[str, dict]]]


def load_agent_config():
    with open("ai/config/agents.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clone_repo(state: RepoAnalysisState):
    try:
        tmp_dir = tempfile.mkdtemp()
        repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
        root_path = Path(tmp_dir)

        # Ищем нужные файлы
        code_extensions = [".py", ".java", ".cpp"]
        file_paths = [
            str(path) for path in root_path.rglob("*")
            if path.suffix in code_extensions and path.is_file()
        ]

        return {
            "root_path": str(root_path),
            "file_paths": file_paths,
            "current_file_index": 0,
            "analysis_results": {}
        }
    except Exception as e:
        return {"analysis_results": {"repo": {"error": f"Failed to clone repo: {e}"}}}


def get_next_file(state: RepoAnalysisState):
    # Получаем следующий файл для анализа
    if state["current_file_index"] >= len(state["file_paths"]):
        # Если все файлы проанализированы, возвращаем пустое значение
        return {"current_file": ""}
    
    current_file = state["file_paths"][state["current_file_index"]]
    
    return {
        "current_file": current_file,
        "current_file_index": state["current_file_index"] + 1
    }


def analyze_file(state: RepoAnalysisState):
    current_file = state["current_file"]
    
    # Проверка, если файл пустой
    if not current_file:
        return {"current_analysis": ""}
    
    root = Path(state["root_path"])
    agent_config = load_agent_config()
    user_prompt_template = agent_config['ErrorSearcher']['user_prompt_template']
    system_prompt = agent_config['ErrorSearcher']['system_prompt']
    
    try:
        # Читаем содержимое файла
        with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
            
        # Пропускаем пустые файлы
        if not code.strip():
            return {"current_analysis": ""}
            
        # Формируем промпт с использованием шаблона
        user_prompt = user_prompt_template.format(code=code)
        
        # Вызываем агента для анализа файла
        result = ErrorSearcher.invoke({
            "messages": [
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        })
        
        return {"current_analysis": result['messages'][-1].content}
    
    except Exception as e:
        return {"current_analysis": f"Ошибка анализа: {str(e)}"}


def parse_analysis(state: RepoAnalysisState):
    current_file = state["current_file"]
    current_analysis = state["current_analysis"]
    
    if not current_analysis or not current_file:
        return {}
    
    root = Path(state["root_path"])
    rel_path = str(Path(current_file).relative_to(root))
    analysis_results = state.get("analysis_results", {}).copy()

    if current_analysis.startswith("Ошибка анализа:"):
        analysis_results[rel_path] = {"error": current_analysis}
        return {"analysis_results": analysis_results}
    
    issues = {}
    # Делим по блокам [ISSUE N]
    blocks = re.split(r'\[ISSUE (\d+)\]', current_analysis)
    # blocks: ['', '1', '...текст...', '2', '...текст...'] => начинаем с index 1, шаг 2
    for i in range(1, len(blocks), 2):
        issue_num = blocks[i].strip()
        block = blocks[i+1]

        row_match = re.search(r'rows:\s*(.+)', block)
        error_match = re.search(r'error:\s*(.+)', block)
        criticality_match = re.search(r'criticality:\s*(.+)', block)
        solution_match = re.search(r'solution:\s*(.+?)(?:```|$)', block, re.DOTALL)
        code_match = re.search(r'```(?:python)?\n(.*?)```', block, re.DOTALL)

        if not all([row_match, error_match, criticality_match, solution_match]):
            continue

        rows = row_match.group(1).strip()
        error = error_match.group(1).strip()
        crit = criticality_match.group(1).strip().lower()
        solution_text = solution_match.group(1).strip()

        criticality_eng = (
            'low' if 'низк' in crit else
            'medium' if 'средн' in crit else
            'high' if 'высок' in crit else
            'unknown'
        )

        if code_match:
            solution_text += "\n```python\n" + code_match.group(1).strip() + "\n```"

        issues[f"issue {issue_num}"] = {
            "rows": rows,
            "error": error,
            "criticality": criticality_eng,
            "solution": solution_text
        }

    analysis_results[rel_path] = issues
    return {"analysis_results": analysis_results}


def route_analysis(state: RepoAnalysisState):
    # Проверяем, все ли файлы обработаны
    if state["current_file_index"] >= len(state["file_paths"]):
        return END
    else:
        return "get_next_file"


def aggregate_results(state: RepoAnalysisState):
    return {"analysis_results": state["analysis_results"]}


def build_code_analysis_workflow():
    builder = StateGraph(RepoAnalysisState)

    # Добавляем все ноды
    builder.add_node("clone_repo", clone_repo)
    builder.add_node("get_next_file", get_next_file)
    builder.add_node("analyze_file", analyze_file)
    builder.add_node("parse_analysis", parse_analysis)
    builder.add_node("aggregate_results", aggregate_results)

    # Устанавливаем начальную точку
    builder.set_entry_point("clone_repo")
    
    # Создаем основные связи
    builder.add_edge("clone_repo", "get_next_file")
    builder.add_edge("get_next_file", "analyze_file")
    builder.add_edge("analyze_file", "parse_analysis")
    
    # Добавляем условную связь для цикла
    builder.add_conditional_edges(
        "parse_analysis",
        route_analysis,
        {
            "get_next_file": "get_next_file",
            END: "aggregate_results"
        }
    )
    
    # Устанавливаем конечную точку
    builder.set_finish_point("aggregate_results")

    return builder.compile()


code_analysis_graph = build_code_analysis_workflow()