"""
Code processing functions for running different review agents.
"""

import os
import shutil
from typing import List, Dict, Any, Tuple, Generator
from app.config import (
    UPLOAD_DIR,
    SUPPORTED_EXTENSIONS,
    codeStyle_file_level_review_list,
    dry_file_level_review_list,
    security_file_level_review_list,
    codeStyle_line_level_review_list,
    dry_line_level_review_list,
    security_line_level_review_list
)
from app.utils import clear_uploaded_files


def reset_review_lists():
    """Reset all global review lists to empty state."""
    global codeStyle_file_level_review_list, dry_file_level_review_list, security_file_level_review_list
    global codeStyle_line_level_review_list, dry_line_level_review_list, security_line_level_review_list
    
    codeStyle_file_level_review_list.clear()
    dry_file_level_review_list.clear()
    security_file_level_review_list.clear()
    codeStyle_line_level_review_list.clear()
    dry_line_level_review_list.clear()
    security_line_level_review_list.clear()


def save_uploaded_files(files: List[Any]) -> None:
    """
    Save uploaded files to the upload directory.
    
    Args:
        files: List of uploaded file objects
    """
    for temp_file in files:
        original_filename = os.path.basename(temp_file.name)
        if hasattr(temp_file, 'orig_name') and temp_file.orig_name:
            original_filename = temp_file.orig_name

        file_path = os.path.join(UPLOAD_DIR, original_filename)
        shutil.copy(temp_file.name, file_path)


def get_processable_files() -> List[str]:
    """
    Get list of files that can be processed (Python or SQL files).
    
    Returns:
        List of file paths that can be processed
    """
    processable_files = []
    
    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        if (os.path.isfile(file_path) and 
            any(file_path.endswith(ext) for ext in SUPPORTED_EXTENSIONS)):
            processable_files.append(file_path)
    
    return processable_files


def run_code_style_agent(file_path: str) -> Dict[str, Any]:
    """
    Run the code style and consistency agent on a file.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        Dictionary containing the code style analysis results
    """
    # Import here to avoid circular imports
    from ReviewAgents.CodeStyle import create_code_quality_graph
    
    graph = create_code_quality_graph()
    response = graph.invoke({"filename": file_path})["evaluationReport"]
    return response


def run_dry_modularity_agent(file_path: str) -> Dict[str, Any]:
    """
    Run the DRY and modularity agent on a file.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        Dictionary containing the DRY and modularity analysis results
    """
    # Import here to avoid circular imports
    from ReviewAgents.DRY import run_dry_modularity_compliance_agent
    
    response = run_dry_modularity_compliance_agent(file_path)
    return response


def run_security_agent(file_path: str) -> Dict[str, Any]:
    """
    Run the security compliance agent on a file.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        Dictionary containing the security analysis results
    """
    # Import here to avoid circular imports
    from ReviewAgents.Security import run_security_compliance_agent
    
    response = run_security_compliance_agent(file_path)
    return response


def process_single_file(file_path: str, filename: str) -> Tuple[Dict, Dict, Dict]:
    """
    Process a single file with all three agents.
    
    Args:
        file_path: Full path to the file
        filename: Just the filename
        
    Returns:
        Tuple of (code_style_response, dry_response, security_response)
    """
    # Run Code Style Agent
    print(f"Running Code Style Agent for {filename}")
    codeStyle_response = run_code_style_agent(file_path)
    
    # Run DRY Agent  
    print(f"Running DRY & Modularity Agent for {filename}")
    dry_response = run_dry_modularity_agent(file_path)
    
    # Run Security Agent
    print(f"Running Security Compliance Agent for {filename}")
    security_response = run_security_agent(file_path)
    
    return codeStyle_response, dry_response, security_response


def store_file_level_results(filename: str, codeStyle_response: Dict, dry_response: Dict, security_response: Dict):
    """
    Store file-level results in global lists.
    
    Args:
        filename: Name of the processed file
        codeStyle_response: Code style agent response
        dry_response: DRY agent response  
        security_response: Security agent response
    """
    # File level data
    codeStyle_file_level_review_list.append({
        "filename": filename,
        "category": "Code Style & Consistency",
        "score": codeStyle_response["evaluation_score"],
        "issue_summary": codeStyle_response["evaluation_issue_summary"],
        "refactor_summary": codeStyle_response["evaluation_refactor_summary"],
        "violations": codeStyle_response["violations_count"]
    })

    dry_file_level_review_list.append({
        "filename": filename,
        "category": "DRY & Modularity",
        "score": dry_response["evaluation_score"],
        "issue_summary": dry_response["evaluation_issue_summary"],
        "refactor_summary": dry_response["evaluation_refactor_summary"],
        "violations": len(dry_response["evaluation_details"])
    })

    security_file_level_review_list.append({
        "filename": filename,
        "category": "Security Compliance",
        "score": security_response["evaluation_score"],
        "issue_summary": security_response["evaluation_issue_summary"],
        "refactor_summary": security_response["evaluation_refactor_summary"],
        "violations": len(security_response["evaluation_details"])
    })


