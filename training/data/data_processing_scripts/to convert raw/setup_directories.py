"""
Script to create the necessary directory structure for data processing
"""
from pathlib import Path

def setup_environment():
    """Set up the environment and directory structure"""
    data_path = Path("..")
    paths_to_create = [
        data_path / "processed",
        data_path / "processed/roleplay_transcripts",
        data_path / "processed/sales_training_transcripts",
        data_path / "processed/script_breakdowns",
        data_path / "scripts"
    ]
    
    for path in paths_to_create:
        path.mkdir(exist_ok=True, parents=True)
    
    print("Directory structure created successfully!")

if __name__ == "__main__":
    setup_environment()
