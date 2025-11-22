"""
Main script for running the data processing pipeline
"""
import os
import sys
from pathlib import Path

def setup_environment():
    """Set up the environment and install required packages"""
    data_path = Path("..")
    paths_to_create = [
        data_path / "processed",
        data_path / "processed/roleplay_transcripts",
        data_path / "processed/sales_training_transcripts",
        data_path / "processed/script_breakdowns",
        data_path / "scripts",
        data_path / "readable_converted",
        data_path / "readable_converted/roleplay-transcripts",
        data_path / "readable_converted/sales-training-transcripts",
        data_path / "readable_converted/script-breakdowns"
    ]
    
    for path in paths_to_create:
        path.mkdir(exist_ok=True, parents=True)
    
    required_packages = [
        "docx2txt",
        "nltk",
        "openai-whisper" 
    ]
    
    for package in required_packages:
        try:
            print(f"Installing {package}...")
            os.system(f"{sys.executable} -m pip install {package}")
        except Exception as e:
            print(f"Failed to install {package}: {e}. You may need to install it manually.")

def main():
    """Run the entire data processing pipeline"""
    setup_environment()
    
    print("\n=== Processing Document Files ===")
    from process_documents import extract_text_from_docx
    extract_text_from_docx()
    
    print("\n=== Extracting Transcripts from Videos ===")
    from transcribe_audio import transcribe_audio_files
    transcribe_audio_files()
    
    print("\n=== Converting Documents to Readable Format ===")
    try:
        from convert_to_readable import convert_documents
        convert_documents()
    except Exception as e:
        print(f"Error running document conversion: {e}")
    
    print("\n=== Data Processing Complete ===")
    print("Check the following directories for processed data:")
    print("- processed/ directory - For model training")
    print("- readable_converted/ directory - For human-readable documents:")
    print("  - readable_converted/roleplay-transcripts/")
    print("  - readable_converted/sales-training-transcripts/")
    print("  - readable_converted/script-breakdowns/")

if __name__ == "__main__":
    main()