def store_line_level_results(filename: str, codeStyle_response: Dict, dry_response: Dict, security_response: Dict):
    """
    Store line-level results in global lists.
    
    Args:
        filename: Name of the processed file
        codeStyle_response: Code style agent response
        dry_response: DRY agent response
        security_response: Security agent response
    """
    # Line Level Reviews
    x = codeStyle_response["evaluation_details"]
    y = dry_response["evaluation_details"]
    z = security_response["evaluation_details"]

    for i in x:
        i["filename"] = filename
        i["category"] = "Code Style & Consistency"
        codeStyle_line_level_review_list.append(i)

    for i in y:
        i["filename"] = filename
        i["category"] = "DRY and Modularity"
        dry_line_level_review_list.append(i)

    for i in z:
        i["filename"] = filename
        i["category"] = "Security Compliance"
        security_line_level_review_list.append(i)


def process_uploaded_files(files: List[Any]) -> Generator[Tuple[int, str, Any, Any, Any], None, None]:
    """
    Process uploaded files with progress tracking.
    
    Args:
        files: List of uploaded files
        
    Yields:
        Tuple of (progress, status_message, export_button_update, repo_table_update, download_link_update)
    """
    if not files:
        yield 0, "Please upload files first.", {"visible": False}, {"visible": False}, None
        return

    # Reset previous results
    reset_review_lists()
    
    total_files = len(files)
    
    # Calculate total steps: 3 agents per file
    total_steps = total_files * 3 
    current_step = 0

    yield 0, f"Processing {total_files} files...", {"visible": False}, {"visible": False}, None

    try:
        # Save uploaded files
        save_uploaded_files(files)
        
        # Get processable files
        processable_files = get_processable_files()
        
        if not processable_files:
            yield 0, "No .py or .sql files found to process.", {"visible": False}, {"visible": False}, None
            return

        # Process each file
        processed = 0
        for file_path in processable_files:
            filename = os.path.basename(file_path)
            
            progress = int((current_step / total_steps) * 100)
            yield progress, f"📁 Processing file: {filename}", {"visible": False}, {"visible": False}, None

            try:
                # Process the file with all agents
                yield progress, f"🧹 Running Code Style & Consistency Agent for file {filename}", {"visible": False}, {"visible": False}, None
                codeStyle_response = run_code_style_agent(file_path)
                current_step += 1
                
                progress = int((current_step / total_steps) * 100)
                yield progress, f"✅ Code Style Agent completed for {filename}.", {"visible": False}, {"visible": False}, None
                
                yield progress, f"🔄 Running DRY & Modularity Agent for file {filename}", {"visible": False}, {"visible": False}, None
                dry_response = run_dry_modularity_agent(file_path)
                current_step += 1
                
                progress = int((current_step / total_steps) * 100)
                yield progress, f"✅ DRY & Modularity Agent completed for {filename}.", {"visible": False}, {"visible": False}, None

                yield progress, f"🔒 Running Security Compliance Agent for file {filename}", {"visible": False}, {"visible": False}, None
                security_response = run_security_agent(file_path)
                current_step += 1
                
                progress = int((current_step / total_steps) * 100)
                yield progress, f"✅ Security Compliance Agent completed for {filename}.", {"visible": False}, {"visible": False}, None

                # Store results
                store_file_level_results(filename, codeStyle_response, dry_response, security_response)
                store_line_level_results(filename, codeStyle_response, dry_response, security_response)

                print(f"###code style response### {codeStyle_response}")
                print(f"##dry response## {dry_response}")
                print(f"##security response## {security_response}")

            except Exception as agent_err:
                # Still increment step counter even on error to maintain progress accuracy
                current_step += 3  # Skip the remaining 3 steps for this file
                progress = int((current_step / total_steps) * 100)
                yield progress, f"❌ Error processing {filename}: {agent_err}", {"visible": False}, {"visible": False}, None

            processed += 1
            yield progress, f"📋 Finished Reviewing {filename} ({processed}/{len(processable_files)})", {"visible": False}, {"visible": False}, None

        # Clean up and create summary
        clear_uploaded_files()
        
        from app.report_generator import create_repo_summary_table
        repo_df = create_repo_summary_table()
        
        yield 100, "✅ All files processed. See summary below.", {"visible": True}, {"value": repo_df, "visible": True}, None

    except Exception as e:
        yield 0, f"❌ Error during processing: {str(e)}", {"visible": False}, {"visible": False}, None