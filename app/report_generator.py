import pandas as pd
import os
from datetime import datetime
from app.config import (
    codeStyle_file_level_review_list,
    dry_file_level_review_list,
    security_file_level_review_list,
    codeStyle_line_level_review_list,
    dry_line_level_review_list,
    security_line_level_review_list,
    OUTPUT_DIR
)
from app.summary import (
    generate_overall_issue_summary,
    generate_overall_refactor_summary,
    generate_overall_repo_issue_summary,
    generate_overall_repo_refactor_summary
)

# Report Generation Function
def create_repo_level_df() -> pd.DataFrame:
    """
    Create repository-level summary dataframe.
    """
    # Code Style and Consistency
    codeStyle_file_level_issue_summary_list = []
    codeStyle_file_level_refactor_summary_list = []
    codeStyle_violations = 0
    codeStyle_score = 0
    codeStyle_score_avg = 0
    
    for single_dict in codeStyle_file_level_review_list:
        codeStyle_file_level_issue_summary_list.append(single_dict["issue_summary"])
        codeStyle_file_level_refactor_summary_list.append(single_dict["refactor_summary"])
        codeStyle_violations += single_dict["violations"]
        codeStyle_score += single_dict["score"]

    if codeStyle_file_level_review_list:
        codeStyle_score_avg = codeStyle_score / len(codeStyle_file_level_review_list)
    else:
        codeStyle_score_avg = 0

    codeStyle_repo_level_issue_summary = generate_overall_issue_summary(
        "Code Style and Consistency", codeStyle_file_level_issue_summary_list
    )
    codeStyle_repo_level_refactor_summary = generate_overall_refactor_summary(
        "Code Style and Consistency", codeStyle_file_level_refactor_summary_list
    )
    
    # DRY and Modularity
    dry_file_level_issue_summary_list = []
    dry_file_level_refactor_summary_list = []
    dry_violations = 0
    dry_score = 0
    dry_score_avg = 0
    
    for single_dict in dry_file_level_review_list:
        dry_file_level_issue_summary_list.append(single_dict["issue_summary"])
        dry_file_level_refactor_summary_list.append(single_dict["refactor_summary"])
        dry_violations += single_dict["violations"]
        dry_score += single_dict["score"]

    if dry_file_level_review_list:
        dry_score_avg = dry_score / len(dry_file_level_review_list)
    else:
        dry_score_avg = 0

    dry_repo_level_issue_summary = generate_overall_issue_summary(
        "DRY and Modularity", dry_file_level_issue_summary_list
    )
    dry_repo_level_refactor_summary = generate_overall_refactor_summary(
        "DRY and Modularity", dry_file_level_refactor_summary_list
    )
    
    # Security Compliance
    security_file_level_issue_summary_list = []
    security_file_level_refactor_summary_list = []
    security_violations = 0
    security_score = 0
    security_score_avg = 0
    
    for single_dict in security_file_level_review_list:
        security_file_level_issue_summary_list.append(single_dict["issue_summary"])
        security_file_level_refactor_summary_list.append(single_dict["refactor_summary"])
        security_violations += single_dict["violations"]
        security_score += single_dict["score"]

    if security_file_level_review_list:
        security_score_avg = security_score / len(security_file_level_review_list)
    else:
        security_score_avg = 0

    security_repo_level_issue_summary = generate_overall_issue_summary(
        "Security Compliance", security_file_level_issue_summary_list
    )
    security_repo_level_refactor_summary = generate_overall_refactor_summary(
        "Security Compliance", security_file_level_refactor_summary_list
    )
    
    # Overall Results
    overall_violations = codeStyle_violations + dry_violations + security_violations
    overall_score_avg = (security_score_avg + dry_score_avg + codeStyle_score_avg) / 3
    overall_repo_level_issue_summary = generate_overall_repo_issue_summary(
        codeStyle_repo_level_issue_summary, 
        dry_repo_level_issue_summary, 
        security_repo_level_issue_summary
    )
    overall_repo_level_refactor_summary = generate_overall_repo_refactor_summary(
        codeStyle_repo_level_refactor_summary, 
        dry_repo_level_refactor_summary, 
        security_repo_level_refactor_summary
    )
    
    # Create Repo Level DataFrame
    repo_level_data = [
        {
            "Review Category": "Code Style and Consistency", 
            "Vulnerabilities Flagged": codeStyle_violations, 
            "AI Review Score": codeStyle_score_avg, 
            "AI Reviewer Comments": codeStyle_repo_level_issue_summary, 
            "AI Suggested Fixes": codeStyle_repo_level_refactor_summary
        },
        {
            "Review Category": "DRY and Modularity", 
            "Vulnerabilities Flagged": dry_violations, 
            "AI Review Score": dry_score_avg, 
            "AI Reviewer Comments": dry_repo_level_issue_summary, 
            "AI Suggested Fixes": dry_repo_level_refactor_summary
        },
        {
            "Review Category": "Security Compliance", 
            "Vulnerabilities Flagged": security_violations, 
            "AI Review Score": security_score_avg, 
            "AI Reviewer Comments": security_repo_level_issue_summary, 
            "AI Suggested Fixes": security_repo_level_refactor_summary
        },
        {
            "Review Category": "Overall", 
            "Vulnerabilities Flagged": overall_violations, 
            "AI Review Score": overall_score_avg, 
            "AI Reviewer Comments": overall_repo_level_issue_summary, 
            "AI Suggested Fixes": overall_repo_level_refactor_summary
        }
    ]

    return pd.DataFrame(repo_level_data)

