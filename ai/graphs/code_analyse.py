import tempfile
import git
import json
import re
import os
import subprocess
import lizard
import black

from pathlib import Path
from typing import TypedDict, List, Dict, Annotated
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langgraph.graph import StateGraph
import operator

from ai.utils import load_agent_config, run_cpplint, run_pylint, add_module_docstring, convert_to_snake_case
from ai.agents.ErrorsSearcher import ErrorSearcher

llm = ChatGroq(model="qwen-2.5-coder-32b",
               temperature=0.3, max_tokens=7000)

agent_config = load_agent_config()
reason_template = agent_config['ComplexityAnalyzer']['reason_template']
simplify_template = agent_config['ComplexityAnalyzer']['simplify_template']

reason_prompt = PromptTemplate(input_variables=['code'], template=reason_template)
reason_chain = LLMChain(llm=llm, prompt=reason_prompt)
simplify_prompt = PromptTemplate(input_variables=['code'], template=simplify_template)
simplify_chain = LLMChain(llm=llm, prompt=simplify_prompt)

class IntegratedAnalysisState(TypedDict):
    repo_url: str
    root_path: str
    file_paths: List[str]
    use_llm: bool
    linter_results: Annotated[List[Dict], operator.add]
    complexity_results: Annotated[List[Dict], operator.add]
    error_results: Annotated[List[Dict], operator.add]

    output_linter_path: str
    output_complexity_path: str
    output_error_path: str

def clone_repo(state: IntegratedAnalysisState):
    try:
        tmp_dir = tempfile.mkdtemp()
        repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
        root_path = Path(tmp_dir).resolve()
        code_extensions = ['.py', '.cpp', '.h', '.java', '.c']
        file_paths = [
            str(path.resolve().relative_to(root_path)) for path in root_path.rglob("*")
            if path.suffix in code_extensions and path.is_file()
        ]

        return {
            "root_path": str(root_path),
            "file_paths": file_paths,
            "linter_results": [],
            "complexity_results": [],
            "error_results": []
        }
    except Exception as e:
        return {"error_results": [{"repo": {"error": f"Failed to clone repo: {e}"}}]}

