import os
import subprocess
import json
import re
from dotenv import load_dotenv

import time
from openai import RateLimitError

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.chat_models.base import BaseChatModel

# Initialize the prompt templates
from prompt_template import (
    SQL_SECURITY_REVIEW_PROMPT,
    INPUT_VALIDATION_PROMPT,
    EVALUATION_SUMMARY_PROMPT_TEMPLATE,
    RISK_SCORE_ASSIGNER,
    REACT_AGENT_PROMPT_TEMPLATE,
    CODE_REFACTORING_PROMPT
)


from dotenv import load_dotenv
load_dotenv()

model_name = "openai/gpt-oss-120b"
temperature = 0.01

llm = ChatGroq(
    model_name=model_name,
    temperature=temperature,
    max_tokens=None,
    groq_api_key=os.environ["GROQ_API_KEY"],
    timeout=60
)

def enforce_rate_limit(messages):
    while True:
        try:
            return (
                llm.invoke(messages)
            )
        except RateLimitError as e:
            print("Rate limit reached. Waiting 60 seconds...")
            time.sleep(60)

def _get_code_with_lines(code_content: str) -> str:
    lines = code_content.splitlines()
    return "\n".join(f"{i+1:04d}: {line}" for i, line in enumerate(lines))


def apply_code_changes(code_script, issue_list, llm):
    """
    Apply markdown suggestions to base code and return updated code.
    Handles JSON decode errors gracefully.
    """

    CODE_REFACTORING_PROMPT_1 = CODE_REFACTORING_PROMPT.format(
        code_script=code_script,
        issue_list=(json.dumps(issue_list, indent=2))
    )
    review_messages = [HumanMessage(content=CODE_REFACTORING_PROMPT_1)]
    refactored_parsed_review = []
    try:

        # response = llm.invoke(review_messages)
        response = enforce_rate_limit(review_messages)
        review_str = response.content.strip()

        if review_str.startswith("```json"):
            review_str = review_str[7:]
        if review_str.endswith("```"):
            review_str = review_str[:-3]

        refactored_parsed_review = json.loads(review_str.strip())

        return refactored_parsed_review

    except json.JSONDecodeError as json_err:
        raise
    except Exception as e:
        raise

def pull_refactored_code(filename, scored_issues):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        raise

    try:
        code_with_lines = _get_code_with_lines(code_content)
    except Exception as e:
        raise

    try:
        refactored_code_list = apply_code_changes(
            code_script=code_with_lines,
            issue_list=scored_issues,
            llm=llm
        )
        return refactored_code_list
    except Exception as e:
        raise


def bandit_run(filename):
    try:
        # Define a mapping for severity to a 1-10 score
        BANDIT_SEVERITY_MAP = {
            'LOW': "Minor",
            'MEDIUM': "Moderate",
            'HIGH': "Critical"
        }
        all_issues = []
        command = ["bandit", "-f", "json", filename]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode > 1 and result.stderr:
            print(f"[Bandit] Error during execution: {result.stderr.strip()}")
            errors.append(f"[Bandit] Error during execution: {result.stderr.strip()}")

        data = json.loads(result.stdout)
        issues = data.get("results", [])
        report = [f"Bandit found {len(issues)} issue(s):"]
        for issue in issues:
            severity = issue.get('issue_severity', 'UNDEFINED')
            line = issue.get('line_number')
            issue_text = issue.get('issue_text')
            all_issues.append(
                {
                    "source": "bandit",
                    "start_line_number": line,
                    "end_line_number": line,
                    "severity": BANDIT_SEVERITY_MAP.get(severity),
                    "original_python_script": issue.get('code'),
                    "issue_summary": issue_text
                }
            )
        return all_issues
    except json.JSONDecodeError:
        raise
    except FileNotFoundError:
        raise
    except Exception as e:
        raise


def detect_secrets_run(filename):
    ### --- Layer 2: Run detect-secrets for hardcoded secrets ---
    try:
        all_issues = []
        secrets_command = ["detect-secrets", "scan", filename]
        secrets_result = subprocess.run(secrets_command, capture_output=True, text=True)

        # Log stderr for debugging, as it can contain useful info
        if secrets_result.stderr:
            print(f"[Debug] detect-secrets stderr: {secrets_result.stderr.strip()}")

        if secrets_result.stdout:
            secrets_data = json.loads(secrets_result.stdout)
            # The results are keyed by filename in the JSON output
            results_by_file = secrets_data.get("results", {})
            for file_path, findings in results_by_file.items():
                for secret in findings:
                    all_issues.append({
                        "source": "detect-secrets",
                        "start_line_number": secret.get('line_number'),
                        "end_line_number": secret.get('line_number'),
                        "original_python_script": secret.get('hashed_secret'),
                        "severity": "CRITICAL",  # Hardcoded secrets are always critical
                        "issue_summary": f"Potential hardcoded secret detected: {secret.get('type')}"
                    })
            return all_issues
    except json.JSONDecodeError:
        raise
    except FileNotFoundError:
        raise
    except Exception as e:
        raise


