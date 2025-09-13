# Imports

from typing import List, Optional, Literal
from pathlib import Path
from enum import Enum
import os

from pydantic import ValidationError

import time
from openai import RateLimitError

from langchain_groq import ChatGroq
from langchain.schema import HumanMessage

from pydantic import BaseModel, Field, conint, confloat
from langgraph.graph import StateGraph, START, END

import json

from dotenv import load_dotenv
load_dotenv()

# LLM Setup
model_name = "openai/gpt-oss-20b"
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

# Pydantic - State Maanagement

class Language(BaseModel):
    major_language: str
    minor_languages: List[str] = Field(default_factory=list)

# class Severity(str, Enum):
#     CRITICAL = "Critical"
#     MODERATE = "Moderate"
#     MINOR = "Minor"

class Issue(BaseModel):
    score: confloat(ge=0.0, le=8.0)
    severity: Literal["Critical", "Moderate", "Minor"]
    start_line: int
    end_line: int
    issue: str

class ToolIssue(BaseModel):
    report: List[Issue] = Field(default_factory=list)
    violations_count: int
    base_score: float

class EvaluationDetail(BaseModel):
    start_line_number: int
    end_line_number: int
    original_python_script: str
    issue_summary: str
    refactored_python_script: str
    severity: Literal["Critical", "Moderate", "Minor"]
    score: confloat(ge=0.0, le=8.0)

class EvaluationReport(BaseModel):
    violations_count: int
    evaluation_score: confloat(ge=0.0, le=8.0)
    evaluation_issue_summary: str
    evaluation_refactor_summary: str
    evaluation_details: List[EvaluationDetail] = Field(default_factory=list)

# Final LangGraph State
class State(BaseModel):
    filename: str
    language: Optional[Language] = None
    language_Report: Optional[ToolIssue] = None
    inline_Report: Optional[ToolIssue] = None
    merged_Report: Optional[ToolIssue] = None
    evaluationReport: Optional[EvaluationReport] = None


# Utility Functions

