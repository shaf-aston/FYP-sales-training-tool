"""
Main Training Script - Easy Entry Point
Automatically adapts to dataset size and structure changes
Simple command-line interface for flexible training
"""
import sys
import argparse
import logging
from pathlib import Path
import json
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from transformers import AutoTokenizer
from core_pipeline.adaptive_dataset import AdaptiveSalesDataset, create_train_val_split
from core_pipeline.adaptive_config import (
    AdaptiveTrainingConfig,
    create_config_from_dataset_stats,
    get_preset_config
)
from core_pipeline.adaptive_trainer import AdaptivePyTorchTrainer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Adaptive PyTorch Training Pipeline for Sales Roleplay Chatbot"
    )
    
    # Data arguments
    parser.add_argument(
        "--data_path",
        type=str,
        default="training/data/processed/training_pairs.jsonl",
        help="Path to training data (JSONL or JSON)"
    )
    parser.add_argument(
        "--val_split",
        type=float,
        default=0.1,
        help="Validation split ratio (0.0-1.0)"
    )
    
    # Model arguments
    parser.add_argument(
        "--model_name",
        type=str,
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="Hugging Face model name or path"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="training/models/fine-tuned",
        help="Output directory for trained model"
    )
    
    # Training arguments
    parser.add_argument(
        "--preset",
        type=str,
        choices=["quick_test", "small_dataset", "medium_dataset", "large_dataset", "production", "auto"],
        default="auto",
        help="Preset configuration (auto will adapt to dataset size)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Number of training epochs (overrides preset)"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=None,
        help="Training batch size (overrides preset)"
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=None,
        help="Learning rate (overrides preset)"
    )
    parser.add_argument(
        "--max_length",
        type=int,
        default=None,
        help="Maximum sequence length (auto-computed if not specified)"
    )
    
    # Configuration arguments
    parser.add_argument(
        "--config_file",
        type=str,
        default=None,
        help="Path to custom config file (YAML or JSON)"
    )
    parser.add_argument(
        "--save_config",
        type=str,
        default=None,
        help="Save generated config to file"
    )
    parser.add_argument(
        "--auto_configure",
        action="store_true",
        default=True,
        help="Automatically configure hyperparameters based on dataset"
    )
    parser.add_argument(
        "--no_auto_configure",
        action="store_false",
        dest="auto_configure",
        help="Disable automatic configuration"
    )
    
    # Advanced options
    parser.add_argument(
        "--resume_from_checkpoint",
        type=str,
        default=None,
        help="Resume training from checkpoint"
    )
    parser.add_argument(
        "--save_dataset_stats",
        action="store_true",
        help="Save dataset statistics to JSON"
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Show configuration without training"
    )
    
    return parser.parse_args()


