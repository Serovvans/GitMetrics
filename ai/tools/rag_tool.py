import os
import git
import tempfile

from typing import List
from langchain_core.tools import tool
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from huggingface_hub import login

from typing import List
from langchain_core.tools import tool
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import os

@tool
def retrieve_context(query: str, vector_db_path: str) -> List[str]:
    """
    Автоматически находит и извлекает релевантный контекст из векторной БД
    
    Args:
        query: Поисковый запрос
        vector_db_path: Путь к векторной БД
        
    Returns:
        Релевантные фрагменты контекста
    """
    # Инициализируем эмбеддинг-функцию
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={'device': 'mps'},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    # Загружаем базу данных с эмбеддинг-функцией
    db = Chroma(
        persist_directory=vector_db_path,
        embedding_function=embeddings  # Добавляем эмбеддинг-функцию
    )
    
    # Выполняем поиск
    docs = db.similarity_search(query, k=20)
    
    # Фильтрация и обработка результатов
    unique_sources = set()
    filtered_docs = []
    
    for doc in docs:
        source = doc.metadata.get("source", "")
        if source not in unique_sources:
            unique_sources.add(source)
            filtered_docs.append(doc)
    
    return [doc.page_content for doc in filtered_docs[:15]]


def initialize_vector_db_from_github(repo_url: str, storage_base_path: str = "storage"):
    """
    Initialize a Chroma vector database with repository files from GitHub using language-specific text splitters.
    
    Args:
        repo_url: URL of the GitHub repository
        output_db_path: Path where the vector database will be stored
        github_token: GitHub personal access token (optional)
    """
    # Create temporary directory for cloning
    tmp_dir = tempfile.mkdtemp()
    
    try:
        # Clone the repository
        print(f"Cloning repository from {repo_url}...")
        repo = git.Repo.clone_from(repo_url, tmp_dir)
        
        # Login to HuggingFace
        login(token=os.getenv("HF_TOKEN"))
        
        # Initialize embeddings model (optimized for multilingual semantic similarity)
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={'device': 'mps', 'trust_remote_code': True},
            encode_kwargs={'normalize_embeddings': True}  # For cosine similarity
        )
        
        # Create the default text splitter for non-code files
        default_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Map file extensions to language-specific splitters
        language_map = {
            ".py": Language.PYTHON,
            ".js": Language.JS,
            ".jsx": Language.JS,
            ".ts": Language.TS,
            ".tsx": Language.TS,
            ".java": Language.JAVA,
            ".cpp": Language.CPP,
            ".c": Language.CPP,
            ".cs": Language.CSHARP,
            ".go": Language.GO,
        }
        
        repo_name = repo_url.strip('/').split('/')[-1].replace('.git', '')
    
        output_db_path = os.path.join(storage_base_path, repo_name, "vectore_store")
        os.makedirs(output_db_path, exist_ok=True)
        
        db = Chroma(persist_directory=output_db_path, embedding_function=embeddings)
        
        # Process all files in the repository
        repo_path = Path(tmp_dir)
        
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
                
            if any(part.startswith('.') for part in file_path.parts):
                continue
                
            try:
                # Skip binary files and very large files
                if file_path.stat().st_size > 1_000_000:  # Skip files larger than 1MB
                    print(f"Skipping large file: {file_path.relative_to(repo_path)}")
                    continue
                    
                # Select the appropriate splitter based on file extension
                file_ext = file_path.suffix.lower()
                
                loader = TextLoader(str(file_path), encoding='utf-8')
                documents = loader.load()
                
                # Add relative path as metadata
                for doc in documents:
                    doc.metadata["source"] = str(file_path.relative_to(repo_path))
                    doc.metadata["file_type"] = file_ext.lstrip('.')
                    doc.metadata["repo_url"] = repo_url
                
                # Use language-specific splitter if available
                if file_ext in language_map:
                    language = language_map[file_ext]
                    splitter = RecursiveCharacterTextSplitter.from_language(
                        language=language,
                        chunk_size=400,
                        chunk_overlap=100
                    )
                    print(f"Using {language.name} splitter for {file_path.relative_to(repo_path)}")
                    splits = splitter.split_documents(documents)
                else:
                    splits = default_splitter.split_documents(documents)
                
                db.add_documents(splits)
                
                print(f"Added {file_path.relative_to(repo_path)} to the vector database")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        
        db.persist()
        print(f"Vector database initialized at {output_db_path}")
        return db
    
    finally:
        # Clean up temporary directory
        import shutil
        try:
            shutil.rmtree(tmp_dir)
            print(f"Cleaned up temporary directory: {tmp_dir}")
        except Exception as e:
            print(f"Error cleaning up temporary directory: {e}")
            