def extract_json_block(text: str):
    """Extracts the first JSON object from a string using brace counting."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in the text.")

    brace_count = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        char = text[i]

        if char == '"' and not escape:
            in_string = not in_string
        elif char == "\\" and in_string:
            escape = not escape
            continue
        elif not in_string:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return text[start : i + 1]

        escape = False

    raise ValueError("No complete JSON object found.")

def load_code_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()
    
def _get_code_with_lines(code_content: str) -> str:
        lines = code_content.splitlines()
        return "\n".join(f"{i + 1:04d}: {line}" for i, line in enumerate(lines))
    
    
# Language Detection Node

def language_identification_prompt(code_string):
    return f"""
    {{
      "task_definition": {{
        "persona": {{
          "role": "Language Identifier",
          "specialization": "Analyze the entire source code using and identify the language in which it is written"
        }},
        "task": {{
          "description": "You are given a input file for which you need to determine the language. The language can be any valid coding language, for example, Python, Java, SQL etc.",
          "rules" : [
            "1. The source code can be written completely in 1 language. Alternatively, the source code can have some code snippets defined in other languages.",
            "2. In case the source code is written in only 1 language, mention only that language in the major_language section of the output. Keep minor_language as empty",
            "3. If however, the source code contains code snippets from other languages, you need to mention that language in the major_language. In the minor_language, mention the language(s) in which other sections of the code are written",
            "4. Return only in JSON format, refer to the output_format. ",
            "5. Do not output any extra comment or response. Do not include any ``` json, or triple quotes."
          ]
          "input": {{
            "code_script": "{code_string}"
          }}
        }},
        "output_format": {{
          "result": {{
            "major_language": "str — language in which the majority of the script is written",
            "minor_languages": "[List str] — language(s) in which the some part of the script is written"
          }}
        }}
      }}
    }}
  """

def identify_language(state: State) -> dict:
    """Detects languages that are present in the file."""
    
    print(f"--- Starting Code Style And Consistency Review on the file : {state.filename} ---")
    
    
    try:
        code = str(load_code_from_file(state.filename))
        prompt = language_identification_prompt(code)
        messages = [HumanMessage(content=prompt)]
        # response = llm.invoke(messages)
        response = enforce_rate_limit(messages)
        raw_response = extract_json_block(response.content)
        raw_response_dict = json.loads(raw_response)
        result = raw_response_dict.get("result")


        if result:
            try:
                language_obj = Language(**result)
                # print(f"Language detected: {language_obj.model_dump()}")
                # print("\n########################################################\n")
                return {"language": language_obj.model_dump()}
            except ValidationError as ve:
                print(f"Validation error while parsing Language model: {ve}")
                return {}
        else:
            print("No 'result' found in LLM response.")
            return {}

    except Exception as e:
        print(f"Unexpected error in identify_language: {e}")
        return {}
    

# Node Condition

def nodes_condition(state: State) -> str:
    if state.language and state.language.major_language == "SQL":
        print("Detected major language as SQL, routing to SQL analysis node.\n")
        return "SQL"
    elif state.language and state.language.major_language == "Python":
        minor_langs = state.language.minor_languages or []
        if "SQL" in minor_langs:
            print("Detected minor language as SQL, routing to Python + SQL analysis node.\n")
            return "SQL"
        print("Detected major language as Python, routing to Python analysis node.\n")
        return "Python"
    else:
        raise ValueError("Unsupported language")
    
    
# Python Check Node

def score_getter_prompt(report_list, severity_list):
    return f"""{{
  "task_definition": {{
    "persona": {{
      "role": "Advanced Score Generator",
      "specialization": "Analyze every entry of input report, understand and generate a score for each report line."
    }},
    "context": "You are given a pylint **report list** and the **severity level** of each report in a list. Follow the rules mentioned to get the output in the particular `output_format` mentioned."
    "task": {{
      "description": [
        "1. Read each line of the **report_list** one by one.",
        "2. Extract the line number, pylint error code, and the issue description for each line from the report_list, and also get the severity from the severity_list.",
        "3. Based on the severity level, error code, and issue description, assign a score.",
        "4. Follow industry-standard coding practices.",
        "5. Based on the rule violated or context, assign a numeric score **between 0 and 8**. Strictly follow the severity_mapping for assigning the score.",
        "6. Return a well-structured report with all this information in a dictionary with the key `score`.",
        "7. Do not output any extra comment or response. Do not include any ``` json, or triple quotes.",
        "8. Keep in mind standard developer best practices such as code readability, naming conventions, whitespace and formatting, function/class documentation (docstrings), and code complexity."
      ]
    }},
    "input": {{
      "report_list": "{report_list}",
      "severity_list": "{severity_list}"
    }},
    "severity_mapping": {{
      "Critical": "score between 0–2",
      "Moderate": "score between 3–5",
      "Minor": "score between 6–8"
    }},
    "output_format": {{
      "score": "List[int] — **Score associated with each issue**. Do not give the report along with it."
    }}
  }}
}}
"""

def get_score(report_list, severity):
    """
    Analyze pylint report to generate score for each line.

    """

    prompt = score_getter_prompt(report_list, severity)
    messages = [HumanMessage(content=prompt)]
    # response = llm.invoke(messages)
    response = enforce_rate_limit(messages)

    try:
        raw_json = extract_json_block(response.content)
        parsed = json.loads(raw_json)
        result = parsed.get("score", [])
        if not isinstance(result, list):
            print(f"[WARN] get_score returned non-list: {type(result)} — {result}")
            return []
        return result
    except Exception as e:
        print(f"[ERROR] Failed to parse LLM score output: {e}")
        return []
    

def extract_score(stats) -> float | None:
    """Get `global_note` from dict (≤2.17) or LinterStats (≥3.0)."""
    return stats.get("global_note") if isinstance(stats, dict) else getattr(stats, "global_note", None)

def get_severity_level(msg_id: str) -> str:
    """
    Assign severity levels to different types of pylint violations.
    """
    severity_map = {
        'F': 'Critical',
        'E': 'Critical',
        'W': 'Minor',
        'C': 'Moderate',
        'R': 'Minor',
        'I': 'Minor'
    }

    # Get the first character of msg_id
    category = msg_id[0] if msg_id else 'I'
    return severity_map.get(category, 'Minor')

def format_messages_with_severity(reporter) -> list[dict]:
    """
    Convert CollectingReporter messages to a list of violation details with severity.
    """
    violations = []

    for m in reporter.messages:
        severity_level = get_severity_level(m.msg_id)
        violations.append({
            "score": None,  # Filled later
            "severity": severity_level,
            "start_line": m.line,
            "end_line": m.line,
            "issue_description": f"{m.msg_id}: {m.msg} ({m.symbol})"
        })

    return violations

def pylint_analyze(state: State) -> dict:
    """
    Run pylint on a Python script and return structured analysis.
    """

    try:
        from pylint.lint import Run
        from pylint.reporters.collecting_reporter import CollectingReporter
        print("Pylint imported successfully.")
    except ImportError as exc:
        raise RuntimeError("pylint is not installed (`pip install pylint`).") from exc

    target = Path(state.filename).expanduser()
    if not target.exists():
        raise FileNotFoundError(target)

    reporter = CollectingReporter()

    try:
        try:
            Run([str(target), "--disable=C0301,E0401,C0303,C0304"], reporter=reporter)
        except SystemExit:
            pass

        base_score = extract_score(reporter.linter.stats)
        if base_score is None:
            raise RuntimeError("Pylint ran but produced no global score.")

        violations = format_messages_with_severity(reporter)
        violation_count = len(violations)
        
        # Skip scoring if there are no violations
        if not violations:
            language_report = ToolIssue(
                report=[],
                violations_count=0,
                base_score=int(base_score)
            )
            print(f"[INFO] No violations found in: {state.filename}")
            return {"language_Report": language_report.model_dump()}

        # Combine message strings for LLM scoring
        report_lines = [
            f"{v['start_line']}:{v['issue_description']}" for v in violations
        ]
        score_input = "\n".join(report_lines)

        try:
            score_list = get_score(score_input, [v["severity"] for v in violations])
        except Exception as e:
            print(f"[ERROR] Failed to get score list: {e}")
            score_list = []

        # Attach scores to the violations
        for i in range(min(len(violations), len(score_list))):
            try:
                violations[i]["score"] = int(score_list[i])
            except (ValueError, TypeError):
                violations[i]["score"] = None

        # Convert to Pydantic Issue objects
        issue_objects = []
        for v in violations:
            try:
                score = v.get("score") or 0
                severity = v["severity"]
                start_line = v["start_line"]
                end_line = v["end_line"]
                issue_description = v["issue_description"]
                
                if severity and start_line is not None and end_line is not None and issue_description:
                    issue_objects.append(Issue(
                        score=score,
                        severity=severity,
                        start_line=start_line,
                        end_line=end_line,
                        issue=issue_description
                    ))
                else:
                    print(f"[ERROR] Skipping incomplete issue: {v}")
            except Exception as e:
                print(f"[ERROR] Skipping invalid issue: {e}")

        # Wrap in ToolIssue and update state
        language_report = ToolIssue(
            report=issue_objects,
            violations_count=violation_count,
            base_score=int(base_score)
        )

        print(f"Pylint analysis complete: {language_report.model_dump()}")
        # print("\n########################################################\n")
        # return {"language_Report": language_report.model_dump()}

    except Exception as e:
        raise RuntimeError(f"Pylint analysis failed: {e}")
    

# Python + SQL Check Node

def python_sql_analysis_prompt(code_string):
    return f"""
{{
  "task_definition": {{
    "persona": {{
      "role": "Advanced Linting Report Generator",
      "specialization": "Analyze the entire source code using **Pylint** and/or **SQLFluff** rules and categorize issues by severity and score."
    }},
    "context": "You are given a code script with line numbers that may include - Python code (containing embedded SQL queries as multiline strings or variables) or Pure SQL."
    "task": {{
      "description": [
        "Perform a complete linting analysis by acting like pylint for Python portion of the code and/or sqlfluff for SQL portion of the code",
        "Your linting process must ensure completeness and precision while strictly relying on available information. Aways adhere to the task_guidelines mentioned."
        "Your response should be in the specififed output format in JSON only."
      ]
    }}
    "task_guidelines": [
      {{
        "rule": "Detect and separate the script into Python and SQL segments or it may be pure SQL.",
        "details": [
          "1. For embedded SQL in Python strings (e.g., triple-quoted or multiline), identify them as SQL.",
          "2. Treat SQL-only scripts entirely as SQL.",
          "3. For rest ofthe code, identify them as Python."
        ]
      }},
      {{
        "rule": "Analyze the entire code first, then generate all the linting issues.",
        "details": [
          "1. Apply `pylint` to all the Python portions of the script.",
          "2. Apply `sqlfluff` to all the SQL portions of the script. Remember to stick to **only issues regarding Code Style and Consistency**. Do not list issues regarding security checks or modularity, or anything other than Code Style and Consistency."
        ]
      }},
      {{
        "rule": "For each issue, extract the important information regarding each issues.",
        "details": [
          "1. Extract the Line number",
          "2. Extract the column number",
          "3. Short and precise issue description",
          "4. Categorize the issue into one of the severity levels: Critical, Moderate and Minor",
          "5. Numeric severity score from 0 (sever, multiple serious issues) to 7 (very minor issues). Refer to the severity_mapping for getting the score. Do not output anything above 8.",
          "6. If the code line has no issue, do not count or take into consideration."
        ]
      }},
      {{
        "rule": "The output must follow strict formatting and content guidelines.",
        "details": [
          "1. Return a well-structured report with all this information in JSON format.",
          "2. Do not output any extra comment or response, do not include any ``` jason, or triple quotes.",
          "3. Keep in mind standard developer best practices, such as code readability, naming conventions, whitespace and formatting, and function/class documentation (docstrings), code complexity, and SQL formatting/style compliances."
        ]
      }},
    ],
    "note": "Note: Do not flag imports as unused if their attributes (e.g., json.dumps) are used in the code.",
    "input": {{
      "code_script": "{code_string}"
    }}
    "severity_mapping": {{
      "Critical": "score between 0 and 2",
      "Moderate": "score between 3 and 5",
      "Minor": "score between 6 and 8"
    }},
    "output_format": {{
      "result": {{
        "violations": "int — Total number of linting issues found",
        "base_score": "int — Overall score for the file **between 0 and 8**",
        "issue_description": "List[str] — Strings containing several detailed lint messages in readable format (each entry includes line number: column number: description)",
        "severity": "List[str] — List of severity levels mapped from each issue's score (Critical, Moderate, Minor)",
        "score": "List[str] — Score associated with each issue"
      }}
    }}
  }}
}}
"""

def analyze_python_and_sql(state: State) -> dict:
    """
    Perform comprehensive static code analysis on a file and return a structured report.
    """
    target = Path(state.filename).expanduser()
    if not target.exists():
        raise FileNotFoundError(target)

    code = str(load_code_from_file(target))
    code_with_lines = _get_code_with_lines(code)
    prompt = python_sql_analysis_prompt(code_with_lines)
    messages = [HumanMessage(content=prompt)]
    # response = llm.invoke(messages)
    response = enforce_rate_limit(messages)

    try:
        raw_json = extract_json_block(response.content)
        parsed = json.loads(raw_json)

        result = parsed.get("result", parsed)  # fallback if "result" is top-level
        violations = result.get("violations", 0)
        base_score = result.get("base_score", 0)
        descriptions = result.get("issue_description", [])
        severities = result.get("severity", [])
        scores = result.get("score", [])

        report = []
        for i, desc in enumerate(descriptions):
            try:
                parts = desc.split(":", 2)
                line = int(parts[0]) if len(parts) > 1 and parts[0].isdigit() else 0
                message = parts[2] if len(parts) > 2 else desc

                report.append(Issue(
                    score=int(scores[i]) if i < len(scores) else 0,
                    severity=severities[i] if i < len(severities) else "Minor",
                    start_line=line,
                    end_line=line,
                    issue=message.strip()
                ))
            except Exception as e:
                print(f"[WARN] Skipped malformed issue description '{desc}': {e}")

        tool_report = ToolIssue(
          violations_count=int(violations),
          base_score=int(base_score),
          report=report
        )

        # print(f"Analysis complete: {tool_report.model_dump()}")
        # print("\n########################################################\n")
        return {"language_Report": tool_report.model_dump()}

    except Exception as e:
        print(f"[ERROR] Failed to parse LLM output: {e}")
        empty_report = ToolIssue(violations_count=0, base_score=0, report=[])
        return {"language_Report": empty_report.model_dump()}
    

# Inline Comments Check Node

def inline_comments_analysis_prompt(code_string):
    return f"""
{{
  "task_definition": {{
    "persona": {{
      "role": "Static Code Analysis Agent",
      "specialization": "Analyze inline comments in source code to assess their correctness, clarity, and necessity."
    }},
    "context": "You are given a code script along with line numbers.",
    "task_guidlines": [
      {{
        "rule": "Analyze **only** the inline comments in the given code",
        "details": [
          "1. Identify issues in existing comments like language, spelling or logical errors.",
          "2. Suggest where comments are needed. Where the code logic becomes complex.",
          "3. If the comment lines are having no issue, do not include it in the report.",
          "4. Identify the starting and ending line nubers where the issue exists."
        ]
      }},
      {{
        "rule": "Return the output in the provided output_format only.",
        "details": [
          "1. 'start_line_number' - specifying the line number where the *issue starts*. Do not include any zero in the begining. It should be a valid integer.",
          "2. 'end_line_number' - specifying the line number where the *issue ends*. Do not include any zero in the begining. It should be a valid integer.",
          "3. 'issue' is the short description of the issue."
        ]
      }},
      {{
        "rule": "Return the output in JSON, and no other format.",
        "details": [
          "1. Do not include any markdown, ``` jason, or triple quotes, or any extra explanations.",
          "2. Output must be **valid and complete JSON** that can be **parsed** directly."
        ]
      }},
    ],
    "output_format": {{
      "report": [
        {{
          "start_line_number": <int - start_line_number>,
          "end_line_number": <int - end_line_number>,
          "issue": <str - Brief description of the problem>
        }}
      ]
    }},
    "example_output": {{
      "report": [
        {{
          "start_line_number": 256,
          "end_line_number": 259,
          "issue": "Commented out code should be removed if not needed."
        }}
      ]
    }}
    "input": {{
      "code_string": {code_string}
    }}
  }}
}}
"""

def analyze_inline_comments(state: State) -> dict:
    """
    Analyze inline comments in a Python file to detect issues related to clarity, relevance, and redundancy.
    Returns a structured report with score, severity, and issue description.
    """
    target = Path(state.filename).expanduser()
    if not target.exists():
        raise FileNotFoundError(target)

    code = str(load_code_from_file(target))
    code_with_lines = _get_code_with_lines(code)
    prompt = inline_comments_analysis_prompt(code_with_lines)
    messages = [HumanMessage(content=prompt)]
    # response = llm.invoke(messages)
    response = enforce_rate_limit(messages)

    raw_response = response.content
#     print(raw_response)

    try:
        json_text = extract_json_block(raw_response)
        parsed = json.loads(json_text)
        raw_report = parsed.get("report", [])
    except Exception as e:
        print(f"[ERROR] Failed to parse response: {e}")
        raw_report = []

    issues = []
    for item in raw_report:
        try:
            issues.append(Issue(
                score=8,  # Assuming static score for now
                severity="Minor",  # Assuming all are minor; could be LLM-predicted later
                start_line=item["start_line_number"],
                end_line=item["end_line_number"],
                issue=item["issue"]
            ))
        except KeyError as e:
            print(f"[WARN] Skipping malformed report entry: {item}, missing key {e}")
        except Exception as e:
            print(f"[WARN] Could not parse item: {item}, error: {e}")

    inline_report = ToolIssue(
        violations_count=len(issues),
        base_score=8,  # Static base score for inline comments
        report=issues
    )

    # print(f"Inline comments analysis complete: {inline_report.model_dump()}")
    # print("\n########################################################\n")
    return {"inline_Report": inline_report.model_dump()}


# Summation Node

def report_merger_prompt(report1, report2):
    return f"""
  You are a static code evaluation agent.

  Your task is to merge two issue reports from different analysis tools into one consolidated report.

  Each input report contains:
  - `violation_count`: Number of issues found.
  - `base_score`: Integer from 0 to 8. Chose the number based on the base_score of the two reports
  - `report`: A list of issues, where each issue includes:
      - `score`: Integer (0–8)
      - `severity`: One of ["Critical", "Moderate", "Minor"]
      - `start_line`: Start line of the issue
      - `end_line`: End line of the issue
      - `issue_description`: Brief text description

  ### Merging Instructions:
  1. Combine all issues from both reports.
  2. If two or more issues share the same `start_line` and `end_line`:
    - Merge them into one entry.
    - Concatenate their `issue_description` with `; ` separator.
    - Set severity to the more severe one using this ranking: Critical (highest), then Moderate, then Minor (lowest). For example, if one issue is Minor and another is Moderate, choose Moderate.”
    - Set the `score` to the **minimum** score.
  3. If both reports contain identical issues (same lines, severity, score, and description), include only one copy.
  4. If line numbers are different, retain the issues as-is.
  5. Make sure to **complete the json** output, do not end abruptly.

  ### Final Output Format (JSON):
  {{
    "report": [
      {{
        "score": <int>,
        "severity": "<Critical|Moderate|Minor>",
        "start_line": <int>,          // the starting line number of the issue
        "end_line": <int>,            // the ending line number of the issue
        "issue_description": "<text>"
      }},
      ...
    ]
  }}

  Respond only with **valid and complete JSON** in the specified format. Do not include explanations, markdown, or free-text commentary.

  ### REPORT 1:
  {report1}

  ### REPORT 2:
  {report2}
