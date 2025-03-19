from langchain_core.tools import tool
import subprocess
import os
import json
import tempfile

@tool
def sonarqube_analysis(code_path: str) -> str:
    """
    Analyzes code using SonarQube and returns the results in a structured format
    
    Args:
        code_path (str): Path to the source code file
    
    Returns:
        str: String with analysis results
    """
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.properties') as f:
            properties_file = f.name
            f.write(f"""
sonar.projectKey=file_analysis
sonar.projectName=File Analysis
sonar.projectVersion=1.0
sonar.sources={os.path.dirname(code_path)}
sonar.sourceEncoding=UTF-8
sonar.language={get_language_from_file(code_path)}
sonar.login=your_sonar_token
            """)
        
        result = subprocess.run([
            'sonar-scanner',
            f'-Dproject.settings={properties_file}'
        ], capture_output=True, text=True, timeout=60)
        
        os.unlink(properties_file)
        
        if result.returncode != 0:
            return f"SonarQube analysis failed: {result.stderr}"
        
        return analyze_code_basic(code_path)
    except Exception as e:
        return f"Error during analysis: {str(e)}"


def get_language_from_file(file_path: str) -> str:
    """Determine the programming language from the file extension"""
    ext = os.path.splitext(file_path)[1].lower()
    language_map = {
        '.py': 'python',
        '.js': 'js',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'cs',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php',
        '.ts': 'typescript'
    }
    return language_map.get(ext, 'python')


def analyze_code_basic(file_path: str) -> str:
    """
    Perform a basic code analysis when SonarQube is not available
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        issues = []
        
        for i, line in enumerate(lines):
            if len(line) > 100:
                issues.append({
                    "line": i + 1,
                    "message": "Line exceeds 100 characters",
                    "severity": "MINOR"
                })
        
        for i, line in enumerate(lines):
            if "TODO" in line:
                issues.append({
                    "line": i + 1,
                    "message": "TODO comment found",
                    "severity": "INFO"
                })
        
        lines_with_def = [i for i, line in enumerate(lines) if line.strip().startswith('def ')]
        for i in range(len(lines_with_def) - 1):
            func_length = lines_with_def[i+1] - lines_with_def[i]
            if func_length > 30:
                issues.append({
                    "line": lines_with_def[i] + 1,
                    "message": f"Function appears to be {func_length} lines long, consider refactoring",
                    "severity": "MAJOR"
                })
        
        analysis_result = {
            "file": file_path,
            "issues": issues,
            "metrics": {
                "lines": len(lines),
                "functions": len(lines_with_def),
                "issues": len(issues)
            }
        }
        
        return json.dumps(analysis_result, indent=2)
    except Exception as e:
        return f"Basic analysis failed: {str(e)}"
