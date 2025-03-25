import json
import sys
import io
import black
import pylint.lint
import subprocess
import os
import libcst as cst
import re


# Функция для перевода в snake_case
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
    cpplint_path = os.path.join(os.path.dirname(__file__), 'cpplint.py')

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


def lint_file(file_path):
    """Исправляет ошибки в файле"""
    with open(file_path, 'r', encoding="utf-8") as file:
        code = file.read()

    lint_report, error_count = None, 0

    if file_path.endswith('.py'):
        lint_report, error_count = run_pylint(file_path)
        code = add_module_docstring(file_path, code)
        response = black.format_str(code, mode=black.FileMode())
        response = convert_to_snake_case(response)
    elif file_path.endswith('.cpp') or file_path.endswith('.h') or file_path.endswith(".c"):
        lint_report, error_count = run_cpplint(file_path)
        formatted_code = subprocess.run(
            ["clang-format", "-style=LLVM"],
            input=code.encode(),
            capture_output=True,
        )
        response = formatted_code.stdout.decode()
    elif file_path.endswith('.java'):
        lint_report, error_count = ("Отчёты для Java файлов coming soon."
                                    " Но предложенный вариант исправления уже доступен!"), 0
        formatted_code = subprocess.run(
            ["clang-format"],
            input=code.encode(),
            capture_output=True,
        )
        response = formatted_code.stdout.decode()
    else:
        response = "Данный язык пока не поддерживается"
    return {
        "file_path": file_path,
        "logs": lint_report,
        "fixed_code": response,
        "error_count": error_count
    }


path = input("Введите путь к файлу: ")
lint_result = lint_file(path)
with open("lint_result.json", "w", encoding="utf-8") as json_file:
    json.dump(lint_result, json_file, ensure_ascii=False, indent=4)