def create_file_level_df() -> pd.DataFrame:
    """
    Create file-level summary dataframe.
    """
    codeStyle_file_level_df = pd.DataFrame(codeStyle_file_level_review_list)
    dry_file_level_df = pd.DataFrame(dry_file_level_review_list)
    security_file_level_df = pd.DataFrame(security_file_level_review_list)

    # Merge the Dataframes
    return pd.concat([codeStyle_file_level_df, dry_file_level_df, security_file_level_df], ignore_index=True)

def create_line_level_df() -> pd.DataFrame:
    """
    Create line-level summary dataframe.
    """
    codeStyle_line_level_df = pd.DataFrame(codeStyle_line_level_review_list)
    dry_line_level_df = pd.DataFrame(dry_line_level_review_list)
    security_line_level_df = pd.DataFrame(security_line_level_review_list)

    # Changing Column Names
    if not codeStyle_line_level_df.empty:
        codeStyle_line_level_df = codeStyle_line_level_df.rename(columns={
            'refactored_python_script': 'refactored_script',
            'original_python_script': 'original_code_script'
        })
    
    if not dry_line_level_df.empty:
        dry_line_level_df = dry_line_level_df.rename(columns={
            'original_sql_script': 'original_code_script'
        })

    # Merge the Dataframes
    return pd.concat([codeStyle_line_level_df, dry_line_level_df, security_line_level_df], ignore_index=True)

# Displays Summary in UI
def create_repo_summary_table() -> pd.DataFrame:
    """
    Create repository summary table for display.
    """
    df = create_repo_level_df()
    return df if not df.empty else pd.DataFrame([{"No data": "Repository summary is empty"}])

# Generates Excel
def generate_excel_report() -> str:
    """
    Generate Excel report with all analysis data.
    """
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Generate filename with timestamp
    filename = f"code_review_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_file = os.path.join(OUTPUT_DIR, filename)
    
    # Create dataframes
    final_repo_review_df = create_repo_level_df()
    file_level_merged_df = create_file_level_df()
    line_level_merged_df = create_line_level_df()
    
    # Write to Excel
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        final_repo_review_df.to_excel(writer, sheet_name='Repository Review', index=False)
        file_level_merged_df.to_excel(writer, sheet_name='Files Review', index=False)
        line_level_merged_df.to_excel(writer, sheet_name='Line Level Review', index=False)
    
    return output_file