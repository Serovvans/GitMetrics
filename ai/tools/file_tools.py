from pathlib import Path

class FileEnumerator:
    def run(self, path: str) -> list[str]:
        extensions = {'.py', '.js', '.java', '.go'}
        base_path = Path(path)
        return [
            str(p.relative_to(base_path))
            for p in base_path.rglob('*.*')
            if p.suffix in extensions and p.is_file()
        ]

class FileReader:
    def run(self, file_path: str) -> str:
        with open(file_path, 'r') as f:
            return f.read()