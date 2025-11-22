"""
Script to extract transcripts from audio/video files
"""
import os
import subprocess
from pathlib import Path

def transcribe_audio_files():
    """
    Extract transcripts from audio/video files using a transcription service.
    """
    raw_path = Path("../raw")
    
    video_paths = []
    for folder_name in ["sales-training-transcripts", "roleplay-transcripts"]:
        folder_path = raw_path / folder_name
        if folder_path.exists():
            video_paths.extend(list(folder_path.glob("**/*.mp4")))
            video_paths.extend(list(folder_path.glob("**/*.mp3")))
    
    print(f"Found {len(video_paths)} audio/video files to transcribe")
    
    for video_path in video_paths:
        if "roleplay-transcripts" in str(video_path):
            output_dir = Path("../processed/roleplay_transcripts")
        else:
            output_dir = Path("../processed/sales_training_transcripts")
        
        output_dir.mkdir(exist_ok=True, parents=True)
        output_name = video_path.stem + ".txt"
        output_path = output_dir / output_name
        
        if output_path.exists():
            print(f"Transcript already exists for {video_path.name}, skipping...")
            continue
        
        print(f"Transcribing {video_path.name}...")
        
        try:
            command = f"whisper \"{video_path}\" --model medium --output_dir \"{output_dir}\" --output_format txt"
            subprocess.run(command, shell=True, check=True)
            print(f"Transcription complete: {output_path}")
        except Exception as e:
            print(f"Error transcribing {video_path.name}: {e}")
            with open(output_path, 'w') as f:
                f.write(f"Transcription failed for {video_path}\nError: {str(e)}")

if __name__ == "__main__":
    transcribe_audio_files()
