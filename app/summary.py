import time
from typing import List
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from openai import RateLimitError
from app.config import MODEL_NAME, TEMPERATURE, GROQ_API_KEY, LLM_TIMEOUT


def initialize_llm():
    """Initialize the LLM client with configuration from config.py"""
    return ChatGroq(
        model_name=MODEL_NAME,
        temperature=TEMPERATURE,
        max_tokens=None,
        groq_api_key=GROQ_API_KEY,
        timeout=LLM_TIMEOUT
    )


def enforce_rate_limit(llm, messages: List[HumanMessage]):
    """
    Enforce rate limiting for LLM API calls with retry logic.
    """
    while True:
        try:
            return llm.invoke(messages)
        except RateLimitError as e:
            print("Rate limit reached. Waiting 60 seconds...")
            time.sleep(60)


def issue_summary_generation_prompt(topic: str, summary_text: str) -> str:
    """Generate prompt for issue summary generation."""
    return f"""
    You are a highly skilled code quality analysis assistant.

    Your task is to generate a clear, concise, and insightful **overall summary** for a software repository, focused specifically on the topic: **{topic}**.

    You are provided with a collection of **raw code review issues** which are extracted from individual files or modules related to this topic:
    ------------------------
    {summary_text}
    ------------------------

    Please analyze the issues and synthesize the key patterns, recurring violations, and critical observations related to **{topic}**. Your summary should:

    1. Highlight only the most significant or frequent types of issues found in the input.
    2. Identify common trends, such as repeated bad practices or patterns of neglect.
    3. Emphasize any critical or high-severity issues that require urgent remediation. Be specific where possible.
    4. Highlight major concerns only. Do not comment on what needs to be changed.
    5. Maintain a professional, concise, and objective tone.

    Return only the final textual summary. Do not repeat or restate the raw input. Do not format your response as a list or dictionary — only provide a well-written paragraph.
    """


def refactor_summary_generation_prompt(topic: str, summary_text: str) -> str:
    """Generate prompt for refactor summary generation."""
    return f"""
    You are a highly skilled code quality analysis assistant.

    Your task is to generate a clear, concise, and insightful **refactoring summary** for a software repository, focused specifically on the topic: **{topic}**.

    You are provided with a list of summaries describing the **code changes that were done** in individual files or modules related to the topic: {topic}
    ------------------------
    {summary_text}
    ------------------------

    Please analyze the described changes and synthesize the key improvements, recurring refactor patterns, and overall impact of the modifications related to **{topic}**. Your summary should:

    1. Highlight the most important or impactful changes made across the codebase.
    2. Identify common refactoring patterns or trends (e.g., modularization, removal of duplication, performance improvements).
    3. Mention any changes that address critical or high-severity issues, if applicable.
    4. The 'summary_text' contains all the **changes made**.
    5. Do not mention what can be refactored, but only on what changes are actually made.
    6. Maintain a professional, concise, and objective tone.

    Return only the final textual summary. Do not repeat or restate the raw input. Do not format your response as a list or dictionary — only provide a well-written paragraph.
    """


def overall_issue_summary_generation_prompt(text_code_styling: str, text_dry_modularity: str, text_security: str) -> str:
    """Generate prompt for overall issue summary across all categories."""
    return f"""You are a code quality analysis assistant.

You are given three issue summaries highlighting problems identified in a codebase, each focusing on a different aspect:
1. Code Styling — formatting inconsistencies, naming violations, and readability issues.
2. DRY and Modularity — code duplication, poor abstraction, and lack of reuse.
3. Security Compliance — unsafe practices, vulnerabilities, and deviations from security best practices.

Each summary is provided below. Your task is to:
- Carefully review the three issue summaries.
- Synthesize and interpret the most important insights across all three areas.
- Identify critical patterns, recurring violations, or any systemic problems affecting code quality.
- Write a **concise, high-level summary** that reflects the overall quality and areas needing improvement.
- Do **not** copy or restate the full summaries; focus on generating a holistic assessment of the issues only, do not suggest any changes.

Return only the summary text. Do not include any formatting, lists, or metadata — just plain text.

---

**Code Styling Issues Summary:**
{text_code_styling}

**DRY & Modularity Issues Summary:**
{text_dry_modularity}

**Security Compliance Issues Summary:**
{text_security}
"""


def overall_refactor_summary_generation_prompt(text_code_styling: str, text_dry_modularity: str, text_security: str) -> str:
    """Generate prompt for overall refactor summary across all categories."""
    return f"""You are a code quality analysis assistant.

You are given summaries describing refactoring changes made to a code repository, grouped into three key areas:
1. Code Styling — improvements related to formatting, naming conventions, readability, and consistency.
2. DRY and Modularity — changes addressing code duplication, abstraction, reuse, and structural modularity.
3. Security Compliance — enhancements targeting security risks, vulnerabilities, and adherence to best practices.

Each summary below describes the changes that have already been made. Your task is to:
- Read and analyze the three refactoring summaries carefully.
- Synthesize and interpret the overall improvements to the codebase.
- Identify recurring patterns or themes across the changes.
- Write a **concise, high-level summary** of how the refactoring has improved the codebase.
- Emphasize the overall impact on maintainability, readability, structure, and security.

Return only the final summary text — do not include lists, formatting, or restate the input directly.

---

**Code Styling Refactoring Summary:**
{text_code_styling}

**DRY & Modularity Refactoring Summary:**
{text_dry_modularity}

**Security Compliance Refactoring Summary:**
{text_security}
"""


def generate_overall_issue_summary(topic: str, summary_text: List[str]) -> str:
    """
    Generate an overall issue summary for a specific topic.
    """
    llm = initialize_llm()
    combined_prompt = issue_summary_generation_prompt(topic, summary_text)
    messages = [HumanMessage(content=combined_prompt)]
    response = enforce_rate_limit(llm, messages)
    return response.content


def generate_overall_refactor_summary(topic: str, summary_text: List[str]) -> str:
    """
    Generate an overall refactor summary for a specific topic.
    """
    llm = initialize_llm()
    combined_prompt = refactor_summary_generation_prompt(topic, summary_text)
    messages = [HumanMessage(content=combined_prompt)]
    response = enforce_rate_limit(llm, messages)
    return response.content


def generate_overall_repo_issue_summary(text1: str, text2: str, text3: str) -> str:
    """
    Generate an overall repository-level issue summary across all categories.
    """
    llm = initialize_llm()
    combined_prompt = overall_issue_summary_generation_prompt(text1, text2, text3)
    messages = [HumanMessage(content=combined_prompt)]
    response = enforce_rate_limit(llm, messages)
    return response.content


def generate_overall_repo_refactor_summary(text1: str, text2: str, text3: str) -> str:
    """
    Generate an overall repository-level refactor summary across all categories.
    """
    llm = initialize_llm()
    combined_prompt = overall_refactor_summary_generation_prompt(text1, text2, text3)
    messages = [HumanMessage(content=combined_prompt)]
    response = enforce_rate_limit(llm, messages)
    return response.content