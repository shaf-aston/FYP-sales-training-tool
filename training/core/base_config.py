"""
Training configuration
"""
from dataclasses import dataclass
from pathlib import Path

@dataclass
class TrainingConfig:
    model_name: str
    output_dir: str
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-5
    max_length: int = 512
    eval_split: float = 0.1
    save_steps: int = 500
    log_steps: int = 100
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    device: str = "cuda"
    
    def __post_init__(self):
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
