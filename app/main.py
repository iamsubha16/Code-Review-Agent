import sys
import os

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils import ensure_directories_exist
from app.gradio_ui import launch_app


def main():
    """
    Main function to initialize and launch the application.
    """
    try:
        print("🚀 Starting AI Code Review Report Generator...")
        
        # Ensure required directories exist
        print("📁 Setting up directories...")
        ensure_directories_exist()
        
        # Launch the Gradio application
        print("🌐 Launching web interface...")
        print("📝 Upload .py or .sql files to get started!")
        print("🔗 The application will be available in your browser...")
        
        # Launch with default settings - you can modify these as needed
        launch_app(
            share=True,          
            server_name="0.0.0.0",
            server_port=None     
        )
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()