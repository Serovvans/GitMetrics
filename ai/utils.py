import yaml
import pylint.lint
import libcst as cst
import io
import sys
import subprocess
import os
import re

def load_agent_config():
    with open("ai/config/agents.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
    
def load_model_config():
    with open("ai/config/models.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
    
def get_function_code(file_path, start_line, end_line):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        return ''.join(lines[start_line - 1:end_line])
    except Exception as e:
        return f"# Error extracting code: {str(e)}"

def run_pylint(file_path):
    pylint_output = io.StringIO()
    sys.stdout = pylint_output
    try:
        pylint.lint.Run([file_path], exit=False)
    except SystemExit:
        pass
    sys.stdout = sys.__stdout__
    report = pylint_output.getvalue()
    error_count = report.count(f"{file_path}:")
    return report, error_count

def run_cpplint(file_path):
    result = subprocess.run(
        ['python', './ai/linters/cpplint.py', file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8'
    )
    output = result.stdout
    error_count = output.count(file_path + ":")
    return output, error_count

def add_module_docstring(file_path, code):
    if not code.startswith('"""') and not code.startswith("'''"):
        docstring = f'"""File {os.path.basename(file_path)}. Add your description here."""\n'
        code = docstring + code
    return code

def convert_to_snake_case(code):
    # Implementation of convert_to_snake_case
    tree = cst.parse_module(code)
    transformer = RenameToSnakeCase()
    new_tree = tree.visit(transformer)
    return new_tree.code

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

def to_snake_case(name):
    name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
    name = re.sub(r'([A-Z])([A-Z][a-z])', r'\1_\2', name)
    return name.lower()
