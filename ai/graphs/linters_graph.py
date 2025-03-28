import sys
import io
import black
import pylint.lint
import subprocess
import os
import libcst as cst
import re
import tempfile
import git
import json
from pathlib import Path
from langgraph.graph import StateGraph, END
from ai.utils import load_agent_config

agent_config = load_agent_config()


class LinterState(dict):
    """State for complexity analysis workflow"""
    repo_url: str
    output_json: str
    root_path: str
    file_paths: list
    current_file_index: int
    current_file: str
    current_analysis: dict
    analysis_results: dict


def clone_repo(state: LinterState):
    """Клонирует репозиторий и собирает пути файлов"""
    try:
        tmp_dir = tempfile.mkdtemp()
        repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
        root_path = Path(tmp_dir).resolve()
        file_paths = [
            str(p.resolve()) for p in root_path.rglob("*")
            if p.suffix in ['.py', '.cpp', '.h']
        ]

        return {
            "root_path": str(root_path),
            "file_paths": file_paths,
            "current_file_index": 0,
            "analysis_results": {},
            "current_analysis": {}
        }
    except Exception as e:
        return {"analysis_results": {"repo": {"error": f"Failed to clone repo: {e}"}}}


def compile_file_result(state: LinterState):
    """Компилирует результаты анализа текущего файла"""
    current_file = state.get("current_file", "")
    current_analysis = state.get("current_analysis", {})
    root_path = Path(state.get("root_path", "")).resolve()

    if not current_analysis or not current_file:
        return {}

    # Приводим путь к относительному от репозитория
    relative_path = str(Path(current_file).resolve().relative_to(root_path))

    file_result = {
        "file_path": relative_path,  # Записываем относительный путь
        "logs": current_analysis.get("logs", 0),
        "fixed_code": current_analysis.get("fixed_code", 0),
        "error_count": current_analysis.get("error_count", 0),
    }

    analysis_results = state.get("analysis_results", {})
    analysis_results[relative_path] = file_result  # Используем относительный путь в ключе

    return {"analysis_results": analysis_results}


def get_next_file(state: LinterState):
    """Get the next file to analyze"""
    if state.get("current_file_index", 0) >= len(state.get("file_paths", [])):
        return {"current_file": ""}
    return {
        "current_file": state["file_paths"][state["current_file_index"]],
        "current_file_index": state["current_file_index"] + 1,
        "current_analysis": {},
    }


def lint_file(state: LinterState):
    """Analyze complexity of the current file"""
    current_file = state.get("current_file", "")
    if not current_file:
        return {"current_analysis": {}}

    try:
        with open(current_file, 'r', encoding="utf-8") as file:
            code = file.read()

        lint_report, error_count = None, 0

        if current_file.endswith('.py'):
            lint_report, error_count = run_pylint(current_file)
            code = add_module_docstring(current_file, code)
            response = black.format_str(code, mode=black.FileMode())
            response = convert_to_snake_case(response)
        elif current_file.endswith('.cpp') or current_file.endswith('.h') or current_file.endswith(".c"):
            lint_report, error_count = run_cpplint(current_file)
            formatted_code = subprocess.run(
                ["../linters/clang-format", "-style=LLVM"],
                input=code.encode(),
                capture_output=True,
            )
            response = formatted_code.stdout.decode()
        elif current_file.endswith('.java'):
            lint_report, error_count = ("Отчёты для Java файлов coming soon."
                                        " Но предложенный вариант исправления уже доступен!"), 0
            formatted_code = subprocess.run(
                ["../linters/clang-format"],
                input=code.encode(),
                capture_output=True,
            )
            response = formatted_code.stdout.decode()
        else:
            response = "Данный язык пока не поддерживается"

        return {
            "current_analysis": {
                "logs": lint_report,
                "fixed_code": response,
                "error_count": error_count
            }
        }
    except Exception as e:
        return {
            "current_analysis": {
                "error": f"Failed to analyze file {current_file}: {str(e)}",
                "logs": "",
                "fixed_code": "",
                "error_count": 0
            }
        }


