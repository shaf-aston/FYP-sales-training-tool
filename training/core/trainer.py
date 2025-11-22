"""
Training loop and model management
"""
import time
import torch
import torch.nn as nn
from torch.optim import AdamW
from transformers import get_scheduler
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Trainer:
    def __init__(self, model, config, train_loader, eval_loader, tokenizer):
        self.model = model
        self.config = config
        self.train_loader = train_loader
        self.eval_loader = eval_loader
        self.tokenizer = tokenizer
        
        self.optimizer = AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay
        )
        
        num_training_steps = len(train_loader) * config.num_epochs
        num_warmup_steps = int(num_training_steps * config.warmup_ratio)
        
        self.scheduler = get_scheduler(
            "linear",
            optimizer=self.optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=num_training_steps
        )
        
        self.global_step = 0
        self.best_eval_loss = float('inf')
    
    def train(self):
        for epoch in range(self.config.num_epochs):
            logger.info(f"\nEpoch {epoch + 1}/{self.config.num_epochs}")
            train_loss = self.train_epoch()
            
            if self.eval_loader:
                eval_loss = self.evaluate()
                logger.info(f"Epoch {epoch + 1} - Train Loss: {train_loss:.4f}, Eval Loss: {eval_loss:.4f}")
                
                if eval_loss < self.best_eval_loss:
                    self.best_eval_loss = eval_loss
                    self.save_model("best_model")
                    logger.info(f"✓ New best model saved (eval_loss: {eval_loss:.4f})")
            else:
                logger.info(f"Epoch {epoch + 1} - Train Loss: {train_loss:.4f}")
            
            self.save_model(f"epoch_{epoch + 1}")
    
    def train_epoch(self):
        self.model.train()
        total_loss = 0
        start_time = time.time()
        
        for batch_idx, batch in enumerate(self.train_loader):
            batch = {k: v.to(self.config.device) for k, v in batch.items()}
            
            outputs = self.model(**batch)
            loss = outputs.loss
            loss.backward()
            
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
            
            self.optimizer.step()
            self.scheduler.step()
            self.optimizer.zero_grad()
            
            total_loss += loss.item()
            self.global_step += 1
            
            if (batch_idx + 1) % self.config.log_steps == 0:
                avg_loss = total_loss / (batch_idx + 1)
                elapsed = time.time() - start_time
                logger.info(
                    f"  Step {self.global_step} [{batch_idx + 1}/{len(self.train_loader)}] "
                    f"Loss: {avg_loss:.4f} Time: {elapsed:.1f}s"
                )
            
            if self.global_step % self.config.save_steps == 0:
                self.save_model(f"checkpoint-{self.global_step}")
        
        return total_loss / len(self.train_loader)
    
    @torch.no_grad()
    def evaluate(self):
        self.model.eval()
        total_loss = 0
        
        for batch in self.eval_loader:
            batch = {k: v.to(self.config.device) for k, v in batch.items()}
            outputs = self.model(**batch)
            total_loss += outputs.loss.item()
        
        return total_loss / len(self.eval_loader)
    
    def save_model(self, name):
        save_path = self.config.output_dir / name
        save_path.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)
