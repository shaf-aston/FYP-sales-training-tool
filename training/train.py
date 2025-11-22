#!/usr/bin/env python3
"""
Main training script for sales roleplay chatbot
Simple, clean PyTorch training pipeline
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForCausalLM, get_scheduler
from torch.utils.data import DataLoader

from core.dataset import SalesDataset, load_training_data
from core.config import TrainingConfig
from core.trainer import Trainer
from core.utils import set_seed, get_device

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Train sales roleplay chatbot")
    parser.add_argument("--data_path", type=str, required=True, help="Path to training data")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen2.5-0.5B-Instruct", help="Model to train")
    parser.add_argument("--output_dir", type=str, default="./checkpoints", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--eval_split", type=float, default=0.1, help="Validation split ratio")
    parser.add_argument("--max_length", type=int, default=512, help="Max sequence length")
    parser.add_argument("--save_steps", type=int, default=500, help="Save checkpoint every N steps")
    parser.add_argument("--log_steps", type=int, default=100, help="Log every N steps")
    return parser.parse_args()

def main():
    args = parse_args()
    set_seed(args.seed)
    device = get_device()
    
    logger.info("=" * 60)
    logger.info("Sales Roleplay Chatbot Training")
    logger.info("=" * 60)
    logger.info(f"Device: {device}")
    logger.info(f"Model: {args.model_name}")
    logger.info(f"Data: {args.data_path}")
    
    config = TrainingConfig(
        model_name=args.model_name,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_length=args.max_length,
        eval_split=args.eval_split,
        save_steps=args.save_steps,
        log_steps=args.log_steps,
        device=device
    )
    
    logger.info("Loading tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    )
    model = model.to(device)
    
    logger.info("Loading training data...")
    train_data, eval_data = load_training_data(args.data_path, args.eval_split)
    logger.info(f"Train samples: {len(train_data)}, Eval samples: {len(eval_data)}")
    
    train_dataset = SalesDataset(train_data, tokenizer, args.max_length)
    eval_dataset = SalesDataset(eval_data, tokenizer, args.max_length) if eval_data else None
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    eval_loader = DataLoader(eval_dataset, batch_size=args.batch_size) if eval_dataset else None
    
    trainer = Trainer(
        model=model,
        config=config,
        train_loader=train_loader,
        eval_loader=eval_loader,
        tokenizer=tokenizer
    )
    
    logger.info("Starting training...")
    trainer.train()
    
    logger.info("Training complete!")
    logger.info(f"Best model saved to: {config.output_dir}/best_model")

if __name__ == "__main__":
    main()
