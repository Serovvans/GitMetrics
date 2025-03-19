import tempfile
import git
from pathlib import Path
from typing import TypedDict, List, Dict, Union
import yaml

from langgraph.graph import StateGraph
from ai.agents.ErrorsSearcher import ErrorSearcher


class RepoAnalysisState(TypedDict):
    repo_url: str
    root_path: str
    file_paths: List[str]
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
            "file_paths": file_paths
        }
    except Exception as e:
        return {"analysis_results": {"repo": {"error": f"Failed to clone repo: {e}"}}}


def analyze_files(state: RepoAnalysisState):
    results = {}
    root = Path(state["root_path"])
    agent_config = load_agent_config()
    user_prompt_template = agent_config['ErrorSearcher']['user_prompt_template']

    for full_path in state["file_paths"]:
        try:
            rel_path = str(Path(full_path).relative_to(root))

            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            # Формируем промпт с использованием шаблона
            user_prompt = user_prompt_template.format(code=code)

            # Правильный формат вызова агента
            result = ErrorSearcher.invoke({
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            })

            # Проверка на словарь, как ожидается в output
            if not isinstance(result, dict):
                raise ValueError(f"Ожидался словарь, получено: {type(result)}")

            results[rel_path] = result

        except Exception as e:
            results[rel_path] = {"error": f"Ошибка анализа: {str(e)}"}

    return {"analysis_results": results}


def aggregate_results(state: RepoAnalysisState):
    return {"analysis_results": state["analysis_results"]}


def build_code_analysis_workflow():
    builder = StateGraph(RepoAnalysisState)

    builder.add_node("clone_repo", clone_repo)
    builder.add_node("analyze_files", analyze_files)
    builder.add_node("aggregate_results", aggregate_results)

    builder.set_entry_point("clone_repo")
    builder.add_edge("clone_repo", "analyze_files")
    builder.add_edge("analyze_files", "aggregate_results")
    builder.set_finish_point("aggregate_results")

    return builder.compile()

code_analysis_graph = build_code_analysis_workflow()
