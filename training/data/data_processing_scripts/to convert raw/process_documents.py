"""
Script to process document files and categorize them
"""
import os
from pathlib import Path
import docx2txt
import re

def extract_text_from_docx():
    """
    Extract text from DOCX files and categorize them.
    """
    raw_path = Path("../raw")
    
    doc_paths = list(raw_path.glob("**/*.docx"))
    doc_paths.extend(list(raw_path.glob("**/*.txt")))
    
    print(f"Found {len(doc_paths)} document files to process")
    
    for doc_path in doc_paths:
        content_category = categorize_document(doc_path)
        
        if content_category == "roleplay":
            output_dir = Path("../processed/roleplay_transcripts")
        elif content_category == "training":
            output_dir = Path("../processed/sales_training_transcripts")
        elif content_category == "breakdown":
            output_dir = Path("../processed/script_breakdowns")
        else:
            output_dir = Path("../processed/sales_training_transcripts")
        
        output_dir.mkdir(exist_ok=True, parents=True)
        output_name = doc_path.stem + ".txt"
        output_path = output_dir / output_name
        
        if output_path.exists():
            print(f"Text already extracted for {doc_path.name}, skipping...")
            continue
        
        print(f"Extracting text from {doc_path.name} to {content_category}...")
        
        try:
            if doc_path.suffix.lower() == '.docx':
                text = docx2txt.process(doc_path)
            else:
                with open(doc_path, 'r', encoding='utf-8', errors='replace') as f:
                    text = f.read()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"Extraction complete: {output_path}")
        except Exception as e:
            print(f"Error extracting text from {doc_path.name}: {e}")

def categorize_document(doc_path):
    """
    Categorize a document based on its filename or content.
    Returns: "roleplay", "training", or "breakdown"
    """
    filename = doc_path.name.lower()
    
    if any(term in filename for term in ["roleplay", "role play", "script", "james and jill"]):
        return "roleplay"
    elif any(term in filename for term in ["training", "guide", "guideline"]):
        return "training"
    elif any(term in filename for term in ["breakdown", "analysis", "review"]):
        return "breakdown"
    
    try:
        if doc_path.suffix.lower() == '.docx':
            sample_text = docx2txt.process(doc_path)[:1000].lower()
        else:
            with open(doc_path, 'r', encoding='utf-8', errors='replace') as f:
                sample_text = f.read(1000).lower()
        
        if any(term in sample_text for term in ["roleplay", "script", "customer:", "rep:", "sales:"]):
            return "roleplay"
        elif any(term in sample_text for term in ["training", "lesson", "guidelines", "how to"]):
            return "training"
        elif any(term in sample_text for term in ["breakdown", "analysis", "review", "critique"]):
            return "breakdown"
    except Exception:
        pass
    
    return "training"

if __name__ == "__main__":
    extract_text_from_docx()
