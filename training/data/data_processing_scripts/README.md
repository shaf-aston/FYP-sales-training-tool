# Python Code for Data Processing

This directory contains Python scripts for processing transcripts, documents, and other data related to the Sales Roleplay Chatbot project.

## Directory Structure

- `raw processing/`: Main scripts for processing raw data
  - `main.py`: Main script to run the entire data processing pipeline
  - `setup_directories.py`: Creates the necessary directory structure
  - `process_documents.py`: Processes document files (DOCX, TXT)
  - `transcribe_audio.py`: Transcribes audio/video files
  - `process_nepq_data.py`: Processes text data according to NEPQ framework
  - `extract_transcripts.py`: Extracts transcripts from various sources

- `scripts/`: Helper scripts for specific tasks
  - `test_process_file.py`: Test script to process a single file

## Utility Scripts

- `organize_scripts.py`: Script that organizes files from data/scripts into appropriate folders
- `rename_scripts.py`: Renames scripts to match expected import names
- `cleanup_scripts.py`: Removes original scripts from data/scripts after organization

## How to Use

1. Run the main processing pipeline:
   ```
   cd "data/python code/raw processing"
   python main.py
   ```

2. This will:
   - Set up the directory structure
   - Process document files into appropriate categories
   - Transcribe audio/video files (if configured)

3. The processed data will be organized into:
   - `data/processed/roleplay_transcripts/`
   - `data/processed/sales_training_transcripts/`
   - `data/processed/script_breakdowns/`

## Notes

- The scripts are designed to skip files that have already been processed, preventing duplication.
- For transcription to work properly, you need to install the required dependencies.
- Check the specific script files for more detailed documentation on each step of the process.
