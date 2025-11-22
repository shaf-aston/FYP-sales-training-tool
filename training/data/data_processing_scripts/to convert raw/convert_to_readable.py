import os
from pathlib import Path
import docx2txt
import re
import shutil

def convert_documents():
    """
    Convert raw documents to readable format and organize by type.
    """
    base_dir = Path("../../").resolve()
    raw_path = base_dir / "raw"
    readable_path = base_dir / "readable_converted"
    
    print(f"Looking for files in: {raw_path}")
    print(f"Will save converted files to: {readable_path}")
    
    readable_path.mkdir(exist_ok=True)
    
    roleplay_dir = readable_path / "roleplay-transcripts"
    sales_training_dir = readable_path / "sales-training-transcripts"
    script_breakdowns_dir = readable_path / "script-breakdowns"
    
    roleplay_dir.mkdir(exist_ok=True)
    sales_training_dir.mkdir(exist_ok=True)
    script_breakdowns_dir.mkdir(exist_ok=True)
    
    doc_paths = list(raw_path.glob("**/*.docx"))
    txt_paths = list(raw_path.glob("**/*.txt"))
    all_paths = doc_paths + txt_paths
    
    print(f"Found {len(all_paths)} files to convert to readable format")
    
    for file_path in all_paths:
        if file_path.suffix.lower() == ".docx":
            content_category = categorize_document(file_path)
            try:
                text = docx2txt.process(file_path)
                file_content = text
            except Exception as e:
                print(f"Error extracting text from {file_path.name}: {e}")
                continue
        else:
            content_category = categorize_document(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    file_content = f.read()
            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")
                continue
        
        if content_category == "roleplay" or "roleplay-transcripts" in str(file_path):
            output_dir = roleplay_dir
        elif content_category == "training" or "sales-training-transcripts" in str(file_path):
            output_dir = sales_training_dir
        elif content_category == "breakdown" or "script-breakdowns" in str(file_path):
            output_dir = script_breakdowns_dir
        else:
            parent_folder = file_path.parent.name.lower()
            if "roleplay" in parent_folder:
                output_dir = roleplay_dir
            elif "training" in parent_folder or "sales" in parent_folder:
                output_dir = sales_training_dir
            elif "script" in parent_folder or "breakdown" in parent_folder:
                output_dir = script_breakdowns_dir
            else:
                output_dir = sales_training_dir
        
        output_name = file_path.stem + ".txt"
        output_path = output_dir / output_name
        
        if output_path.exists():
            print(f"File already exists: {output_path}, skipping...")
            continue
        
        print(f"Converting {file_path.name} to readable format in {output_dir.name}...")
        
        formatted_content = format_for_readability(file_content, content_category)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        
        print(f"Conversion complete: {output_path}")

def categorize_document(doc_path):
    """
    Categorize a document based on its filepath, filename or content.
    Returns: "roleplay", "training", or "breakdown"
    """
    filename = doc_path.name.lower()
    filepath = str(doc_path).lower()
    
    if "roleplay" in filepath or "role play" in filepath or "jill" in filepath:
        return "roleplay"
    
    elif "script" in filepath or "breakdown" in filepath or "grail" in filepath:
        return "breakdown"
    
    elif "training" in filepath or "guide" in filepath:
        return "training"
    
    if doc_path.suffix.lower() == ".docx":
        try:
            sample_text = docx2txt.process(doc_path)[:1000].lower()
            
            if "roleplay" in sample_text or ("role" in sample_text and "play" in sample_text):
                return "roleplay"
            elif "script" in sample_text or "breakdown" in sample_text:
                return "breakdown"
            elif "training" in sample_text or "learn" in sample_text:
                return "training"
        except:
            pass
    
    return "training"

def format_for_readability(text, category):
    """
    Format the text to be more readable based on document category
    """
    text = re.sub(r'\\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    if category == "roleplay":
        text = re.sub(r'(?i)^(Sales|Rep|Agent)[\s:]+(.*?)$', r'SALES REP: \2', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^(Customer|Client|Prospect)[\s:]+(.*?)$', r'CUSTOMER: \2', text, flags=re.MULTILINE)
        
        text = f"# ROLEPLAY TRANSCRIPT\n\n{text}"
        
    elif category == "breakdown":
        if not re.search(r'#{1,3}\s+', text):
            text = f"# SCRIPT BREAKDOWN\n\n{text}"
            
    elif category == "training":
        text = f"# SALES TRAINING MATERIAL\n\n{text}"
    
    return text

if __name__ == "__main__":
    convert_documents()
