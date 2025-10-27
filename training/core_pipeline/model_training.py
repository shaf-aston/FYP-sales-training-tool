"""
Model Fine-tuning Components
Handles model training, evaluation, and optimization for sales conversation AI
"""
import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, 
    TrainingArguments, Trainer,
    DataCollatorForLanguageModeling
)
from torch.utils.data import Dataset, DataLoader
import json
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import logging
from datetime import datetime
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    wandb = None

logger = logging.getLogger(__name__)

@dataclass
class TrainingConfig:
    """Configuration for model training"""
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    output_dir: str = "./training/models/fine-tuned"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_steps: int = 100
    logging_steps: int = 10
    eval_steps: int = 500
    save_steps: int = 500
    max_length: int = 512
    fp16: bool = True
    dataloader_num_workers: int = 4
    remove_unused_columns: bool = False

class SalesConversationDataset(Dataset):
    """Dataset for sales conversation training"""
    
    def __init__(self, data: List[Dict], tokenizer, max_length: int = 512):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        
        # Format conversation for training
        conversation = self._format_conversation(item)
        
        # Tokenize
        encoding = self.tokenizer(
            conversation,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': encoding['input_ids'].flatten()
        }
    
    def _format_conversation(self, item: Dict) -> str:
        """Format conversation data for training"""
        conversation = []
        
        # Add system prompt
        if 'persona' in item:
            persona = item['persona']
            system_prompt = f"You are a {persona} in a sales conversation. Respond naturally and consistently with this persona."
            conversation.append(f"<|im_start|>system\n{system_prompt}<|im_end|>")
        
        # Add conversation turns
        if 'conversation' in item:
            for turn in item['conversation']:
                role = turn.get('role', 'user')
                content = turn.get('content', '')
                conversation.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        
        return '\n'.join(conversation)

