# Training Pipeline

Clean, modular PyTorch training for sales roleplay chatbot.

## Quick Start

### 1. Prepare Data

Place your training data in one of these formats:

**JSONL format** (`data/training.jsonl`):
```jsonl
{"input": "User message", "output": "Bot response"}
{"input": "Another user message", "output": "Another response"}
```

**JSON format** (`data/training.json`):
```json
[
  {"input": "User message", "output": "Bot response"},
  {"input": "Another user message", "output": "Another response"}
]
```

### 2. Train Model

```bash
python train.py --data_path data/training.jsonl
```

### 3. Advanced Options

```bash
python train.py \
  --data_path data/training.jsonl \
  --model_name Qwen/Qwen2.5-0.5B-Instruct \
  --output_dir ./checkpoints \
  --epochs 3 \
  --batch_size 4 \
  --lr 2e-5 \
  --max_length 512
```

## Structure

```
training/
├── train.py              # Main training script
├── core/                 # Core modules
│   ├── config.py        # Training configuration
│   ├── dataset.py       # Data loading
│   ├── trainer.py       # Training loop
│   └── utils.py         # Utilities
├── data/                # Training data
└── checkpoints/         # Saved models
```

## Module Overview

### train.py
Entry point for training. Handles argument parsing and orchestrates training pipeline.

### core/config.py
Training configuration dataclass. All hyperparameters in one place.

### core/dataset.py
Data loading and preprocessing. Supports JSONL and JSON formats.

### core/trainer.py
Training loop implementation. Handles optimization, evaluation, and checkpointing.

### core/utils.py
Helper functions for seed setting and device selection.

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data_path` | Required | Path to training data |
| `--model_name` | Qwen/Qwen2.5-0.5B-Instruct | HuggingFace model |
| `--output_dir` | ./checkpoints | Where to save models |
| `--epochs` | 3 | Number of training epochs |
| `--batch_size` | 4 | Training batch size |
| `--lr` | 2e-5 | Learning rate |
| `--seed` | 42 | Random seed |
| `--eval_split` | 0.1 | Validation split ratio |
| `--max_length` | 512 | Max sequence length |
| `--save_steps` | 500 | Save checkpoint every N steps |
| `--log_steps` | 100 | Log every N steps |

## Output

Trained models are saved to `checkpoints/`:
- `best_model/` - Best model based on validation loss
- `epoch_N/` - Model after each epoch
- `checkpoint-N/` - Model at specified save steps
