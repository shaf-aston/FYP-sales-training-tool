"""
PDF Text and Visual Content Extractor - LLM-Optimized
Extracts text and diagrams from all PDF files in the parent directory.
Converts images/diagrams to LLM-readable text using OCR.
Output is formatted for consumption by text-based LLMs and AI agents.
No image files are saved - all content is converted to text representation.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

def setup_output_directory(base_path):
    """Create output directory for extracted content"""
    output_dir = base_path / "extracted_content"
    output_dir.mkdir(exist_ok=True)
    return output_dir

def extract_text_from_pdf(pdf_path):
    """Extract text content from PDF"""
    try:
        doc = fitz.open(pdf_path)
        text_content = []
        
        for page_num, page in enumerate(doc, 1):
            text = page.get_text()
            if text.strip():
                text_content.append(f"\n{'='*80}\nPage {page_num}\n{'='*80}\n{text}")
        
        doc.close()
        return "\n".join(text_content)
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def extract_images_from_pdf(pdf_path, output_dir, pdf_name):
    """Extract images from PDF and convert to text using OCR - LLM-optimized output"""
    image_texts = []
    
    try:
        doc = fitz.open(pdf_path)
        image_count = 0
        
        for page_num, page in enumerate(doc, 1):
            # Get images on the page
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Convert to PIL Image
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    image_count += 1
                    
                    # Get image metadata for LLM context
                    width, height = image.size
                    mode = image.mode
                    
                    # Perform OCR on image
                    ocr_text = pytesseract.image_to_string(image)
                    
                    # Create LLM-readable representation
                    image_representation = (
                        f"\n{'='*80}\n"
                        f"[VISUAL ELEMENT #{image_count}]\n"
                        f"Location: Page {page_num}, Image {img_index+1}\n"
                        f"Type: {image_ext.upper()} image\n"
                        f"Dimensions: {width}x{height} pixels\n"
                        f"Color Mode: {mode}\n"
                        f"{'='*80}\n"
                        f"[OCR EXTRACTED TEXT FROM THIS VISUAL]:\n"
                        f"{ocr_text if ocr_text.strip() else '[No readable text detected in this image]'}\n"
                        f"{'='*80}\n"
                    )
                    
                    image_texts.append(image_representation)
                
                except Exception as e:
                    image_texts.append(
                        f"\n[VISUAL ELEMENT - ERROR]\n"
                        f"Location: Page {page_num}, Image {img_index+1}\n"
                        f"Error: {str(e)}\n"
                    )
        
        doc.close()
        
        if image_count > 0:
            return "\n".join(image_texts), image_count
        else:
            return "[No visual elements found in PDF]", 0
    
    except Exception as e:
        return f"[Error extracting visual elements: {str(e)}]", 0

def process_pdf(pdf_path, output_dir):
    """Process a single PDF file"""
    pdf_name = pdf_path.stem
    print(f"\nProcessing: {pdf_path.name}")
    print("-" * 80)
    
    # Extract text
    print("Extracting text content...")
    text_content = extract_text_from_pdf(pdf_path)
    
    # Extract visual elements and perform OCR (no image files saved)
    print("Extracting visual elements and performing OCR...")
    image_content, image_count = extract_images_from_pdf(pdf_path, output_dir, pdf_name)
    
    # Combine content - LLM-optimized format
    output_content = f"""
{'='*80}
[DOCUMENT METADATA]
{'='*80}
PDF FILE: {pdf_path.name}
EXTRACTION DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
CONTENT TYPE: LLM-optimized text extraction
{'='*80}

{'#'*80}
[SECTION 1: TEXT CONTENT]
{'#'*80}
{text_content}

{'#'*80}
[SECTION 2: VISUAL ELEMENTS - OCR EXTRACTED TEXT]
Total Visual Elements: {image_count}
{'#'*80}
{image_content}

{'='*80}
[END OF DOCUMENT]
{'='*80}
"""
    
    # Save to file
    output_filename = f"{pdf_name}_extracted.txt"
    output_path = output_dir / output_filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_content)
    
    print(f"✓ Extraction complete: {output_filename}")
    print(f"  - Text extracted: {'Yes' if text_content else 'No'}")
    print(f"  - Visual elements processed (OCR): {image_count}")
    print(f"  - Output format: LLM-optimized text only")
    
    return output_path

def main():
    """Main function to process all PDFs in the parent directory"""
    # Get the parent directory (Project management)
    script_dir = Path(__file__).parent
    parent_dir = script_dir.parent
    
    print(f"\n{'='*80}")
    print(f"PDF TEXT AND VISUAL EXTRACTOR")
    print(f"{'='*80}")
    print(f"Scanning directory: {parent_dir}")
    print(f"{'='*80}\n")
    
    # Find all PDF files in parent directory (direct children only)
    pdf_files = [f for f in parent_dir.glob("*.pdf")]
    
    if not pdf_files:
        print("No PDF files found in the parent directory.")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s):\n")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    print()
    
    # Setup output directory
    output_dir = setup_output_directory(parent_dir)
    print(f"Output directory: {output_dir}\n")
    
    # Process each PDF
    processed_count = 0
    for pdf_path in pdf_files:
        try:
            process_pdf(pdf_path, output_dir)
            processed_count += 1
        except Exception as e:
            print(f"✗ Error processing {pdf_path.name}: {str(e)}")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total PDFs found: {len(pdf_files)}")
    print(f"Successfully processed: {processed_count}")
    print(f"Output location: {output_dir}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