"""

def summing_reports(state: State) -> dict:
    """
    Merge two tool reports into one unified report using an LLM.

    - Calculates the average base score of the two input reports.
    - Merges overlapping issues according to line ranges and severity.
    """

    if state.language_Report is None or state.inline_Report is None:
        print("[WARN] One or both reports are missing, skipping merge.")
        return state

    report1 = state.language_Report.model_dump()
    report2 = state.inline_Report.model_dump()

    prompt = report_merger_prompt(report1, report2)
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    raw_response = response.content
    
#     print("Summing Report:\n")
#     print(raw_response)
    
    try:
        json_text = extract_json_block(raw_response)
        parsed = json.loads(json_text)
        raw_report = parsed.get("report", [])
    except Exception as e:
        print(f"[ERROR] Failed to parse response: {e}")
        raw_report = []

    # Calculate average base score
    base_score_1 = report1.get("base_score", 0)
    base_score_2 = report2.get("base_score", 0)
    average_base_score = float((base_score_1 + base_score_2) / 2.0)

    merged_issues = []
    for item in raw_report:
        try:
            merged_issues.append(Issue(
                score=item.get("score", 0),
                severity=item.get("severity", "Minor"),
                start_line=item.get("start_line", 0),
                end_line=item.get("end_line", 0),
                issue=item.get("issue_description", "No description provided.")
            ))
        except Exception as e:
            print(f"[WARN] Skipping malformed merged issue: {item}, error: {e}")

    merged_report = ToolIssue(
        violations_count=len(merged_issues),
        base_score=average_base_score,
        report=merged_issues
    )

    # print(f"Merged reports: {merged_report.model_dump()}")
    # print("\n########################################################\n")
    return {"merged_Report": merged_report.model_dump()}

# Refactor Node


def refactor_prompt(code_script: str, report: dict) -> str:
    return f"""
