# Imports
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

# Initialize the prompt templates
from prompt_template import (
    SQL_CODE_REVIEW_PROMPT_TEMPLATE,
    DRY_MODULARITY_REVIEW_PROMPT,
    DRY_REACT_AGENT_PROMPT_TEMPLATE,
    EVALUATION_SUMMARY_PROMPT_TEMPLATE,
    CODE_REFACTORING_PROMPT
)

from dotenv import load_dotenv
load_dotenv()

model_name = "llama-3.3-70b-versatile"
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

        response = llm.invoke(review_messages)
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


@tool
def python_file_evaluator_dry_review(file_path: str) -> dict:
    """
    Analyze a Python file for DRY, modularity, reusable utilities, and config practices.
    Returns structured evaluation results including scores and summary.
    """

    parsed_review = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        error_msg = f"Error reading file {file_path}: {str(e)}"
        raise Exception

    try:
        code_with_lines = _get_code_with_lines(code_content)
    except Exception as e:
        error_msg = f"Error generating line-numbered code: {str(e)}"
        raise Exception

    review_prompt = str(DRY_MODULARITY_REVIEW_PROMPT).format(
        file_path=file_path, code_with_lines=code_with_lines)
    review_messages = [HumanMessage(content=review_prompt)]

    try:

        # response = llm.invoke(review_messages)
        response = enforce_rate_limit(review_messages)
        review_str = response.content.strip()

        if review_str.startswith("```json"):
            review_str = review_str[7:]
        if review_str.endswith("```"):
            review_str = review_str[:-3]

        parsed_review = json.loads(review_str.strip())

        if not isinstance(parsed_review, list):
            print(f"Error: LLM response is not a list. Raw response:\n{review_str}")
            raise Exception

        scores = [float(f['score']) for f in parsed_review if 'score' in f]
        evaluation_score = sum(scores) / len(scores) if scores else 8

        try:
            if parsed_review:
                summary_prompt = EVALUATION_SUMMARY_PROMPT_TEMPLATE.format(
                    list_of_json_findings=json.dumps(parsed_review, indent=2)
                )
                summary_messages = [HumanMessage(content=summary_prompt)]
                eval_response = llm.invoke(summary_messages)
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
                evaluation_issue_summary = "No issues found while reviewing the code for DRY compliance."
                evaluation_refactor_summary = """No refactor suggestions since the issues are not found while reviewing the code for DRY compliance."""
        except Exception as summary_exception:
            raise

        list_contains_refactored_code = apply_code_changes(code_script=code_with_lines, issue_list=parsed_review,
                                                           llm=llm)

        return {
            "filename": file_path,
            "evaluation_score": evaluation_score,
            "evaluation_issue_summary": evaluation_issue_summary,
            "evaluation_refactor_summary": evaluation_refactor_summary,
            "evaluation_details": list_contains_refactored_code
        }

    except json.JSONDecodeError:
        error_msg = f"Error decoding JSON from LLM review response:\n{review_str}"
        raise


    except Exception as e:
        error_msg = f"Unexpected error during LLM invocation or result parsing: {str(e)}"
        raise


@tool
def sql_file_evaluator_dry_review(file_path: str) -> dict:
    """
    Analyze a SQL file for DRY principles, modular design, best practices,
    and configuration hygiene. Returns structured evaluation results.
    """

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        error_msg = f"Error reading file {file_path}: {str(e)}"
        print(error_msg)
        raise Exception

    try:
        code_with_lines = _get_code_with_lines(code_content)
    except Exception as e:
        error_msg = f"Error generating line-numbered SQL: {str(e)}"
        print(error_msg)
        raise Exception

    review_prompt = SQL_CODE_REVIEW_PROMPT_TEMPLATE.format(code_content=code_with_lines)
    review_messages = [HumanMessage(content=review_prompt)]

    try:
        # response = llm.invoke(review_messages)
        response = enforce_rate_limit(review_messages)
        review_str = response.content.strip()

        if review_str.startswith("```json"):
            review_str = review_str[7:]
        if review_str.endswith("```"):
            review_str = review_str[:-3]

        parsed_review = json.loads(review_str.strip())
        print("##parsed review##", parsed_review)
        if not isinstance(parsed_review, list):
            print(f"Error: LLM response is not a list. Raw response:\n{review_str}")
            raise Exception

        scores = [float(f['score']) for f in parsed_review if 'score' in f]
        evaluation_score = sum(scores) / len(scores) if scores else None

        try:
            if parsed_review:
                summary_prompt = EVALUATION_SUMMARY_PROMPT_TEMPLATE.format(
                    list_of_json_findings=json.dumps(parsed_review, indent=2)
                )
                summary_messages = [HumanMessage(content=summary_prompt)]
                eval_response = llm.invoke(summary_messages)
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
                evaluation_issue_summary = "No issues found while reviewing the code for DRY compliance."
                evaluation_refactor_summary = """No refactor suggestions since the issues are not found while reviewing the code for DRY compliance."""
        except Exception as summary_exception:
            raise Exception

        list_contains_refactored_code = apply_code_changes(code_script=code_with_lines, issue_list=parsed_review,
                                                           llm=llm)

        return {
            "filename": file_path,
            "evaluation_score": evaluation_score,
            "evaluation_issue_summary": evaluation_issue_summary,
            "evaluation_refactor_summary": evaluation_refactor_summary,
            "evaluation_details": list_contains_refactored_code
        }

    except json.JSONDecodeError:
        error_msg = f"Failed to decode JSON from LLM response:\n{review_str}"
        print(error_msg)
        raise Exception

    except Exception as e:
        error_msg = f"Unexpected error during LLM invocation or processing: {str(e)}"
        print(error_msg)
        raise Exception


def run_dry_modularity_compliance_agent(file_path: str):
    """Main function to scan a directory and run the security agent on each file."""

    print(f"--- Starting DRY Modularity Review on the file : {file_path} ---")

    agent_prompt = PromptTemplate.from_template(DRY_REACT_AGENT_PROMPT_TEMPLATE)
    tools = [python_file_evaluator_dry_review, sql_file_evaluator_dry_review]
    dry_modularity_agent = create_react_agent(llm, tools, agent_prompt)
    agent_executor = AgentExecutor(
        agent=dry_modularity_agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        return_intermediate_steps=True
    )

    try:
        response = agent_executor.invoke({"input": f"Analyze the file: {file_path}"})
    except Exception as e:
        print("failed to invoke the DRY & Modularity Agent", e)
        return []

    if response.get("intermediate_steps"):
        try:
            _, tool_direct_output = response["intermediate_steps"][-1]
            print(f"--- Ending DRY Modularity Reviewing on the file : {file_path} ---")
            return tool_direct_output

        except Exception as eval_error:
            return []



    return total_review_list