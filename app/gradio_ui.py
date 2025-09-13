import sys
import os
from typing import Generator, Tuple, Any
from app.config import APP_TITLE, APP_DESCRIPTION, SUPPORTED_EXTENSIONS
from code_processor import process_uploaded_files
from app.report_generator import generate_excel_report

# Try to import gradio with fallback
try:
    import app.gradio_ui as gr
    GRADIO_AVAILABLE = True
    GRADIO_VERSION = getattr(gr, '__version__', 'unknown')
    print(f"✅ Gradio {GRADIO_VERSION} detected")
except ImportError:
    GRADIO_AVAILABLE = False
    print("⚠️ Gradio not available - using command line interface")


def generate_excel_report_with_progress() -> Generator[Tuple[int, str, Any], None, None]:
    """
    Generate Excel report with progress tracking.
    
    Yields:
        Tuple of (progress, status_message, download_file_update)
    """
    total_steps = 4  # Create repo df, file df, line df, write Excel
    current_step = 0
    
    try:
        # Step 1: Create repository level dataframe
        yield 0, "📊 Creating repository level analysis...", None
        
        # Import here to avoid circular imports
        from app.report_generator import create_repo_level_df, create_file_level_df, create_line_level_df
        
        final_repo_review_df = create_repo_level_df()
        
        # Update progress AFTER repo analysis is complete
        current_step += 1
        progress = int((current_step / total_steps) * 100)
        yield progress, "✅ Repository level analysis completed.", None
        
        # Step 2: Create file level dataframe  
        yield progress, "📁 Creating file level analysis...", None
        file_level_merged_df = create_file_level_df()
        
        # Update progress AFTER file analysis is complete
        current_step += 1
        progress = int((current_step / total_steps) * 100)
        yield progress, "✅ File level analysis completed.", None
        
        # Step 3: Create line level dataframe
        yield progress, "📝 Creating line level analysis...", None
        line_level_merged_df = create_line_level_df()
        
        # Update progress AFTER line analysis is complete
        current_step += 1
        progress = int((current_step / total_steps) * 100)
        yield progress, "✅ Line level analysis completed.", None
        
        # Step 4: Generate Excel file
        yield progress, "💾 Generating Excel file...", None
        
        output_file = generate_excel_report()
        
        # Update progress AFTER Excel file is generated
        current_step += 1
        progress = int((current_step / total_steps) * 100)
        status_message = f"✅ Excel report generated successfully! Click below to download."
        yield 100, status_message, gr.update(value=output_file, visible=True)

    except Exception as e:
        error_message = f"❌ Error generating Excel: {e}"
        print(error_message)
        raise gr.Error(error_message)


def create_gradio_interface():
    """
    Create and return the Gradio interface.
    
    Returns:
        Gradio Interface
    """
    
    def upload_and_process(files):
        """Handle file upload and processing."""
        if not files:
            return 0, "Please upload files first.", gr.update(visible=False), gr.update(visible=False), None
        
        # Convert generator to final result for simpler interface
        results = list(process_uploaded_files(files))
        if results:
            final_result = results[-1]  # Get the last yielded result
            return final_result
        else:
            return 0, "No files processed.", gr.update(visible=False), gr.update(visible=False), None
    
    def generate_report():
        """Handle report generation."""
        results = list(generate_excel_report_with_progress())
        if results:
            final_result = results[-1]  # Get the last yielded result
            return final_result
        else:
            return 0, "Failed to generate report.", None

    # Try using Blocks interface (newer Gradio versions)
    try:
        with gr.Blocks(theme=gr.themes.Soft()) as demo:
            gr.Markdown(f"# {APP_TITLE}")
            gr.Markdown(APP_DESCRIPTION)

            with gr.Row():
                with gr.Column(scale=1):
                    upload_button = gr.File(
                        label="Upload Code Files", 
                        file_count="multiple", 
                        file_types=SUPPORTED_EXTENSIONS
                    )
                with gr.Column(scale=2):
                    progress_bar = gr.Slider(
                        minimum=0, 
                        maximum=100, 
                        value=0, 
                        interactive=False, 
                        label="Progress"
                    )
                    status_text = gr.Textbox(
                        label="Status Message", 
                        value="Ready to upload files..."
                    )

            # Full-width repo summary table
            repo_summary_table = gr.Dataframe(
                label="📘 Repository Summary",
                visible=False,
                interactive=False,
                wrap=True
            )

            export_button = gr.Button(
                "Generate Detailed Review", 
                variant="primary", 
                visible=False
            )
            download_link = gr.File(
                label="Download Report", 
                visible=False
            )

            # Event handlers
            upload_button.upload(
                fn=upload_and_process,
                inputs=upload_button,
                outputs=[progress_bar, status_text, export_button, repo_summary_table, download_link]
            )

            export_button.click(
                fn=generate_report,
                inputs=None,
                outputs=[progress_bar, status_text, download_link]
            )

    except AttributeError:
        # Fallback to Interface for older Gradio versions
        print("⚠️ Using fallback interface for older Gradio version")
        
        def combined_process(files):
            """Combined processing function for older Gradio interface."""
            if not files:
                return "Please upload files first.", None, None
            
            try:
                # Process files
                results = list(process_uploaded_files(files))
                if not results:
                    return "No files processed.", None, None
                
                # Get final processing result
                final_process_result = results[-1]
                progress, status, export_btn, repo_table, download = final_process_result
                
                # Generate report
                report_results = list(generate_excel_report_with_progress())
                if not report_results:
                    return status, None, "Files processed but failed to generate report."
                
                final_report_result = report_results[-1]
                report_progress, report_status, report_download = final_report_result
                
                return report_status, report_download, "Processing and report generation completed successfully!"
                
            except Exception as e:
                return f"Error: {str(e)}", None, None

        demo = gr.Interface(
            fn=combined_process,
            inputs=gr.File(
                label="Upload Code Files (.py, .sql)", 
                file_count="multiple"
            ),
            outputs=[
                gr.Textbox(label="Status"),
                gr.File(label="Download Report"),
                gr.Textbox(label="Summary")
            ],
            title=APP_TITLE,
            description=APP_DESCRIPTION,
            allow_flagging="never"
        )

    return demo


def launch_app(share: bool = True, server_name: str = None, server_port: int = None):
    """
    Launch the Gradio application.
    
    Args:
        share: Whether to create a public link
        server_name: Server name/IP to bind to
        server_port: Port to use
    """
    demo = create_gradio_interface()
    demo.launch(
        share=share, 
        server_name=server_name, 
        server_port=server_port
    )