You are a **Code Refactoring Agent** specialized in applying automated fixes code based on diagnostic reports.

## TASK DEFINITION:
You will be given:
1. **A complete Python code script** along with line numbers.
2. **A structured report** containing:
   - `violation_count`: total number of issues found.
   - `base_score`: an integer from 0 to 8.
   - `report`: a list of issues. Each issue is a dictionary with:
       - `score`: Integer (0–8) representing severity.
       - `severity`: One of ["Critical", "Moderate", "Minor"]
       - `start_line`: Starting line of the issue.
       - `end_line`: Ending line of the issue.
       - `issue_description`: Brief text describing the issue.

## OBJECTIVE:
Apply **precise, minimal, and necessary** modifications to the original code, addressing each issue clearly and completely while preserving functionality.

## RULES:
- Only modify lines between `start_line` and `end_line`.
- Do not alter unrelated parts of the code.
- When refactoring, follow Python best practices and maintain existing formatting.
- Combine overlapping issues on the same lines if needed.
- Ensure fixes are consistent and correct.
- Use the `issue_description` to guide changes, but be smart and minimal.
- Return the output strictly in the requested JSON format, do not include any markdowns or triple quotes.

---

## OUTPUT FORMAT (Strict JSON):
{{
  "overall_issue_summary": "<short summary>",   # A concise summary (3 - 6 lines) of all the issues the code script contains
  "overall_refactor_summary": "<short summary>",   # A concise summary (3 - 6 lines) of all the changes made or refactored
  "evaluation_details": [
    {{
      "start_line_number": <int>,               # Get from the input `start_line`
      "end_line_number": <int>,                 # Get from the input `end_line`
      "original_python_script": "<original lines of code>",
      "issue_summary": "<issue description>",
      "refactored_python_script": "<corrected code>",
      "severity": "<Critical|Moderate|Minor>",
      "score": <int>
    }},
    ...
  ]
}}

