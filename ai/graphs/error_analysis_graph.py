import tempfile
import git
import re
import json
import os
from pathlib import Path
from typing import TypedDict, List, Dict, Union, Literal
from ai.utils import load_agent_config
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
    output_file_path: str

def clone_repo(state: RepoAnalysisState):
    try:
        tmp_dir = tempfile.mkdtemp()
        repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
        root_path = Path(tmp_dir).resolve()
        code_extensions = [".py", ".java", ".cpp"]
        file_paths = [
            str(path.resolve().relative_to(root_path)) for path in root_path.rglob("*")
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
    if state["current_file_index"] >= len(state["file_paths"]):
        return {"current_file": ""}
    current_file = state["file_paths"][state["current_file_index"]]
    return {
        "current_file": current_file,
        "current_file_index": state["current_file_index"] + 1
    }

def analyze_file(state: dict):
    current_file = state["current_file"]
    if not current_file:
        return {"current_analysis": ""}
    
    root = Path(state["root_path"])
    agent_config = load_agent_config()
    user_prompt_template = agent_config['ErrorSearcher']['user_prompt_template']
    system_prompt = agent_config['ErrorSearcher']['system_prompt']

    try:
        with open(root / current_file, "r", encoding="utf-8", errors="ignore") as f:
            code_lines = f.readlines()

        if not code_lines:
            return {"current_analysis": ""}
        
        # Нумеруем строки кода
        numbered_code = "\n".join(f"{i + 1}: {line.rstrip()}" for i, line in enumerate(code_lines))
        
        user_prompt = user_prompt_template.format(code=numbered_code)
        
        result = ErrorSearcher.invoke({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
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
    analysis_results = state.get("analysis_results", {}).copy()
    if current_analysis.startswith("Ошибка анализа:"):
        analysis_results[current_file] = {"error": current_analysis}
        return {"analysis_results": analysis_results}
    
    # Разбор ошибок и вычисление метрик
    issues = {}
    high_priority_count = 0
    medium_priority_count = 0
    low_priority_count = 0
    
    blocks = re.split(r'\[ISSUE (\d+)\]', current_analysis)
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
        
        if criticality_eng == 'high':
            high_priority_count += 1
        elif criticality_eng == 'medium':
            medium_priority_count += 1
        elif criticality_eng == 'low':
            low_priority_count += 1
            
        if code_match:
            solution_text += "\n```python\n" + code_match.group(1).strip() + "\n```"
            
        issues[f"issue {issue_num}"] = {
            "rows": rows,
            "error": error,
            "criticality": criticality_eng,
            "solution": solution_text
        }
    
    total_issues = high_priority_count + medium_priority_count + low_priority_count
    error_score = (high_priority_count * 3 + medium_priority_count * 2 + low_priority_count * 1) / total_issues if total_issues > 0 else 0
    
    file_metrics = {
        "total_issues": total_issues,
        "high_priority": high_priority_count,
        "medium_priority": medium_priority_count,
        "low_priority": low_priority_count,
        "error_score": round(error_score, 2)
    }
    
    analysis_results[current_file] = {
        "metrics": file_metrics,
        "issues": issues
    }
    
    return {"analysis_results": analysis_results}


def route_analysis(state: RepoAnalysisState):
    # Проверяем, все ли файлы обработаны
    if state["current_file_index"] >= len(state["file_paths"]):
        return END
    else:
        return "get_next_file"

def aggregate_results(state: RepoAnalysisState):
    analysis_results = state["analysis_results"]
    
    # Собираем общую статистику по всем файлам
    total_files = len([k for k in analysis_results.keys() if not k.startswith("repo")])
    total_issues = 0
    total_high = 0
    total_medium = 0
    total_low = 0
    
    # Собираем статистику по всем файлам
    for file_path, file_data in analysis_results.items():
        if file_path.startswith("repo") or "error" in file_data:
            continue
            
        metrics = file_data.get("metrics", {})
        total_issues += metrics.get("total_issues", 0)
        total_high += metrics.get("high_priority", 0)
        total_medium += metrics.get("medium_priority", 0)
        total_low += metrics.get("low_priority", 0)
    
    # Вычисляем общую метрику ошибочности для репозитория
    repo_error_score = 0
    if total_issues > 0:
        repo_error_score = (total_high * 3 + total_medium * 2 + total_low * 1) / total_issues
    
    # Создаем итоговый отчет
    report = {
        "repository_summary": {
            "total_files_analyzed": total_files,
            "total_issues": total_issues,
            "high_priority_issues": total_high,
            "medium_priority_issues": total_medium,
            "low_priority_issues": total_low,
            "error_score": round(repo_error_score, 2)
        },
        "file_reports": analysis_results
    }
    
    # Сохраняем отчет в файл, если указан путь
    if "output_file_path" in state and state["output_file_path"]:
        try:
            output_path = state["output_file_path"]
            # Убедимся, что директория существует
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
                
            # Добавляем информацию о сохранении отчета
            report["report_saved"] = True
            report["report_path"] = output_path
        except Exception as e:
            report["report_saved"] = False
            report["report_error"] = str(e)
    
    return {"analysis_results": report}

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

error_analysis_graph = build_code_analysis_workflow()