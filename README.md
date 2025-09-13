# 🤖 AI Code Reviewer – Gradio Interface

This project provides an **AI-powered automated code reviewer** that checks uploaded source code files for:

- **Code Style & Consistency** (via `CodeStyle.py`)
- **DRY & Modularity** (via `DRY.py`)
- **Security Compliance** (via `Security.py`)

It offers an interactive **Gradio UI** where users can upload multiple Python files, review them automatically, and download a structured **Excel report**.

---

## 📂 Project Structure

```
ReviewAgents/
│── CodeStyle.py       # Agent for code style & consistency checks
│── DRY.py             # Agent for modularity & DRY checks
│── Security.py        # Agent for security checks
Gradio_AICodeReviewer.ipynb  # Main notebook with Gradio UI
uploaded_folder_gradio/      # Temporary folder for uploaded files
ai_code_review_reports/      # Stores generated Excel reports
```

---

## ⚙️ Features

- **Gradio-based interface** for uploading & reviewing files.
- Supports **multiple file uploads** in one session.
- Each review covers:
  - Repository-level insights
  - File-level findings
  - Line-level issues with suggested fixes
- **Excel reports** with 3 sheets:
  - **Repository-Level Report**
  - **File-Level Report**
  - **Line-Level Report**
- Reports include **scores, comments, and recommendations**.
- Uploaded files are **deleted automatically** after processing.

---

## 📊 Output Example

Each review generates an Excel file inside `ai_code_review_reports/`, structured as:

1. **Repository-Level Report** → Overall project health, key risks, and compliance.  
2. **File-Level Report** → File-wise issues, modularity, maintainability scores.  
3. **Line-Level Report** → Specific code line issues, suggested fixes, security vulnerabilities.  

---

## 🛠️ Requirements

Install the required dependencies:

```bash
pip install pydantic langchain langchain_groq langchain-core langgraph python-dotenv bandit detect-secrets gradio pandas openpyxl XlsxWriter pylint openai
```

> ✅ `datetime` is part of Python’s standard library, no need to install separately.  

---

## 🚀 Usage

1. **Clone this repository**  
   ```bash
   git clone https://github.com/your-username/ai-code-reviewer.git
   cd ai-code-reviewer
   ```

2. **Install dependencies** (see above).

3. **Run the notebook**  
   Open `Gradio_AICodeReviewer.ipynb` in Jupyter/VS Code and execute the cells.

4. **Upload your files**  
   - Drag & drop Python files into the Gradio interface.  
   - Files are saved temporarily in `uploaded_folder_gradio/`.

5. **Get your report**  
   - Processed results are saved in `ai_code_review_reports/` as an Excel file.  
   - Uploaded files are **auto-deleted** after review.  

---

## 🔐 Security Tools Used

- **Bandit** → Detects common Python security issues.  
- **Detect-Secrets** → Identifies hardcoded secrets and credentials.  
- **Pylint** → Ensures PEP8 compliance and code quality.  

---

## 🧩 Agents Overview

- `CodeStyle.py` → Linting, naming conventions, formatting, docstrings.  
- `DRY.py` → Repetition detection, modularity improvements, refactoring suggestions.  
- `Security.py` → Security compliance, secret detection, vulnerability scanning.  

---

## 📌 Notes

- Reports are generated in **Excel format** (`.xlsx`) for easy sharing.  
- Supports **multiple file uploads** per run.  
- Designed for **extensibility** → You can add new agents inside `ReviewAgents/`.

---

## 📄 License

MIT License – feel free to use, modify, and share.  

---

## 🙌 Acknowledgements

- [LangChain](https://www.langchain.com/)  
- [Gradio](https://gradio.app/)  
- [Bandit](https://bandit.readthedocs.io/)  
- [Detect-Secrets](https://github.com/Yelp/detect-secrets)  
- [Pylint](https://pylint.pycqa.org/)  