class ModelTrainer:
    """Handles model fine-tuning and training"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.tokenizer = None
        self.model = None
        self.trainer = None
        
    def initialize_model(self):
        """Initialize model and tokenizer"""
        logger.info(f"Loading model: {self.config.model_name}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
            device_map="auto"
        )
        
        # Add padding token if not present
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model.config.pad_token_id = self.model.config.eos_token_id
    
    def prepare_datasets(self, train_data: List[Dict], eval_data: List[Dict] = None):
        """Prepare training and evaluation datasets"""
        train_dataset = SalesConversationDataset(
            train_data, self.tokenizer, self.config.max_length
        )
        
        eval_dataset = None
        if eval_data:
            eval_dataset = SalesConversationDataset(
                eval_data, self.tokenizer, self.config.max_length
            )
        
        return train_dataset, eval_dataset
    
    def setup_trainer(self, train_dataset, eval_dataset=None):
        """Setup Hugging Face trainer"""
        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.num_train_epochs,
            per_device_train_batch_size=self.config.per_device_train_batch_size,
            per_device_eval_batch_size=self.config.per_device_eval_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_steps=self.config.warmup_steps,
            logging_steps=self.config.logging_steps,
            eval_steps=self.config.eval_steps,
            save_steps=self.config.save_steps,
            evaluation_strategy="steps" if eval_dataset else "no",
            save_strategy="steps",
            load_best_model_at_end=True if eval_dataset else False,
            metric_for_best_model="eval_loss" if eval_dataset else None,
            fp16=self.config.fp16,
            dataloader_num_workers=self.config.dataloader_num_workers,
            remove_unused_columns=self.config.remove_unused_columns,
            report_to="wandb" if WANDB_AVAILABLE else None  # For experiment tracking
        )
        
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False  # Causal LM, not masked LM
        )
        
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
            compute_metrics=self.compute_metrics if eval_dataset else None
        )
    
    def compute_metrics(self, eval_pred):
        """Compute metrics for evaluation"""
        predictions, labels = eval_pred
        
        # For language modeling, we compute perplexity
        predictions = predictions.reshape(-1)
        labels = labels.reshape(-1)
        
        # Remove padding tokens
        mask = labels != -100
        predictions = predictions[mask]
        labels = labels[mask]
        
        # Calculate perplexity
        loss = nn.CrossEntropyLoss()(
            torch.tensor(predictions).view(-1, predictions.shape[-1]),
            torch.tensor(labels).view(-1)
        )
        perplexity = torch.exp(loss)
        
        return {"perplexity": perplexity.item()}
    
    def train(self, train_data: List[Dict], eval_data: List[Dict] = None):
        """Execute training pipeline"""
        logger.info("Starting model training...")
        
        # Initialize model
        self.initialize_model()
        
        # Prepare datasets
        train_dataset, eval_dataset = self.prepare_datasets(train_data, eval_data)
        
        # Setup trainer
        self.setup_trainer(train_dataset, eval_dataset)
        
        # Start training
        self.trainer.train()
        
        # Save final model
        self.trainer.save_model()
        self.tokenizer.save_pretrained(self.config.output_dir)
        
        logger.info(f"Training completed. Model saved to {self.config.output_dir}")
        
        return self.trainer.state.log_history

class ModelEvaluator:
    """Evaluate trained models on various metrics"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """Load trained model for evaluation"""
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16,
            device_map="auto"
        )
    
    def evaluate_conversation_quality(self, test_conversations: List[Dict]) -> Dict:
        """Evaluate model performance on conversation quality"""
        results = {
            'persona_consistency': [],
            'response_relevance': [],
            'sales_effectiveness': [],
            'naturalness': []
        }
        
        for conversation in test_conversations:
            # Generate response for each conversation
            generated_response = self._generate_response(conversation)
            
            # Evaluate different aspects
            results['persona_consistency'].append(
                self._evaluate_persona_consistency(conversation, generated_response)
            )
            results['response_relevance'].append(
                self._evaluate_relevance(conversation, generated_response)
            )
            results['sales_effectiveness'].append(
                self._evaluate_sales_effectiveness(generated_response)
            )
            results['naturalness'].append(
                self._evaluate_naturalness(generated_response)
            )
        
        # Calculate averages
        return {
            metric: np.mean(scores) for metric, scores in results.items()
        }
    
    def _generate_response(self, conversation: Dict) -> str:
        """Generate response for evaluation"""
        # Format prompt
        prompt = self._format_evaluation_prompt(conversation)
        
        # Tokenize
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=150,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        # Decode response
        response = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )
        
        return response.strip()
    
    def _format_evaluation_prompt(self, conversation: Dict) -> str:
        """Format conversation for evaluation prompt"""
        # This would format the conversation appropriately for the model
        return f"Continue this sales conversation: {conversation.get('context', '')}"
    
    def _evaluate_persona_consistency(self, conversation: Dict, response: str) -> float:
        """Evaluate if response is consistent with assigned persona"""
        # Simplified evaluation - in practice would use more sophisticated methods
        persona = conversation.get('persona', '')
        
        if 'skeptical' in persona.lower():
            skeptical_words = ['but', 'however', 'concern', 'worry', 'doubt']
            score = sum(1 for word in skeptical_words if word in response.lower()) / len(skeptical_words)
        elif 'busy' in persona.lower():
            busy_words = ['time', 'quick', 'brief', 'fast', 'efficient']
            score = sum(1 for word in busy_words if word in response.lower()) / len(busy_words)
        else:
            score = 0.5  # Neutral score
        
        return min(score, 1.0)
    
    def _evaluate_relevance(self, conversation: Dict, response: str) -> float:
        """Evaluate response relevance to conversation context"""
        # Simplified - would use semantic similarity in practice
        context_words = set(conversation.get('context', '').lower().split())
        response_words = set(response.lower().split())
        
        if not context_words:
            return 0.5
        
        intersection = context_words.intersection(response_words)
        score = len(intersection) / len(context_words)
        
        return min(score, 1.0)
    
    def _evaluate_sales_effectiveness(self, response: str) -> float:
        """Evaluate sales effectiveness of response"""
        sales_techniques = [
            'benefit', 'value', 'solve', 'help', 'improve',
            'save', 'increase', 'reduce', 'guarantee'
        ]
        
        response_lower = response.lower()
        technique_count = sum(1 for technique in sales_techniques if technique in response_lower)
        
        return min(technique_count / len(sales_techniques), 1.0)
    
    def _evaluate_naturalness(self, response: str) -> float:
        """Evaluate naturalness of response"""
        # Check for repetition, coherence, appropriate length
        words = response.split()
        
        if len(words) < 5:
            return 0.3  # Too short
        elif len(words) > 100:
            return 0.7  # Might be too long
        
        # Check for word repetition
        unique_words = len(set(words))
        repetition_ratio = unique_words / len(words)
        
        return min(repetition_ratio * 1.2, 1.0)

def prepare_training_data(processed_data_path: str) -> Tuple[List[Dict], List[Dict]]:
    """Prepare training data from processed conversation data"""
    logger.info(f"Loading processed data from {processed_data_path}")
    
    # Load processed data
    data_files = list(Path(processed_data_path).glob("*.json"))
    all_conversations = []
    
    for file_path in data_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            all_conversations.extend(data)
    
    # Split into train/eval
    split_idx = int(len(all_conversations) * 0.8)
    train_data = all_conversations[:split_idx]
    eval_data = all_conversations[split_idx:]
    
    logger.info(f"Prepared {len(train_data)} training examples and {len(eval_data)} eval examples")
    
    return train_data, eval_data

def main():
    """Demo model training pipeline"""
    logger.info("Starting model training pipeline demo")
    
    # Configuration
    config = TrainingConfig(
        num_train_epochs=1,  # Reduced for demo
        per_device_train_batch_size=2,
        output_dir="./training/models/demo-model"
    )
    
    # Mock training data
    mock_train_data = [
        {
            'persona': 'skeptical_manager',
            'conversation': [
                {'role': 'user', 'content': 'Tell me about your product'},
                {'role': 'assistant', 'content': 'I understand you need to see proof before making decisions. Let me show you concrete results from similar companies...'}
            ]
        }
    ]
    
    # Initialize trainer
    trainer = ModelTrainer(config)
    
    logger.info("Training setup complete. In production, would execute:")
    logger.info("1. Load processed conversation data")
    logger.info("2. Fine-tune model on sales conversations")
    logger.info("3. Evaluate model performance")
    logger.info("4. Deploy trained model")

if __name__ == "__main__":
    main()