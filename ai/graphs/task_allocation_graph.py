import json
import os
from pathlib import Path
from typing import TypedDict, List, Dict, Annotated, Optional, Any
import operator
import re

from langgraph.graph import StateGraph
from ai.agents.TaskAllocation import TaskAllocationAgent
from ai.utils import load_agent_config

class TaskAllocationState(TypedDict):
    repo_path: str
    storage_dir: str
    repo_name: str
    complexity_report_path: str
    error_report_path: str
    complexity_data: Dict
    error_data: Dict
    complexity_tasks: Annotated[List[Dict], operator.add]
    error_tasks: Annotated[List[Dict], operator.add]
    tasks: Annotated[List[Dict], operator.add]
    output_tasks_path: str
    current_task_index: int
    current_task_source: str  # "complexity" or "error"
    current_task: Optional[Dict]
    processed_tasks: Annotated[List[Dict], operator.add]
    is_processing_complete: bool

def load_complexity_report(state: TaskAllocationState):
    """Load complexity report from JSON file"""
    try:
        with open(state["complexity_report_path"], "r", encoding="utf-8") as f:
            complexity_data = json.load(f)
        return {"complexity_data": complexity_data}
    except Exception as e:
        return {"complexity_data": {}, "error": f"Failed to load complexity report: {str(e)}"}

def load_error_report(state: TaskAllocationState):
    """Load error report from JSON file"""
    try:
        with open(state["error_report_path"], "r", encoding="utf-8") as f:
            error_data = json.load(f)
        return {"error_data": error_data}
    except Exception as e:
        return {"error_data": {}, "error": f"Failed to load error report: {str(e)}"}

def extract_tasks_from_reports(state: TaskAllocationState):
    """Extract individual tasks from complexity and error reports"""
    complexity_data = state.get("complexity_data", {})
    error_data = state.get("error_data", {})
    
    # Extract tasks from complexity report - one per file
    complexity_tasks = []
    for file_path, file_data in complexity_data.items():
        # Create a task for each file with complexity issues
        task = {
            "file_path": file_path,
            "complexity_data": file_data,
            "source": "complexity"
        }
        complexity_tasks.append(task)
    
    # Extract tasks from error report - one per file
    error_tasks = []
    for file_path, errors in error_data.items():
        # Create a task for each file with errors
        task = {
            "file_path": file_path,
            "error_data": errors,
            "source": "error"
        }
        error_tasks.append(task)
    
    # Combine all tasks
    all_tasks = complexity_tasks + error_tasks
    
    return {
        "complexity_tasks": complexity_tasks, 
        "error_tasks": error_tasks,
        "tasks": all_tasks,
        "current_task_index": 0,
        "is_processing_complete": False,
        "processed_tasks": []
    }

def get_next_task(state: TaskAllocationState):
    """Get the next task to process or signal completion"""
    tasks = state.get("tasks", [])
    current_index = state.get("current_task_index", 0)
    
    if current_index >= len(tasks):
        return {"is_processing_complete": True, "current_task": None}
    
    current_task = tasks[current_index]
    current_source = current_task.get("source", "")
    
    return {
        "current_task": current_task,
        "current_task_source": current_source,
        "current_task_index": current_index + 1  # Increment for next iteration
    }

def truncate_data(data: Any, max_chars: int = 6000) -> str:
    """Truncate data to stay within context limits"""
    data_str = json.dumps(data, indent=2)
    
    if len(data_str) <= max_chars:
        return data_str
    
    # For complex data, create a summarized version
    if isinstance(data, dict):
        summary = {
            "summary": f"Full data exceeds {max_chars} chars. Showing key information only.",
            "keys": list(data.keys()),
        }
        
        # Include some sample items if possible
        if len(data) > 0:
            sample_keys = list(data.keys())[:3]  # Take first 3 keys
            for key in sample_keys:
                summary[f"sample_{key}"] = data[key]
        
        return json.dumps(summary, indent=2)
    
    elif isinstance(data, list):
        summary = {
            "summary": f"Full data exceeds {max_chars} chars. Showing partial information.",
            "total_items": len(data),
            "samples": data[:3] if len(data) > 0 else []  # Take first 3 items
        }
        return json.dumps(summary, indent=2)
    
    # For simple strings, just truncate
    return data_str[:max_chars] + "... [truncated]"

