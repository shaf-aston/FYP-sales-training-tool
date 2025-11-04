#!/usr/bin/env python3
"""
Sales Roleplay Chatbot Training Starter
Entry point for training conversational AI model with natural human-like responses
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from training.enhanced_training_coordinator import EnhancedTrainingCoordinator
from training.core_pipeline.model_training import ModelTrainer, TrainingConfig
from src.config.model_config import get_training_config, BASE_MODEL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'training/logs/training_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ConversationalTrainingManager:
    """
    Manages the complete training pipeline for natural conversational AI
    Focus: Human-like, natural responses in sales roleplay scenarios
    """
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.training_config = get_training_config()
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary training directories"""
        directories = [
            "training/data/conversations",
            "training/data/personas", 
            "training/data/scenarios",
            "training/models",
            "training/checkpoints",
            "training/logs"
        ]
        
        for dir_path in directories:
            full_path = self.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Directory ready: {full_path}")
    
    def create_conversational_training_data(self):
        """Create high-quality conversational training data for natural responses"""
        
        # Natural conversation examples for each persona
        training_data = {
            "Mary": [
                {
                    "user": "Hi Mary! I heard you're looking into fitness options?",
                    "response": "Oh yes! I've been thinking about it a lot lately. I'm 65 now and just retired from teaching, so I have more time. But honestly, I'm a bit nervous about starting something new at my age. What would you recommend for someone like me?",
                    "style": "curious_but_cautious",
                    "emotion": "interested_yet_hesitant"
                },
                {
                    "user": "What's your biggest concern about starting a fitness routine?",
                    "response": "Well, I'm worried about getting hurt. I haven't done much beyond walking in years. And to be frank, I'm not sure what I can afford right now on a fixed income. I don't want to commit to something that's going to break the bank, you know?",
                    "style": "honest_and_practical",
                    "emotion": "concerned_but_open"
                }
            ],
            "Jake": [
                {
                    "user": "Jake, I understand you've tried gym memberships before?",
                    "response": "Yeah, that's right. Look, I've been burned before - signed up for these expensive contracts and then never used them. I'm pretty skeptical about the whole fitness industry, to be honest. Everyone's trying to sell you something. What makes your approach different?",
                    "style": "direct_and_skeptical", 
                    "emotion": "guarded_but_willing_to_listen"
                },
                {
                    "user": "What would need to happen for you to feel confident in a fitness program?",
                    "response": "I'd need to see real results, not just promises. I'm a numbers guy - I want data, testimonials from people like me, and a clear understanding of what I'm getting for my money. No long-term contracts either. I want the flexibility to walk away if it's not working.",
                    "style": "analytical_and_demanding",
                    "emotion": "cautiously_interested"
                }
            ],
            "Sarah": [
                {
                    "user": "Sarah, tell me about your situation with fitness and budget.",
                    "response": "Hi! So I just graduated college and I'm trying to pay off my student loans while working part-time. I really want to get fit and healthy, but everything seems so expensive. I've been looking at budget options, but I'm worried about quality. Is there something that won't cost me a fortune but actually works?",
                    "style": "enthusiastic_but_budget_conscious",
                    "emotion": "optimistic_yet_worried"
                }
            ],
            "David": [
                {
                    "user": "David, I know you have a busy schedule as a doctor. How do you see fitness fitting in?",
                    "response": "That's exactly the challenge. Between hospital rounds, patients, and on-call shifts, I barely have time to sleep properly, let alone work out. I've tried those 24-hour gyms, but my schedule is so unpredictable. I need something that's flexible and doesn't require me to be somewhere at a specific time.",
                    "style": "professional_and_time_focused",
                    "emotion": "stressed_but_motivated"
                }
            ]
        }
        
        # Save training data
        training_file = self.project_root / "training/data/conversational_training.json"
        with open(training_file, 'w') as f:
            json.dump(training_data, f, indent=2)
        
        logger.info(f"✅ Created conversational training data: {training_file}")
        return training_file
    
    def create_training_config(self):
        """Create optimized training configuration for conversational responses"""
        
        config = TrainingConfig(
            # Model settings for natural conversation
            model_name=BASE_MODEL,
            max_length=512,  # Allow longer, more natural responses
            
            # Training parameters optimized for conversation
            num_epochs=5,  # More epochs for better conversation learning
            batch_size=4,  # Smaller batch for better gradient updates
            learning_rate=2e-5,  # Conservative learning rate
            warmup_steps=100,
            
            # Conversation-specific settings
            temperature=0.8,  # More creative responses
            top_p=0.9,  # Nucleus sampling for variety
            repetition_penalty=1.2,  # Avoid repetitive responses
            
            # Output settings
            output_dir=str(self.project_root / "training/models/conversational_model"),
            save_steps=250,
            eval_steps=250,
            logging_steps=50,
            
            # Quality control
            evaluation_strategy="steps",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            
            # Conversation quality focus
            conversation_quality_weight=0.3,  # Weight for natural conversation metrics
            persona_consistency_weight=0.2,   # Maintain persona characteristics
            response_naturalness_weight=0.5   # Prioritize human-like responses
        )
        
        config_file = self.project_root / "training/conversational_config.json"
        with open(config_file, 'w') as f:
            json.dump(config.__dict__, f, indent=2)
        
        logger.info(f"✅ Created training config: {config_file}")
        return config
    
    def start_conversational_training(self):
        """Start the complete conversational AI training pipeline"""
        
        logger.info("🚀 Starting Conversational AI Training Pipeline")
        logger.info("=" * 60)
        
        # Step 1: Prepare training data
        logger.info("📚 Step 1: Preparing conversational training data...")
        training_data_file = self.create_conversational_training_data()
        
        # Step 2: Create training configuration
        logger.info("⚙️ Step 2: Creating training configuration...")
        config = self.create_training_config()
        
        # Step 3: Initialize enhanced training coordinator
        logger.info("🎯 Step 3: Initializing enhanced training pipeline...")
        coordinator = EnhancedTrainingCoordinator()
        
        # Step 4: Run complete training pipeline
        logger.info("🏋️ Step 4: Starting model training...")
        try:
            # This will train the model for natural conversational responses
            results = coordinator.run_complete_pipeline(
                training_data_path=str(training_data_file),
                config=config,
                focus_areas=[
                    "conversational_naturalness",
                    "persona_consistency", 
                    "response_quality",
                    "human_like_responses"
                ]
            )
            
            logger.info("✅ Training completed successfully!")
            logger.info(f"📊 Results: {results}")
            
            # Step 5: Enable trained model
            self.enable_trained_model()
            
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            raise
    
    def enable_trained_model(self):
        """Switch the system to use the newly trained model"""
        
        # Set environment variable to use trained model
        os.environ["USE_TRAINED_MODEL"] = "1"
        
        # Create a simple script to set this permanently
        env_script = self.project_root / "use_trained_model.sh"
        with open(env_script, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("export USE_TRAINED_MODEL=1\n")
            f.write("echo 'Trained model enabled for conversational AI'\n")
        
        env_script.chmod(0o755)
        
        logger.info("✅ Trained model enabled! Restart server to use new model.")
        logger.info(f"💡 Run: source {env_script} && uvicorn src.main:app --reload")

def main():
    """Main training entry point"""
    print("🤖 Sales Roleplay Chatbot - Conversational AI Training")
    print("=" * 60)
    print("🎯 Goal: Train natural, human-like conversational responses")
    print("📋 Process: Data → Training → Validation → Deployment")
    print("=" * 60)
    
    try:
        manager = ConversationalTrainingManager()
        manager.start_conversational_training()
        
        print("\n🎉 Training pipeline completed!")
        print("🚀 Your AI is now ready for natural conversations!")
        
    except Exception as e:
        logger.error(f"❌ Training failed: {e}")
        print(f"\n💥 Training failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())