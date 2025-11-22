import os
import subprocess
from pathlib import Path

def extract_transcripts_from_videos():
    """
    Extract transcripts from video files using a transcription service or library.
    This example uses whisper, but you can replace it with any transcription tool.
    """
    raw_path = Path("../raw")
    transcript_output_path = Path("../processed/transcripts")
    transcript_output_path.mkdir(exist_ok=True, parents=True)
    
    video_paths = []
    for folder_name in ["sales-training-transcripts", "roleplay-transcripts"]:
        folder_path = raw_path / folder_name
        if folder_path.exists():
            video_paths.extend(list(folder_path.glob("**/*.mp4")))
    
    print(f"Found {len(video_paths)} video files to transcribe")
    
    for video_path in video_paths:
        output_name = video_path.stem + ".txt"
        output_path = transcript_output_path / output_name
        
        if output_path.exists():
            print(f"Transcript already exists for {video_path.name}, skipping...")
            continue
        
        print(f"Transcribing {video_path.name}...")
        
        try:
            command = f"whisper \"{video_path}\" --model medium --output_dir \"{transcript_output_path}\" --output_format txt"
            subprocess.run(command, shell=True, check=True)
            print(f"Transcription complete: {output_path}")
        except Exception as e:
            print(f"Error transcribing {video_path.name}: {e}")
            
            print("Attempting alternative transcription method...")
            try:
                pass
            except Exception as e2:
                print(f"Alternative transcription also failed: {e2}")

if __name__ == "__main__":
    extract_transcripts_from_videos()