def input_validation_sanitization_python(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code_content = f.read()

    except Exception as e:
        raise
    try:
        code_with_lines = _get_code_with_lines(code_content)
    except Exception as e:
        raise

    INPUT_VALIDATION_PROMPT_1 = INPUT_VALIDATION_PROMPT.format(code_with_lines=code_with_lines)
    messages = [HumanMessage(content=INPUT_VALIDATION_PROMPT_1)]

    try:
        # response = llm.invoke(messages)
        response = enforce_rate_limit(messages)
        review_str = response.content.strip()

        # Strip code block markers if present
        if review_str.startswith("```json"):
            review_str = review_str[7:]
        if review_str.endswith("```"):
            review_str = review_str[:-3]

        parsed_review = json.loads(review_str.strip())

        if not isinstance(parsed_review, list):
            raise Exception

        return parsed_review

    except json.JSONDecodeError:
        raise

    except Exception as e:
        raise


@tool
def python_file_evaluator_security_compliance(filename: str) -> dict:
    """
    Analyze a Python file for security vulnerabilities using Bandit, detect-secrets,
    and input validation checks. Returns a structured dict with filename, evaluation score, summary, and detailed issues.
    """

    if not os.path.exists(filename):
        raise Exception

    all_issues = []
    scored_issues = []

    try:
        bandit_output = bandit_run(filename)
        secrets_output = detect_secrets_run(filename)
        all_issues = bandit_output + secrets_output
        for issue in all_issues:
            try:
                scored = assign_risk_score(issue, llm)
                scored_issues.append(scored)
            except Exception as score_err:
                raise Exception
                print(f"Error scoring issue: {score_err}")

        ##input validation
        try:
            input_issues = input_validation_sanitization_python(filename)
            scored_issues.extend(input_issues)
        except Exception as input_check_err:
            raise
            # print(f"Error running input validation: {input_check_err}")

        # evaluation score
    
        scores = [float(f['risk_score']) for f in scored_issues if 'risk_score' in f]
        evaluation_score = sum(scores) / len(scores) if scores else 8

        # Evaluation Summary
        try:
            if scored_issues:
                summary_prompt = EVALUATION_SUMMARY_PROMPT_TEMPLATE.format(
                    list_of_json_findings=json.dumps(scored_issues, indent=2)
                )
                summary_messages = [HumanMessage(content=summary_prompt)]
                # eval_response = llm.invoke(summary_messages)
                eval_response = enforce_rate_limit(summary_messages)
                evaluation_content = eval_response.content.strip()

                if evaluation_content.startswith("```json"):
                    evaluation_content = evaluation_content[7:]
                if evaluation_content.endswith("```"):
                    evaluation_content = evaluation_content[:-3]

                try:
                    summary_dict = json.loads(evaluation_content)
                    evaluation_issue_summary = summary_dict["evaluation_issue_summary"]
                    evaluation_refactor_summary = summary_dict["evaluation_refactor_summary"]
                except (json.JSONDecodeError, KeyError) as e:
                    print("Failed to parse evaluation summary:", e)
                    evaluation_issue_summary = "Parsing error: Unable to extract issue summary."
                    evaluation_refactor_summary = "Parsing error: Unable to extract refactor summary."
            else:
                evaluation_issue_summary = "No issues found while reviewing the code for Security compliance."
                evaluation_refactor_summary = "No refactor suggestions since the issues are not found while reviewing the code for Security compliance."
        except Exception as summary_exception:
            print(f"Error during evaluation summary generation: {summary_exception}")
            raise 

        list_contains_refactored_code = pull_refactored_code(filename, scored_issues)

        return {
            "filename": filename,
            "evaluation_score": evaluation_score,
            "evaluation_issue_summary": evaluation_issue_summary,
            "evaluation_refactor_summary": evaluation_refactor_summary,
            "evaluation_details": list_contains_refactored_code
        }

    except Exception as e:
        error_msg = f"Unexpected error during security evaluation: {str(e)}"
        raise


def assign_risk_score(issue: dict, llm: BaseChatModel):
    try:
        RISK_SCORE_ASSIGNER_1 = RISK_SCORE_ASSIGNER.format(
            issue_source=issue['source'],
            issue_start_line_number=issue['start_line_number'],
            issue_end_line_number=issue['end_line_number'],
            issue_original_python_script=issue['original_python_script'],
            issue_severity=issue['severity'],
            issue_summary_context=issue['issue_summary']

        )
        messages = [HumanMessage(content=RISK_SCORE_ASSIGNER_1)]
        # response = llm.invoke(messages)
        response = enforce_rate_limit(messages)
        review = response.content.strip()
        if review.startswith("```json"):
            review = review[7:]
        if review.endswith("```"):
            review = review[:-3]
        try:
            review = json.loads(review)
            review = review["risk_score"]
        except (json.JSONDecodeError, KeyError) as e:
            print("Failed to parse evaluation summary:", e)
            review = -1

        issue['risk_score'] = int(review)

    except (ValueError, TypeError) as e:
        print(f"  - WARNING: Could not parse score from LLM response '{review}'. Error: {e}")
        issue['risk_score'] = -1
        issue['score_error'] = f"Invalid LLM response: {review}"
    except Exception as e:
        print(f"  - WARNING: An unexpected error occurred during LLM call. Error: {e}")
        issue['risk_score'] = -1
        issue['score_error'] = f"LLM call failed: {e}"

    return issue


@tool
def sql_file_evaluator_security_compliance(filename: str) -> dict:
    """
    Use this tool to evaluate SQL (.sql) files for security best practices which include review checks for:
    - SQL Injection Prevention
    - File Path Sanitization
    - SQL Content Validation
    - No Hardcoded Secrets

    Returns a structured dict with filename, evaluation score, summary, and detailed issues.
    """
    #     print(f"--- [Tool Called] Running SQL Security Review on {filename} ---")

    if not os.path.exists(filename):
        raise Exception

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        raise Exception

    try:
        code_with_lines = _get_code_with_lines(code_content)
    except Exception as e:
        raise Exception

    try:
        SQL_SECURITY_REVIEW_PROMPT_1 = SQL_SECURITY_REVIEW_PROMPT.format(code_with_lines=code_with_lines)
        messages = [HumanMessage(content=SQL_SECURITY_REVIEW_PROMPT_1)]

        # response = llm.invoke(messages)
        response = enforce_rate_limit(messages)
        review_str = response.content.strip()

        # Clean code block if wrapped
        if review_str.startswith("```json"):
            review_str = review_str[7:]
        if review_str.endswith("```"):
            review_str = review_str[:-3]

        parsed_review = json.loads(review_str.strip())

        if not isinstance(parsed_review, list):
            raise Exception

        # Calculate average score from parsed issues
        scores = [float(f['score']) for f in parsed_review if 'score' in f]
        evaluation_score = sum(scores) / len(scores) if scores else None

        # Generate evaluation summary
        try:
            if parsed_review:
                summary_prompt = EVALUATION_SUMMARY_PROMPT_TEMPLATE.format(
                    list_of_json_findings=json.dumps(parsed_review, indent=2)
                )
                summary_messages = [HumanMessage(content=summary_prompt)]
                # eval_response = llm.invoke(summary_messages)
                eval_response = enforce_rate_limit(summary_messages)
                evaluation_content = eval_response.content.strip()

                if evaluation_content.startswith("```json"):
                    evaluation_content = evaluation_content[7:]
                if evaluation_content.endswith("```"):
                    evaluation_content = evaluation_content[:-3]

                try:
                    summary_dict = json.loads(evaluation_content)
                    evaluation_issue_summary = summary_dict["evaluation_issue_summary"]
                    evaluation_refactor_summary = summary_dict["evaluation_refactor_summary"]
                except (json.JSONDecodeError, KeyError) as e:
                    print("Failed to parse evaluation summary:", e)
                    evaluation_issue_summary = "Parsing error: Unable to extract issue summary."
                    evaluation_refactor_summary = "Parsing error: Unable to extract refactor summary."
            else:

                evaluation_issue_summary = "No issues found while reviewing the code for Security compliance."
                evaluation_refactor_summary = """No refactor suggestions since the issues are not found while reviewing the code for Security compliance."""
        except Exception as summary_exception:
            raise
        #             evaluation_issue_summary = ""
        #             evaluation_refactor_summary = ""
        #             print(f"Error during evaluation summary generation: {summary_exception}")

        list_contains_refactored_code = pull_refactored_code(filename, parsed_review)
        #         print("##list_contains_refactored_code##",list_contains_refactored_code)

        return {
            "filename": filename,
            "evaluation_score": evaluation_score,
            "evaluation_issue_summary": evaluation_issue_summary,
            "evaluation_refactor_summary": evaluation_refactor_summary,
            "evaluation_details": list_contains_refactored_code
        }

    except json.JSONDecodeError:
        raise Exception
    except Exception as e:
        raise Exception


def run_security_compliance_agent(file_path: str):
    """Main function to scan a directory and run the security agent on each file."""

    print(f"--- Starting Security Compliance Review on the file : {file_path} ---")

    agent_prompt = PromptTemplate.from_template(REACT_AGENT_PROMPT_TEMPLATE)
    tools = [python_file_evaluator_security_compliance, sql_file_evaluator_security_compliance]
    dry_modularity_agent = create_react_agent(llm, tools, agent_prompt)
    agent_executor = AgentExecutor(
        agent=dry_modularity_agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        return_intermediate_steps=True)  # Add this    )

    try:
        response = agent_executor.invoke({"input": f"Analyze the file: {file_path}"})
    except Exception as e:
        print(f"failed to invoke security agent due to {e}")
        return []

    if response.get("intermediate_steps"):
        try:
            _, tool_direct_output = response["intermediate_steps"][-1]
            print(f"--- Ending Security Compliance Reviewing on the file : {file_path} ---")
            return tool_direct_output

        except Exception as eval_error:
            return []

    return total_review_list