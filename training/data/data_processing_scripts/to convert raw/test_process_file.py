"""
Test script to process a single document file
"""
import sys
from pathlib import Path
from process_documents import categorize_document, extract_text_from_docx

def process_single_file(file_path):
    """Process a single document file and show its categorization"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"Error: File {file_path} does not exist")
        return
    
    if file_path.suffix.lower() not in ['.docx', '.txt']:
        print(f"Error: File {file_path} is not a supported document type (.docx or .txt)")
        return
    
    category = categorize_document(file_path)
    print(f"File: {file_path}")
    print(f"Categorized as: {category}")
    
    if category == "roleplay":
        output_dir = Path("../processed/roleplay_transcripts")
    elif category == "training":
        output_dir = Path("../processed/sales_training_transcripts")
    elif category == "breakdown":
        output_dir = Path("../processed/script_breakdowns")
    else:
        output_dir = Path("../processed/sales_training_transcripts")
    
    output_dir.mkdir(exist_ok=True, parents=True)
    output_name = file_path.stem + ".txt"
    output_path = output_dir / output_name
    
    try:
        if file_path.suffix.lower() == '.docx':
            import docx2txt
            text = docx2txt.process(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Processing complete!")
        print(f"Output saved to: {output_path}")
    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_process_file.py <path_to_file>")
        sys.exit(1)
    
    process_single_file(sys.argv[1])
