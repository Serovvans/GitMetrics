from git import Repo

class GitCloner:
    def run(self, url: str, path: str) -> str:
        Repo.clone_from(url, path)
        return path