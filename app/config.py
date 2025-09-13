import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM Configuration
MODEL_NAME = "openai/gpt-oss-120b"
TEMPERATURE = 0.01
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
LLM_TIMEOUT = 60

# File and Directory Configuration
UPLOAD_DIR = "uploaded_folder_gradio"
OUTPUT_DIR = "ai_code_review_reports"
SUPPORTED_EXTENSIONS = ['.py', '.sql']

# UI Configuration
APP_TITLE = "🧠 AI Code Review Report Generator"
APP_DESCRIPTION = "Upload `.py` or `.sql` files. Run code quality agents, then export the report."

# Global storage for review results
codeStyle_file_level_review_list = []
dry_file_level_review_list = []
security_file_level_review_list = []

codeStyle_line_level_review_list = []
dry_line_level_review_list = []
security_line_level_review_list = []