def read_file_content(root_path: str, file_path: str):
    try:
        with open(os.path.join(root_path, file_path), 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"# Error reading file: {str(e)}"

def process_all_files_lint(state: IntegratedAnalysisState):
    root_path = state["root_path"]
    file_paths = state["file_paths"]
    linter_results = []
    
    for file_path in file_paths:
        full_path = os.path.join(root_path, file_path)
        
        try:
            with open(full_path, 'r', encoding="utf-8") as file:
                code = file.read()

            lint_report, error_count = None, 0

            if file_path.endswith('.py'):
                lint_report, error_count = run_pylint(full_path)
                code = add_module_docstring(full_path, code)
                response = black.format_str(code, mode=black.FileMode())
                response = convert_to_snake_case(response)
            elif file_path.endswith(('.cpp', '.h', '.c')):
                lint_report, error_count = run_cpplint(full_path)
                formatted_code = subprocess.run(
                    ["sudo", "/Users/ivan/Desktop/HSE/cool_ai/GitMetrics/GitMetrics/ai/linters/clang-format.exe", "-style=LLVM"],
                    input=code.encode(),
                    capture_output=True,
                )
                response = formatted_code.stdout.decode()
            elif file_path.endswith('.java'):
                lint_report = "Java linting coming soon"
                formatted_code = subprocess.run(
                    ["sudo", "/Users/ivan/Desktop/HSE/cool_ai/GitMetrics/GitMetrics/ai/linters/clang-format.exe"],
                    input=code.encode(),
                    capture_output=True,
                )
                response = formatted_code.stdout.decode()
            else:
                response = "Unsupported language"

            linter_results.append({
                "file": file_path,
                "logs": lint_report,
                "fixed_code": response,
                "error_count": error_count
            })
        except Exception as e:
            linter_results.append({
                "file": file_path,
                "error": f"Failed to analyze file {file_path}: {str(e)}",
                "logs": "",
                "fixed_code": "",
                "error_count": 0
            })
    
    return {"linter_results": linter_results}

def get_function_code(file_path, start_line, end_line):
    """Extract function code based on line numbers"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        return ''.join(lines[start_line - 1:end_line])
    except Exception as e:
        return f"# Error extracting code: {str(e)}"

def process_all_files_complexity(state: IntegratedAnalysisState):
    root_path = state["root_path"]
    file_paths = state["file_paths"]
    use_llm = state.get("use_llm", False)
    complexity_results = []
    
    for file_path in file_paths:
        full_path = os.path.join(root_path, file_path)
        
        try:
            # Analyze file complexity
            analysis = lizard.analyze_file(full_path)
            functions_data = []
            total_complexity = 0
            num_functions = len(analysis.function_list)
            fragments = []

            for function in analysis.function_list:
                end_line = function.start_line + function.length - 1
                total_complexity += function.cyclomatic_complexity
                function_info = {
                    "function_name": function.name,
                    "complexity": function.cyclomatic_complexity,
                    "lines": function.nloc,
                    "start_line": function.start_line,
                    "end_line": end_line,
                }
                
                # Process complex functions
                if function.cyclomatic_complexity >= 8:
                    criticality = "high"
                elif function.cyclomatic_complexity >= 4:
                    criticality = "medium"
                else:
                    criticality = "low"
                    
                if criticality == "low":
                    continue
                functions_data.append(function_info)
                func_code = get_function_code(full_path, function.start_line, end_line)
                
                if use_llm:
                    try:
                        reason = reason_chain.invoke({"code": func_code})["text"]
                        simplified_code = simplify_chain.invoke({"code": func_code})["text"]
                    except Exception as e:
                        reason = f"Ошибка при анализе: {str(e)}"
                        simplified_code = "# Ошибка при упрощении"
                else:
                    reason = "-"
                    simplified_code = "-"
                    
                fragments.append({
                    "function_name": function.name,
                    "original_complexity": function.cyclomatic_complexity,
                    "start_line": function.start_line,
                    "end_line": end_line,
                    "description": reason,
                    "solve": simplified_code,
                    "criticality": criticality
                })

            average_complexity = total_complexity / num_functions if num_functions > 0 else 0
            
            complexity_results.append({
                "file": file_path,
                "functions": functions_data,
                "fragments": fragments,
                "total_complexity": total_complexity,
                "average_complexity": average_complexity
            })
            
        except Exception as e:
            complexity_results.append({
                "file": file_path,
                "error": f"Failed to analyze file {file_path}: {str(e)}",
                "functions": [],
                "fragments": [],
                "total_complexity": 0,
                "average_complexity": 0
            })
    
    return {"complexity_results": complexity_results}

def _parse_error_analysis(llm_response):
    """
    Parse LLM error analysis response into structured issues and metrics.
    
    Args:
        llm_response (str): Raw text response from LLM containing error analysis
    
    Returns:
        tuple: A tuple containing (issues dictionary, metrics dictionary)
    """
    # Split the response into individual issue blocks
    issue_blocks = re.split(r'\[ISSUE (\d+)\]', llm_response)[1:]
    
    issues = {}
    priority_counts = {
        'high': 0,
        'medium': 0,
        'low': 0
    }
    
    # Process blocks in pairs (issue number and content)
    for i in range(0, len(issue_blocks), 2):
        issue_number = issue_blocks[i]
        issue_content = issue_blocks[i+1]
        
        # Extract key information using regex
        row_match = re.search(r'rows:\s*(.+?)(?:\n|$)', issue_content)
        error_match = re.search(r'error:\s*(.+?)(?:\n|$)', issue_content)
        criticality_match = re.search(r'criticality:\s*(.+)', issue_content)
        solution_match = re.search(r'solution:\s*(.+?)(?:```|$)', issue_content, re.DOTALL)
        code_match = re.search(r'```(?:python|cpp|java)?\n(.*?)```', issue_content, re.DOTALL | re.MULTILINE)
        
        # Skip incomplete issues
        if not all([row_match, error_match, criticality_match, solution_match]):
            continue
        
        # Extract and clean matched groups
        rows = row_match.group(1).strip()
        error = error_match.group(1).strip()
        criticality = criticality_match.group(1).strip().lower()
        solution_text = solution_match.group(1).strip()
        
        # Normalize criticality
        criticality_eng = (
            'low' if 'низк' in criticality else
            'medium' if 'средн' in criticality else
            'high' if 'высок' in criticality else
            'unknown'
        )
        
        # Update priority counts
        if criticality_eng in priority_counts:
            priority_counts[criticality_eng] += 1
        
        # Add code solution if available
        if code_match:
            solution_text += f"\n```{code_match.group(1).strip()}```"
        
        # Store issue details
        issues[f'issue_{issue_number}'] = {
            'rows': rows,
            'error': error,
            'criticality': criticality_eng,
            'solution': solution_text
        }
    
    # Calculate error score and metrics
    total_issues = sum(priority_counts.values())
    error_score = (
        priority_counts['high'] * 3 + 
        priority_counts['medium'] * 2 + 
        priority_counts['low'] * 1
    ) / total_issues if total_issues > 0 else 0
    
    metrics = {
        'total_issues': total_issues,
        'high_priority': priority_counts['high'],
        'medium_priority': priority_counts['medium'],
        'low_priority': priority_counts['low'],
        'error_score': round(error_score, 2)
    }
    
    return issues, metrics

def process_all_files_errors(state: IntegratedAnalysisState):
    root_path = state["root_path"]
    file_paths = state["file_paths"]
    error_results = []
    
    agent_config = load_agent_config()
    user_prompt_template = agent_config['ErrorSearcher']['user_prompt_template']
    system_prompt = agent_config['ErrorSearcher']['system_prompt']
    
    for file_path in file_paths:
        full_path = os.path.join(root_path, file_path)
        
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                code_lines = f.readlines()

            if not code_lines:
                error_results.append({
                    "file": file_path,
                    "metrics": {},
                    "issues": {}
                })
                continue
            
            # Нумеруем строки кода
            numbered_code = "\n".join(f"{i + 1}: {line.rstrip()}" for i, line in enumerate(code_lines))
            
            user_prompt = user_prompt_template.format(code=numbered_code)
            
            result = ErrorSearcher.invoke({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            })

            issues, metrics = _parse_error_analysis(result['messages'][-1].content)
            
            error_results.append({
                "file": file_path,
                "metrics": metrics,
                "issues": issues
            })
        
        except Exception as e:
            error_results.append({
                "file": file_path, 
                "error": f"Ошибка анализа: {str(e)}",
                "metrics": {},
                "issues": {}
            })
    
    return {"error_results": error_results}

def compare_analyze(complexity_results, error_results):
    # Transform complexity results
    complexity_dict = {}
    
    for result in complexity_results:
        file_path = result.get("file", "")
        complexity_dict[file_path] = {
            "file_path": file_path,
            "total_complexity": result.get("total_complexity", 0),
            "average_complexity": result.get("average_complexity", 0),
            "fragments": result.get("fragments", [])
        }
    
    file_reports = {}
    repository_summary = {
        "total_files_analyzed": len(error_results),
        "total_issues": 0,
        "high_priority_issues": 0,
        "medium_priority_issues": 0,
        "low_priority_issues": 0,
        "error_score": 0.0
    }
    
    for result in error_results:
        file_path = result.get("file", "")
        file_metrics = result.get("metrics", {})
        
        # Accumulate repository-level metrics
        repository_summary["total_issues"] += file_metrics.get("total_issues", 0)
        repository_summary["high_priority_issues"] += file_metrics.get("high_priority", 0)
        repository_summary["medium_priority_issues"] += file_metrics.get("medium_priority", 0)
        repository_summary["low_priority_issues"] += file_metrics.get("low_priority", 0)
        repository_summary["error_score"] += file_metrics.get("error_score", 0.0)
        
        # Create file-specific report
        file_reports[file_path] = {
            "metrics": file_metrics,
            "issues": result.get("issues", {})
        }
    
    # Calculate average error score
    if len(error_results) > 0:
        repository_summary["error_score"] /= len(error_results)
    
    # Prepare final error results structure
    transformed_error_results = {
        "repository_summary": repository_summary,
        "file_reports": file_reports
    }
    
    return complexity_dict, transformed_error_results

def save_results(state: IntegratedAnalysisState):
    linter_results = state.get("linter_results", [])
    complexity_results = state.get("complexity_results", [])
    error_results = state.get("error_results", [])
    
    complexity_results, error_results = compare_analyze(complexity_results, error_results)
    
    # Save linter results
    if "output_linter_path" in state:
        with open(state["output_linter_path"], "w", encoding="utf-8") as f:
            json.dump(linter_results, f, ensure_ascii=False, indent=4)
    
    # Save complexity results
    if "output_complexity_path" in state:
        with open(state["output_complexity_path"], "w", encoding="utf-8") as f:
            json.dump(complexity_results, f, ensure_ascii=False, indent=4)
    
    # Save error results
    if "output_error_path" in state:
        with open(state["output_error_path"], "w", encoding="utf-8") as f:
            json.dump(error_results, f, ensure_ascii=False, indent=4)
    
    return {"final_results": [linter_results, compare_analyze, error_results]}

def build_integrated_code_analysis_workflow():
    builder = StateGraph(IntegratedAnalysisState)

    # Add nodes
    builder.add_node("clone_repo", clone_repo)
    builder.add_node("process_all_files_lint", process_all_files_lint)
    builder.add_node("process_all_files_complexity", process_all_files_complexity)
    builder.add_node("process_all_files_errors", process_all_files_errors)
    builder.add_node("save_results", save_results)

    # Set starting point
    builder.set_entry_point("clone_repo")

    # Параллельные ветки после клонирования репозитория
    builder.add_edge("clone_repo", "process_all_files_lint")
    builder.add_edge("clone_repo", "process_all_files_complexity")
    builder.add_edge("clone_repo", "process_all_files_errors")
    
    # Объединение результатов после параллельной обработки
    builder.add_edge("process_all_files_lint", "save_results")
    builder.add_edge("process_all_files_complexity", "save_results")
    builder.add_edge("process_all_files_errors", "save_results")

    # Set finish point
    builder.set_finish_point("save_results")

    return builder.compile()

integrated_code_analysis_graph = build_integrated_code_analysis_workflow()