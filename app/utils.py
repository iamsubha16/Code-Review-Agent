import os
import shutil
from app.config import UPLOAD_DIR

def load_code_from_file(file_path: str) -> str:
    """
    Load code content from a file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def clear_uploaded_files():
    """Clear the contents of the UPLOAD_DIR."""
    try:
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
    except Exception as e:
        print(f"Error clearing files: {e}")
        raise Exception(f"Error clearing files: {e}")

def ensure_directories_exist():
    """Ensure required directories exist."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)