import tempfile
import git
from pathlib import Path
from typing import TypedDict, List, Dict
import re
import os

from langgraph.graph import StateGraph, END
from ai.agents.CustomCriteria import CustomCriteria
from ai.utils import load_agent_config


class FileAnalysisState(TypedDict):
    repo_url: str
    root_path: str
    file_paths: List[str]
    current_index: int
    current_file: str
    current_code: str
    current_analysis: str
    reports: Dict[str, str]
    criteria: str
    folder_path: str


def clone_repo(state: FileAnalysisState):
    tmp_dir = tempfile.mkdtemp()
    repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
    root = Path(tmp_dir)

    code_files = [
        str(path) for path in root.rglob("*")
        if path.suffix in [".py", ".js", ".java", ".cpp", ".cs"] and path.is_file()
    ]

    return {
        "root_path": str(root),
        "file_paths": code_files,
        "current_index": 0,
        "reports": {},
    }


def get_next_file(state: FileAnalysisState):
    if state["current_index"] >= len(state["file_paths"]):
        return {"current_file": ""}
    
    file_path = state["file_paths"][state["current_index"]]
    return {
        "current_file": file_path,
        "current_index": state["current_index"] + 1
    }


def read_code(state: FileAnalysisState):
    current = state["current_file"]
    if not current:
        return {"current_code": ""}

    try:
        with open(current, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        return {"current_code": code}
    except Exception as e:
        return {"current_code": f"Ошибка чтения файла: {e}"}


def analyze_code(state: FileAnalysisState):
    agent_config = load_agent_config()
    user_prompt_template = agent_config['CodeAnalyzer']['user_prompt_template']
    system_prompt = agent_config['CodeAnalyzer']['system_prompt']
    
    code = state["current_code"]
    if not code.strip():
        return {"current_analysis": ""}
    
    user_prompt = user_prompt_template.format(code=code, criteria=state['criteria'])

    result = CustomCriteria.invoke({
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

    return {"current_analysis": result['messages'][-1].content.strip()}


def generate_report(state: FileAnalysisState):
    path = Path(state["current_file"])
    root = Path(state["root_path"])
    rel_path = str(path.relative_to(root))

    report = (
        f"### Отчет по файлу: {rel_path}\n\n"
        f"**Анализ:**\n{state['current_analysis']}\n\n"
    )


    filename = os.path.join(state["folder_path"], f"report_{path.name}.md")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)

    new_reports = state.get("reports", {}).copy()
    new_reports[rel_path] = report
    return {"reports": new_reports}


def route_next(state: FileAnalysisState):
    if state["current_index"] >= len(state["file_paths"]):
        return END
    return "get_next_file"


def summarize(state: FileAnalysisState):
    summary = "# Итоговый отчет\n\n"
    for filename, report in state["reports"].items():
        summary += f"## {filename}\n{report}\n\n"

    clean_report = re.sub(r"<think>.*?</think>", "", summary, flags=re.DOTALL)
    with open(os.path.join(state["folder_path"], "summary_report.md"), "w", encoding="utf-8") as f:
        f.write(clean_report)

    return {"reports": state["reports"]}


def build_graph():
    builder = StateGraph(FileAnalysisState)

    builder.add_node("clone_repo", clone_repo)
    builder.add_node("get_next_file", get_next_file)
    builder.add_node("read_code", read_code)
    builder.add_node("analyze_code", analyze_code)
    builder.add_node("generate_report", generate_report)
    builder.add_node("summarize", summarize)

    builder.set_entry_point("clone_repo")

    builder.add_edge("clone_repo", "get_next_file")
    builder.add_edge("get_next_file", "read_code")
    builder.add_edge("read_code", "analyze_code")
    builder.add_edge("analyze_code", "generate_report")

    builder.add_conditional_edges(
        "generate_report",
        route_next,
        {
            "get_next_file": "get_next_file",
            END: "summarize"
        }
    )

    builder.set_finish_point("summarize")

    return builder.compile()

custom_criteria_graph = build_graph()
