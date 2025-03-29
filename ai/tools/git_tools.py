
from typing import Annotated
import subprocess
import re
from langchain_core.tools import tool


@tool
def get_code_author(
    file_path: Annotated[str, "Путь к файлу, автора строк которого нужно найти"],
    start_line: Annotated[int, "Индекс первой строки, от которой начинается фрагмент, автора которого нужно найти"],
    end_line: Annotated[int, "Индекс последней строки, где заканчивается фрагмент, автора которого нужно найти"],
    repo_path: Annotated[str, "Путь к репозиторию, в котором ищется автор"]
) -> Annotated[str, "Автор, внёсший последние изменения в заданный фрагмент кода"]:
    """
    Найти автора последнего изменения для указанного диапазона строк.

    Аргументы:
    - file_path: Путь к файлу
    - start_line: Индекс первой строки
    - end_line: Индекс последней строки
    - repo_path: Путь к репозиторию, в котором ищется автор

    Возвращает автора, последним вносившим изменения.

    """

    if start_line < 1:
        start_line = 1  # git blame использует 1-индексацию (0 строки НЕТ!)

    try:
        result = subprocess.run(
            ["git", "blame", "-L", f"{start_line},{end_line}", "--porcelain", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        # Ищем автора в выводе git blame
        last_author = None
        for line in result.stdout.split("\n"):
            match = re.match(r"^author (.+)", line)
            if match:
                last_author = match.group(1)

        return last_author if last_author else "Автор не найден"
    
    except subprocess.CalledProcessError as e:
        return f"Ошибка выполнения git blame: {e}"