def main():
    """Main training pipeline"""
    args = parse_args()
    
    logger.info("="*80)
    logger.info("Adaptive PyTorch Training Pipeline")
    logger.info("="*80)
    
    # Step 1: Load tokenizer
    logger.info(f"\nStep 1: Loading tokenizer from {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    
    # Step 2: Load and analyze dataset
    logger.info(f"\nStep 2: Loading dataset from {args.data_path}")
    dataset = AdaptiveSalesDataset(
        data_path=args.data_path,
        tokenizer=tokenizer,
        max_length=args.max_length,
        auto_configure=True
    )
    
    logger.info(f"Dataset loaded: {len(dataset)} samples")
    
    # Save dataset statistics if requested
    if args.save_dataset_stats:
        stats_path = Path(args.output_dir) / "dataset_stats.json"
        dataset.save_statistics(stats_path)
        logger.info(f"Dataset statistics saved to {stats_path}")
    
    # Step 3: Split into train/validation
    logger.info(f"\nStep 3: Creating train/validation split (val_ratio={args.val_split})")
    train_dataset, val_dataset = create_train_val_split(
        dataset,
        val_ratio=args.val_split,
        stratify_by='persona'
    )
    
    # Step 4: Create training configuration
    logger.info(f"\nStep 4: Creating training configuration")
    
    if args.config_file:
        # Load from file
        logger.info(f"Loading config from {args.config_file}")
        config = AdaptiveTrainingConfig.load(args.config_file)
    elif args.preset != "auto":
        # Use preset
        logger.info(f"Using preset: {args.preset}")
        config = get_preset_config(args.preset)
    else:
        # Auto-generate from dataset stats
        logger.info("Auto-generating configuration from dataset statistics")
        config = create_config_from_dataset_stats(dataset.stats)
    
    # Apply command-line overrides
    if args.model_name:
        config.model_name = args.model_name
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.epochs is not None:
        config.num_train_epochs = args.epochs
    if args.batch_size is not None:
        config.per_device_train_batch_size = args.batch_size
    if args.learning_rate is not None:
        config.learning_rate = args.learning_rate
    if args.max_length is not None:
        config.max_length = args.max_length
    if args.resume_from_checkpoint:
        config.resume_from_checkpoint = args.resume_from_checkpoint
    
    config.auto_configure = args.auto_configure
    
    # Adapt to dataset if auto-configure is enabled
    if config.auto_configure and dataset.stats:
        logger.info("Adapting configuration to dataset characteristics...")
        config.adapt_to_dataset_size(
            total_samples=dataset.stats.total_samples,
            avg_sample_length=(dataset.stats.avg_input_length + dataset.stats.avg_output_length)
        )
        config.adapt_to_available_memory()
    
    # Save configuration if requested
    if args.save_config:
        config.save(args.save_config)
        logger.info(f"Configuration saved to {args.save_config}")
    
    # Display configuration
    logger.info("\nTraining Configuration:")
    logger.info(f"  Model: {config.model_name}")
    logger.info(f"  Output: {config.output_dir}")
    logger.info(f"  Epochs: {config.num_train_epochs}")
    logger.info(f"  Batch size: {config.per_device_train_batch_size}")
    logger.info(f"  Gradient accumulation: {config.gradient_accumulation_steps}")
    logger.info(f"  Effective batch size: {config.get_effective_batch_size()}")
    logger.info(f"  Learning rate: {config.learning_rate:.2e}")
    logger.info(f"  Max length: {config.max_length}")
    logger.info(f"  Mixed precision: FP16={config.fp16}, BF16={config.bf16}")
    
    if dataset.stats:
        logger.info(f"\nDataset Characteristics:")
        logger.info(f"  Total samples: {dataset.stats.total_samples}")
        logger.info(f"  Train samples: {len(train_dataset)}")
        logger.info(f"  Val samples: {len(val_dataset)}")
        logger.info(f"  Unique personas: {len(dataset.stats.personas)}")
        logger.info(f"  Avg input length: {dataset.stats.avg_input_length:.1f} tokens")
        logger.info(f"  Avg output length: {dataset.stats.avg_output_length:.1f} tokens")
        logger.info(f"  Estimated training time: {dataset.stats.estimated_training_time_minutes:.1f} minutes")
    
    # Dry run - stop here if requested
    if args.dry_run:
        logger.info("\nDry run complete. No training performed.")
        return
    
    # Step 5: Initialize trainer
    logger.info(f"\nStep 5: Initializing trainer")
    trainer = AdaptivePyTorchTrainer(
        config=config,
        train_dataset=train_dataset,
        eval_dataset=val_dataset
    )
    
    # Resume from checkpoint if specified
    if args.resume_from_checkpoint:
        trainer.resume_from_checkpoint(args.resume_from_checkpoint)
    
    # Step 6: Train
    logger.info(f"\nStep 6: Starting training")
    logger.info("="*80)
    
    try:
        metrics = trainer.train()
        
        logger.info("\n" + "="*80)
        logger.info("Training completed successfully!")
        logger.info("="*80)
        logger.info(f"Final model saved to: {config.output_dir}")
        logger.info(f"Best validation loss: {trainer.best_eval_loss:.4f}")
        logger.info(f"Total steps: {trainer.global_step}")
        
        # Save final metrics
        metrics_path = Path(config.output_dir) / "training_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump([m.to_dict() for m in metrics], f, indent=2)
        logger.info(f"Metrics saved to: {metrics_path}")
        
    except KeyboardInterrupt:
        logger.warning("\nTraining interrupted by user")
        logger.info("Saving checkpoint...")
        trainer._save_checkpoint(final=True)
        logger.info("Checkpoint saved successfully")
    
    except Exception as e:
        logger.error(f"\nTraining failed with error: {e}", exc_info=True)
        logger.info("Attempting to save checkpoint...")
        try:
            trainer._save_checkpoint(final=True)
            logger.info("Emergency checkpoint saved")
        except:
            logger.error("Failed to save emergency checkpoint")
        raise


if __name__ == "__main__":
    main()