def process_task(state: TaskAllocationState):
    """Process a single task using the appropriate agent based on task source"""
    current_task = state.get("current_task", {})
    current_source = state.get("current_task_source", "")
    repo_path = state.get("repo_path", "")
    
    if not current_task or not repo_path:
        return {"processed_tasks": []}
    
    try:
        # Prepare data for the agent based on task source
        file_path = current_task.get("file_path", "")
        
        if current_source == "complexity":
            complexity_data = current_task.get("complexity_data", {})
            # Truncate data to avoid context length issues
            complexity_str = truncate_data(complexity_data)
            task_type = "complexity"
            fragments = f"Complexity Report for {file_path}:\n{complexity_str}"
            
        elif current_source == "error":
            error_data = current_task.get("error_data", {})
            # Truncate data to avoid context length issues
            error_str = truncate_data(error_data)
            task_type = "error"
            fragments = f"Error Report for {file_path}:\n{error_str}"
            
        else:
            return {"processed_tasks": [], "error": f"Unknown task source: {current_source}"}
        
        # Create a concise prompt with essential info only
        concise_prompt = f"""
Please analyze the following {task_type} report for file: {file_path} in repository: {repo_path}
and create appropriate tasks to address the issues.

Key information:
{fragments}

For each issue identified, create a task with:
- task name
- priority (0-10 scale)
- problem description
- specification of work needed
- affected code file
- line numbers (if available)
"""
        
        # Load agent configuration
        agents_config = load_agent_config()
        
        # Invoke TaskAllocationAgent for the task
        result = TaskAllocationAgent.invoke({
            "messages": [
                {"role": "user", "content": concise_prompt},
            ],
        })
        
        # Extract task details from LLM response
        response_content = ""
        
        # Try different ways to access the content based on the AIMessage structure
        try:
            # If using LangChain messages structure
            if hasattr(result, "messages") and result.messages:
                response_content = result.messages[-1].content
            # If using the dictionary structure
            elif isinstance(result, dict) and "messages" in result:
                last_message = result["messages"][-1]
                if isinstance(last_message, dict) and "content" in last_message:
                    response_content = last_message["content"]
                elif hasattr(last_message, "content"):
                    response_content = last_message.content
            # Direct content access
            elif hasattr(result, "content"):
                response_content = result.content
        except Exception as e:
            print(f"Error extracting content from AI response: {str(e)}")
            return {"processed_tasks": [], "error": f"Failed to extract content from AI response: {str(e)}"}
        
        # Parse tasks from the response
        tasks = parse_tasks_from_response(response_content)
        
        # Add source information and file path to processed tasks
        for task in tasks:
            task["source"] = current_source
            if "code_file" not in task:
                task["code_file"] = file_path
        
        return {"processed_tasks": tasks}
        
    except Exception as e:
        print(f"Error processing task: {str(e)}")
        # Return empty result but don't stop the process
        return {"processed_tasks": [], "error": f"Error processing task: {str(e)}"}

def parse_tasks_from_response(response_content: str) -> List[Dict]:
    """Parse tasks from LLM response in the format:
    [Task 1]
      name: название задачи
      priority: 9.4
      problem: объяснение ошибки
      specification: техническое задание
      code_file: путь до файла
      rows: 1-15
      author: Имя Фамилия
    """
    tasks = []
    
    # Try parsing as JSON first
    try:
        if response_content.strip().startswith("[") and response_content.strip().endswith("]"):
            return json.loads(response_content)
    except json.JSONDecodeError:
        pass
    
    # Parse using task block pattern
    task_pattern = r'\[Task \d+\](.*?)(?=\[Task \d+\]|$)'
    task_blocks = re.findall(task_pattern, response_content, re.DOTALL)
    
    for block in task_blocks:
        task = {}
        lines = block.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Match key-value pairs
            match = re.match(r'\s*([a-zA-Z_]+)\s*:\s*(.*)', line)
            if match:
                key, value = match.groups()
                key = key.strip()
                value = value.strip()
                
                # Convert priority to float
                if key == "priority":
                    try:
                        task[key] = float(value)
                    except ValueError:
                        task[key] = 0.0
                else:
                    task[key] = value
        
        if task:
            tasks.append(task)
    
    return tasks

def check_processing_status(state: TaskAllocationState) -> str:
    """Determine next step based on processing status"""
    is_complete = state.get("is_processing_complete", False)
    
    if is_complete:
        return "complete"
    else:
        return "continue"

def save_processed_tasks(state: TaskAllocationState):
    """Sort tasks by priority and save to JSON file"""
    processed_tasks = state.get("processed_tasks", [])
    output_path = state.get("output_tasks_path", "")
    storage_dir = state.get("storage_dir", "")
    repo_name = state.get("repo_name", "")
    
    # Sort tasks by priority in descending order
    sorted_tasks = sorted(processed_tasks, key=lambda x: x.get("priority", 0), reverse=True)
    
    # Save tasks to JSON file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sorted_tasks, f, ensure_ascii=False, indent=4)
    except Exception as e:
        return {"error": f"Failed to save tasks: {str(e)}"}
    
    # Create directory for task specifications
    tasks_dir = os.path.join(storage_dir, repo_name, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    
    # Save individual task specifications as markdown files
    for i, task in enumerate(sorted_tasks):
        task_name = task.get("name", f"task_{i+1}")
        task_name = task_name.replace(" ", "_").replace("/", "_").lower()
        specification = task.get("specification", "")
        
        try:
            with open(os.path.join(tasks_dir, f"{task_name}.md"), "w", encoding="utf-8") as f:
                f.write(specification)
        except Exception as e:
            print(f"Error saving task specification for {task_name}: {str(e)}")
    
    return {"final_tasks": sorted_tasks}

def build_task_allocation_workflow():
    """Build the task allocation workflow graph with task-by-task processing"""
    builder = StateGraph(TaskAllocationState)
    
    # Add nodes
    builder.add_node("load_complexity_report", load_complexity_report)
    builder.add_node("load_error_report", load_error_report)
    builder.add_node("extract_tasks", extract_tasks_from_reports)
    builder.add_node("get_next_task", get_next_task)
    builder.add_node("process_task", process_task)
    builder.add_node("save_processed_tasks", save_processed_tasks)
    
    # Set entry points and initial flow
    builder.set_entry_point("load_complexity_report")
    builder.add_edge("load_complexity_report", "load_error_report")
    builder.add_edge("load_error_report", "extract_tasks")
    builder.add_edge("extract_tasks", "get_next_task")
    
    # Add conditional branch based on processing status
    builder.add_conditional_edges(
        "get_next_task",
        check_processing_status,
        {
            "continue": "process_task",
            "complete": "save_processed_tasks"
        }
    )
    
    # Create loop for task processing
    builder.add_edge("process_task", "get_next_task")
    
    # Set finish point
    builder.set_finish_point("save_processed_tasks")
    
    return builder.compile()

task_allocation_graph = build_task_allocation_workflow()