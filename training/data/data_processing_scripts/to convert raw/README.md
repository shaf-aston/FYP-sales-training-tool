# Data Processing Scripts

This directory contains scripts for processing raw data files into organized, usable formats for the Sales Roleplay Chatbot project.

## Directory Structure

After processing, your data will be organized into:

- `processed/roleplay_transcripts/` - Contains transcripts of sales roleplay conversations
- `processed/sales_training_transcripts/` - Contains transcripts of sales training materials
- `processed/script_breakdowns/` - Contains analysis and breakdowns of sales techniques

## Getting Started

1. Make sure all your raw data files are in the `../raw/` directory
2. Install required packages:
   ```
   pip install docx2txt nltk openai-whisper
   ```
3. Run the main processing script:
   ```
   python main.py
   ```

## Individual Scripts

- `main.py` - Runs the entire processing pipeline
- `setup_directories.py` - Creates the necessary directory structure
- `process_documents.py` - Extracts text from DOCX files and categorizes them
- `transcribe_audio.py` - Transcribes audio/video files to text

## Notes

- The audio transcription process may take a long time depending on the number and size of your audio/video files
- Files are automatically categorized based on filename and content
- Processing scripts check for existing files to avoid duplication