### CODE SCRIPT:
{code_script}

### REPORT:
{report}
"""

def apply_code_changes(state: State) -> dict:
    """
    Apply structured code refactoring suggestions to a source file using LLM-assisted transformation.

    """
    target = Path(state.filename).expanduser()
    if not target.exists():
        raise FileNotFoundError(target)

    if not state.merged_Report:
        raise ValueError("Missing merged_Report in state. Cannot apply suggestions.")

    code = str(load_code_from_file(target))
    code_with_lines = _get_code_with_lines(code)
    suggestions = state.merged_Report.model_dump()
    prompt = refactor_prompt(code_with_lines, suggestions)
    messages = [HumanMessage(content=prompt)]
    # response = llm.invoke(messages)
    response = enforce_rate_limit(messages)
    raw_response = response.content

    try:
        json_text = extract_json_block(raw_response)
        parsed = json.loads(json_text)
        raw_report = parsed.get("evaluation_details", [])
        overall_issue_summary = parsed.get("overall_issue_summary", "")
        overall_refactor_summary = parsed.get("overall_refactor_summary", "")
#         print(f"Raw Refactored Report: {raw_report}")

        validated_report = []
        overall_score = 0.0
        for item in raw_report:
            try:
                if not isinstance(item, dict):
                    item = item.dict() if hasattr(item, "dict") else vars(item)

                try:
                    start_line_number = int(item.get("start_line_number", 0) or 0)
                except (ValueError, TypeError):
                    start_line_number = 0

                try:
                    end_line_number = int(item.get("end_line_number", 0) or 0)
                except (ValueError, TypeError):
                    end_line_number = 0
                    
                try:
                    overall_score += int(item.get("score", 0) or 0)
                except (ValueError, TypeError):
                    overall_score += 0

                validated_report.append(EvaluationDetail(
                    score=item.get("score", 0),
                    severity=item.get("severity", "Minor"),
                    start_line_number=start_line_number,
                    end_line_number=end_line_number,
                    issue_summary=item.get("issue_summary", "No description provided."),
                    original_python_script=item.get("original_python_script", ""),
                    refactored_python_script=item.get("refactored_python_script", "")
                ))
            except Exception as e:
                print(f"[WARN] Skipping malformed refactor entry: {item}, error: {e}")

        overall_score = overall_score/len(validated_report)
        
        validated_evaluation = EvaluationReport(
            violations_count=len(validated_report),
            evaluation_score=overall_score,
            evaluation_issue_summary=overall_issue_summary,
            evaluation_refactor_summary=overall_refactor_summary,
            evaluation_details=validated_report
        )

        # print(f"Code Style: {validated_evaluation.model_dump()}")
        # print("\n########################################################\n")
        print(f"--- Ending Code Style And Consistency Reviewing on the file : {state.filename} ---")
        return {"evaluationReport": validated_evaluation.model_dump()}
        

    except Exception as e:
        print(f"[ERROR] Failed to parse or validate LLM response: {e}")
        return {}
    

# LangGraph Orchestration

def create_code_quality_graph():
    builder = StateGraph(State)

    # Nodes
    builder.add_node("Language_Detection", identify_language)
    builder.add_node("Python_Check", pylint_analyze)
    builder.add_node("SQL_Python_Check", analyze_python_and_sql)
    builder.add_node("Inline_Comments_Check", analyze_inline_comments)
    builder.add_node("Report_Merger", summing_reports)
    builder.add_node("Refactor_Code", apply_code_changes)

    # Edges
    builder.add_edge(START, "Language_Detection")
    builder.add_conditional_edges("Language_Detection", nodes_condition, {
        "Python": "Python_Check",
        "SQL": "SQL_Python_Check",
    })
    builder.add_edge("Language_Detection", "Inline_Comments_Check")
    builder.add_edge("Python_Check", "Report_Merger")
    builder.add_edge("SQL_Python_Check", "Report_Merger")
    builder.add_edge("Inline_Comments_Check", "Report_Merger")
    builder.add_edge("Report_Merger", "Refactor_Code")
    builder.add_edge("Refactor_Code", END)

    # Compiling the graph
    graph = builder.compile()

    return graph