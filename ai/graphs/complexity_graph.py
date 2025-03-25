import lizard
import tempfile
import git
import json
from langchain_groq import ChatGroq
from pathlib import Path
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langgraph.graph import StateGraph, END
from ai.utils import load_agent_config

# Initialize LLM and load templates from config
llm = ChatGroq(model="qwen-2.5-coder-32b",
               temperature=0.4, max_tokens=7000)

agent_config = load_agent_config()
reason_template = agent_config['ComplexityAnalyzer']['reason_template']
simplify_template = agent_config['ComplexityAnalyzer']['simplify_template']

reason_prompt = PromptTemplate(input_variables=['code'], template=reason_template)
reason_chain = LLMChain(llm=llm, prompt=reason_prompt)
simplify_prompt = PromptTemplate(input_variables=['code'], template=simplify_template)
simplify_chain = LLMChain(llm=llm, prompt=simplify_prompt)


class ComplexityAnalysisState(dict):
    """State for complexity analysis workflow"""
    repo_url: str
    output_json: str
    use_llm: bool
    root_path: str
    file_paths: list
    current_file_index: int
    current_file: str
    current_analysis: dict
    current_fragments: list
    analysis_results: dict


def clone_repo(state: ComplexityAnalysisState):
    """Клонирует репозиторий и собирает пути файлов"""
    try:
        tmp_dir = tempfile.mkdtemp()
        repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
        root_path = Path(tmp_dir).resolve()
        file_paths = [str(p.resolve()) for p in root_path.rglob("*.py")]

        return {
            "root_path": str(root_path),  # Сохраняем корень репозитория
            "file_paths": file_paths,
            "current_file_index": 0,
            "analysis_results": {},
            "current_analysis": {},
            "current_fragments": []
        }
    except Exception as e:
        return {"analysis_results": {"repo": {"error": f"Failed to clone repo: {e}"}}}


def compile_file_result(state: ComplexityAnalysisState):
    """Компилирует результаты анализа текущего файла"""
    current_file = state.get("current_file", "")
    current_analysis = state.get("current_analysis", {})
    current_fragments = state.get("current_fragments", [])
    root_path = Path(state.get("root_path", "")).resolve()

    if not current_analysis or not current_file:
        return {}

    # Приводим путь к относительному от репозитория
    relative_path = str(Path(current_file).resolve().relative_to(root_path))

    file_result = {
        "file_path": relative_path,  # Записываем относительный путь
        "total_complexity": current_analysis.get("total_complexity", 0),
        "average_complexity": current_analysis.get("average_complexity", 0),
        "fragments": current_fragments
    }

    analysis_results = state.get("analysis_results", {})
    analysis_results[relative_path] = file_result  # Используем относительный путь в ключе

    return {"analysis_results": analysis_results}



def get_next_file(state: ComplexityAnalysisState):
    """Get the next file to analyze"""
    if state.get("current_file_index", 0) >= len(state.get("file_paths", [])):
        return {"current_file": ""}
    return {
        "current_file": state["file_paths"][state["current_file_index"]], 
        "current_file_index": state["current_file_index"] + 1,
        "current_analysis": {},
        "current_fragments": []
    }


def analyze_file_complexity(state: ComplexityAnalysisState):
    """Analyze complexity of the current file"""
    current_file = state.get("current_file", "")
    if not current_file:
        return {"current_analysis": {}}
    
    try:
        analysis = lizard.analyze_file(current_file)
        functions_data = []
        total_complexity = 0
        num_functions = len(analysis.function_list)

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
            if function.cyclomatic_complexity >= 5:
                functions_data.append(function_info)

        average_complexity = total_complexity / num_functions if num_functions > 0 else 0
        
        return {
            "current_analysis": {
                "functions": functions_data,
                "total_complexity": total_complexity,
                "average_complexity": average_complexity
            }
        }
    except Exception as e:
        return {
            "current_analysis": {
                "error": f"Failed to analyze file {current_file}: {str(e)}",
                "functions": [],
                "total_complexity": 0,
                "average_complexity": 0
            }
        }


def get_function_code(file_path, start_line, end_line):
    """Extract function code based on line numbers"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        return ''.join(lines[start_line - 1:end_line])
    except Exception as e:
        return f"# Error extracting code: {str(e)}"


def analyze_complex_functions(state: ComplexityAnalysisState):
    """Analyze and simplify complex functions using LLM if enabled"""
    current_file = state.get("current_file", "")
    current_analysis = state.get("current_analysis", {})
    
    if not current_analysis or not current_file:
        return {"current_fragments": []}
    
    use_llm = state.get("use_llm", False)
    fragments = []
    
    functions = current_analysis.get("functions", [])
    for func in functions:
        func_code = get_function_code(current_file, func["start_line"], func["end_line"])
        
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
            "function_name": func["function_name"],
            "original_complexity": func["complexity"],
            "start_line": func["start_line"],
            "end_line": func["end_line"],
            "description": reason,
            "solve": simplified_code,
        })
    
    return {"current_fragments": fragments}


def route_analysis(state: ComplexityAnalysisState):
    """Determine next step in the workflow"""
    return END if state.get("current_file_index", 0) >= len(state.get("file_paths", [])) else "get_next_file"


def save_results(state: ComplexityAnalysisState):
    """Save analysis results to JSON file"""
    output_json = state.get("output_json", "complexity_report.json")
    
    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(state["analysis_results"], json_file, ensure_ascii=False, indent=4)
    
    return {"analysis_results": state["analysis_results"]}


def build_complexity_analysis_workflow():
    """Build and return the complexity analysis workflow graph"""
    builder = StateGraph(ComplexityAnalysisState)
    
    # Add nodes for repository-based analysis
    builder.add_node("clone_repo", clone_repo)
    builder.add_node("get_next_file", get_next_file)
    builder.add_node("analyze_file_complexity", analyze_file_complexity)
    builder.add_node("analyze_complex_functions", analyze_complex_functions)
    builder.add_node("compile_file_result", compile_file_result)
    builder.add_node("save_results", save_results)
    
    # Set up edges for repository-based analysis
    builder.set_entry_point("clone_repo")
    builder.add_edge("clone_repo", "get_next_file")
    builder.add_edge("get_next_file", "analyze_file_complexity")
    builder.add_edge("analyze_file_complexity", "analyze_complex_functions")
    builder.add_edge("analyze_complex_functions", "compile_file_result")
    
    builder.add_conditional_edges(
        "compile_file_result", 
        route_analysis, 
        {"get_next_file": "get_next_file", END: "save_results"}
    )
    
    builder.set_finish_point("save_results")
    
    return builder.compile()

complexity_analysis_graph = build_complexity_analysis_workflow()