def to_snake_case(name):
    name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)  # camelCase → snake_case
    name = re.sub(r'([A-Z])([A-Z][a-z])', r'\1_\2', name)  # PascalCase → snake_case
    return name.lower()


def add_module_docstring(file_path, code):
    """Добавляет строку документации с именем файла, если её нет"""
    if not code.startswith('"""') and not code.startswith("'''"):
        docstring = f'"""File {os.path.basename(file_path)}. Add your description here."""\n'
        code = docstring + code
    return code


class RenameToSnakeCase(cst.CSTTransformer):
    def __init__(self):
        super().__init__()
        self.renamed = {}

    def visit_FunctionDef(self, node):
        new_name = to_snake_case(node.name.value)
        self.renamed[node.name.value] = new_name
        return node

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                new_name = to_snake_case(target.target.value)
                self.renamed[target.target.value] = new_name
        return node

    def leave_FunctionDef(self, original_node, updated_node):
        new_name = self.renamed.get(original_node.name.value, original_node.name.value)
        return updated_node.with_changes(name=cst.Name(new_name))

    def leave_Name(self, original_node, updated_node):
        new_name = self.renamed.get(original_node.value, original_node.value)
        return updated_node.with_changes(value=new_name)


def convert_to_snake_case(code):
    tree = cst.parse_module(code)
    transformer = RenameToSnakeCase()
    new_tree = tree.visit(transformer)
    return new_tree.code


def run_pylint(file_path):
    """Запускает pylint для проверки указанного файла и возвращает отчет и количество ошибок."""
    pylint_output = io.StringIO()
    sys.stdout = pylint_output
    try:
        # Убрать W0621, C0103, C0116
        pylint.lint.Run([file_path], exit=False)
    except SystemExit:
        pass
    sys.stdout = sys.__stdout__
    report = pylint_output.getvalue()
    print(report)
    error_count = report.count(f"{file_path}:")
    return report, error_count


def run_cpplint(file_path):
    """Запускает cpplint и получает полный отчет об ошибках."""
    cpplint_path = '../linters/cpplint.py'

    result = subprocess.run(
        ['python', cpplint_path, file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8'
    )
    output = result.stdout
    print(output)
    error_count = output.count(file_path + ":")

    return output, error_count


def route_analysis(state: LinterState):
    """Determine next step in the workflow"""
    print(f"Current file index: {state.get('current_file_index', 0)}")
    print(f"Total files: {len(state.get('file_paths', []))}")
    return END if state.get("current_file_index", 0) >= len(state.get("file_paths", [])) else "get_next_file"


def save_results(state: LinterState):
    """Save analysis results to JSON file"""
    output_json = state.get("output_json", "linter_report.json")

    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(state["analysis_results"], json_file, ensure_ascii=False, indent=4)

    return {"analysis_results": state["analysis_results"]}


def build_linters_workflow():
    """Build and return the complexity analysis workflow graph"""
    builder = StateGraph(LinterState)

    # Add nodes for repository-based analysis
    builder.add_node("clone_repo", clone_repo)
    builder.add_node("get_next_file", get_next_file)
    builder.add_node("lint_file", lint_file)
    builder.add_node("compile_file_result", compile_file_result)
    builder.add_node("save_results", save_results)

    # Set up edges for repository-based analysis
    builder.set_entry_point("clone_repo")
    builder.add_edge("clone_repo", "get_next_file")
    builder.add_edge("get_next_file", "lint_file")
    builder.add_edge("lint_file", "compile_file_result")


    builder.add_conditional_edges(
        "compile_file_result",
        route_analysis,
        {"get_next_file": "get_next_file", END: "save_results"}
    )

    builder.set_finish_point("save_results")

    return builder.compile()


linters_graph = build_linters_workflow()
