"""
Dataset handling for training
"""
import json
import random
from pathlib import Path
from typing import List, Dict, Tuple
from torch.utils.data import Dataset

class SalesDataset(Dataset):
    def __init__(self, data, tokenizer, max_length):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        text = f"{item['input']}\n{item['output']}"
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": encoding["input_ids"].squeeze()
        }

def load_training_data(data_path: str, eval_split: float = 0.1) -> Tuple[List[Dict], List[Dict]]:
    data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    
    if data_path.suffix == ".jsonl":
        with open(data_path) as f:
            data = [json.loads(line) for line in f]
    elif data_path.suffix == ".json":
        with open(data_path) as f:
            data = json.load(f)
            if isinstance(data, dict):
                data = [{"input": k, "output": v} for k, v in data.items()]
    else:
        raise ValueError(f"Unsupported file format: {data_path.suffix}")
    
    random.shuffle(data)
    split_idx = int(len(data) * (1 - eval_split))
    train_data = data[:split_idx]
    eval_data = data[split_idx:] if eval_split > 0 else []
    
    return train_data, eval_data
