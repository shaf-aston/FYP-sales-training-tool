"""
Training Pipeline Coordinator
Orchestrates the complete model training workflow
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from data_processing_pipeline import DataProcessingPipeline
from roleplay_training import PersonaResponseGenerator, ObjectionHandler, FeatureExtraction
from model_training import ModelTrainer, TrainingConfig, prepare_training_data
from feedback_system import SalesPerformanceClassifier, FeedbackGenerator, ProgressTracker

logger = logging.getLogger(__name__)

class TrainingCoordinator:
    """Coordinates the complete training pipeline"""
    
    def __init__(self, config_path: str = "./training/config.json"):
        self.config = self._load_config(config_path)
        self.data_processor = DataProcessingPipeline()
        self.persona_generator = PersonaResponseGenerator()
        self.feedback_system = SalesPerformanceClassifier()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load training configuration"""
        default_config = {
            "data_sources": {
                "youtube_videos": "./training/raw_data/youtube/",
                "audio_recordings": "./training/raw_data/audio/",
                "transcripts": "./training/raw_data/transcripts/"
            },
            "output_paths": {
                "processed_data": "./training/processed_data/",
                "models": "./training/models/",
                "validation": "./training/validation/"
            },
            "training_params": {
                "model_name": "Qwen/Qwen2.5-0.5B-Instruct",
                "num_epochs": 3,
                "batch_size": 4,
                "learning_rate": 2e-5
            },
            "quality_thresholds": {
                "min_audio_quality": 0.7,
                "min_transcript_clarity": 0.8,
                "min_conversation_length": 100
            }
        }
        
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                # Merge with defaults
                for key, value in loaded_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        
        return default_config
    
    async def run_full_pipeline(self, incremental: bool = False) -> Dict:
        """Run the complete training pipeline"""
        logger.info("Starting complete training pipeline")
        
        results = {
            "pipeline_start": datetime.now().isoformat(),
            "stages_completed": [],
            "data_processed": 0,
            "models_trained": 0,
            "validation_results": {}
        }
        
        try:
            # Stage 1: Data Processing
            logger.info("Stage 1: Processing raw training data")
            processed_data = await self._process_training_data(incremental)
            results["data_processed"] = len(processed_data)
            results["stages_completed"].append("data_processing")
            
            # Stage 2: Quality Validation
            logger.info("Stage 2: Validating data quality")
            validated_data = self._validate_training_data(processed_data)
            results["stages_completed"].append("quality_validation")
            
            # Stage 3: Persona Enhancement
            logger.info("Stage 3: Enhancing with persona data")
            enhanced_data = self._enhance_with_personas(validated_data)
            results["stages_completed"].append("persona_enhancement")
            
            # Stage 4: Model Training
            logger.info("Stage 4: Training sales conversation model")
            training_results = await self._train_models(enhanced_data)
            results["models_trained"] = len(training_results)
            results["stages_completed"].append("model_training")
            
            # Stage 5: Validation & Testing
            logger.info("Stage 5: Validating trained models")
            validation_results = await self._validate_models(training_results)
            results["validation_results"] = validation_results
            results["stages_completed"].append("model_validation")
            
            # Stage 6: Deployment Preparation
            logger.info("Stage 6: Preparing for deployment")
            deployment_info = self._prepare_deployment(training_results, validation_results)
            results["deployment_ready"] = deployment_info
            results["stages_completed"].append("deployment_prep")
            
            results["pipeline_end"] = datetime.now().isoformat()
            results["success"] = True
            
            logger.info("Training pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            results["error"] = str(e)
            results["success"] = False
        
        # Save results
        self._save_pipeline_results(results)
        return results
    
    async def _process_training_data(self, incremental: bool = False) -> List[Dict]:
        """Process raw training data"""
        processed_data = []
        
        # Process YouTube videos
        youtube_path = Path(self.config["data_sources"]["youtube_videos"])
        if youtube_path.exists():
            video_files = list(youtube_path.glob("*.mp4"))
            for video_file in video_files:
                try:
                    data = await self.data_processor.process_youtube_video(str(video_file))
                    processed_data.append(data)
                except Exception as e:
                    logger.warning(f"Failed to process video {video_file}: {e}")
        
        # Process audio recordings
        audio_path = Path(self.config["data_sources"]["audio_recordings"])
        if audio_path.exists():
            audio_files = list(audio_path.glob("*.wav")) + list(audio_path.glob("*.mp3"))
            for audio_file in audio_files:
                try:
                    data = await self.data_processor.process_audio_recording(str(audio_file))
                    processed_data.append(data)
                except Exception as e:
                    logger.warning(f"Failed to process audio {audio_file}: {e}")
        
        # Process transcripts
        transcript_path = Path(self.config["data_sources"]["transcripts"])
        if transcript_path.exists():
            transcript_files = list(transcript_path.glob("*.txt")) + list(transcript_path.glob("*.json"))
            for transcript_file in transcript_files:
                try:
                    data = await self.data_processor.process_transcript(str(transcript_file))
                    processed_data.append(data)
                except Exception as e:
                    logger.warning(f"Failed to process transcript {transcript_file}: {e}")
        
        logger.info(f"Processed {len(processed_data)} data items")
        return processed_data
    
    def _validate_training_data(self, processed_data: List[Dict]) -> List[Dict]:
        """Validate data quality against thresholds"""
        validated_data = []
        thresholds = self.config["quality_thresholds"]
        
        for data_item in processed_data:
            # Check audio quality if present
            if "audio_features" in data_item:
                audio_quality = data_item.get("performance_analysis", {}).get("clarity_score", 0)
                if audio_quality < thresholds["min_audio_quality"]:
                    logger.debug(f"Skipping item due to low audio quality: {audio_quality}")
                    continue
            
            # Check transcript clarity
            if "transcript" in data_item:
                transcript_length = len(data_item["transcript"])
                if transcript_length < thresholds["min_conversation_length"]:
                    logger.debug(f"Skipping item due to short transcript: {transcript_length}")
                    continue
            
            validated_data.append(data_item)
        
        logger.info(f"Validated {len(validated_data)} items from {len(processed_data)} processed")
        return validated_data
    
    def _enhance_with_personas(self, validated_data: List[Dict]) -> List[Dict]:
        """Enhance training data with persona information"""
        enhanced_data = []
        
        for data_item in validated_data:
            # Extract customer personality features
            if "transcript" in data_item:
                feature_extractor = FeatureExtraction()
                customer_features = feature_extractor.extract_prospect_features(data_item["transcript"])
                
                # Assign appropriate persona
                persona_id = self._assign_persona(customer_features)
                
                # Enhance with persona context
                enhanced_item = data_item.copy()
                enhanced_item["persona_id"] = persona_id
                enhanced_item["customer_features"] = customer_features
                
                # Generate additional training examples for this persona
                additional_examples = self._generate_persona_examples(persona_id, data_item)
                enhanced_data.extend(additional_examples)
            
            enhanced_data.append(data_item)
        
        logger.info(f"Enhanced {len(enhanced_data)} training examples with persona data")
        return enhanced_data
    
    def _assign_persona(self, customer_features: Dict) -> str:
        """Assign persona based on extracted features"""
        communication_style = customer_features.get("communication_style", "casual")
        decision_making = customer_features.get("decision_making_style", "analytical")
        
        if communication_style == "direct" and decision_making == "decisive":
            return "busy_executive"
        elif communication_style == "formal" and decision_making == "analytical":
            return "skeptical_manager"
        else:
            return "friendly_small_business"
    
    def _generate_persona_examples(self, persona_id: str, base_data: Dict) -> List[Dict]:
        """Generate additional training examples for persona"""
        objection_handler = ObjectionHandler()
        examples = []
        
        # Generate common objections for this persona
        for _ in range(3):  # Generate 3 additional examples
            objection = objection_handler.generate_objection()
            
            example = {
                "persona_id": persona_id,
                "transcript": f"Customer: {objection['objection']}",
                "objection_type": objection,
                "generated": True,
                "base_conversation": base_data.get("source_file", "unknown")
            }
            examples.append(example)
        
        return examples
    
    async def _train_models(self, enhanced_data: List[Dict]) -> List[Dict]:
        """Train models on enhanced data"""
        training_results = []
        
        # Prepare training configuration
        config = TrainingConfig(
            model_name=self.config["training_params"]["model_name"],
            num_train_epochs=self.config["training_params"]["num_epochs"],
            per_device_train_batch_size=self.config["training_params"]["batch_size"],
            learning_rate=self.config["training_params"]["learning_rate"],
            output_dir=self.config["output_paths"]["models"]
        )
        
        # Split data by persona for specialized training
        persona_data = {}
        for item in enhanced_data:
            persona = item.get("persona_id", "general")
            if persona not in persona_data:
                persona_data[persona] = []
            persona_data[persona].append(item)
        
        # Train a model for each persona
        for persona_id, data in persona_data.items():
            if len(data) < 10:  # Skip if not enough data
                logger.warning(f"Insufficient data for persona {persona_id}: {len(data)} items")
                continue
            
            try:
                logger.info(f"Training model for persona: {persona_id}")
                
                # Configure output directory for this persona
                persona_config = config
                persona_config.output_dir = f"{config.output_dir}/persona_{persona_id}"
                
                # Initialize trainer
                trainer = ModelTrainer(persona_config)
                
                # Split into train/eval
                split_idx = int(len(data) * 0.8)
                train_data = data[:split_idx]
                eval_data = data[split_idx:]
                
                # Train model
                training_history = trainer.train(train_data, eval_data)
                
                training_results.append({
                    "persona_id": persona_id,
                    "model_path": persona_config.output_dir,
                    "training_samples": len(train_data),
                    "eval_samples": len(eval_data),
                    "training_history": training_history,
                    "completed_at": datetime.now().isoformat()
                })
                
                logger.info(f"Completed training for persona {persona_id}")
                
            except Exception as e:
                logger.error(f"Failed to train model for persona {persona_id}: {e}")
        
        return training_results
    
    async def _validate_models(self, training_results: List[Dict]) -> Dict:
        """Validate trained models"""
        validation_results = {}
        
        for result in training_results:
            persona_id = result["persona_id"]
            model_path = result["model_path"]
            
            try:
                # Load test conversations for this persona
                test_conversations = self._load_test_conversations(persona_id)
                
                if not test_conversations:
                    logger.warning(f"No test conversations found for persona {persona_id}")
                    continue
                
                # Initialize evaluator
                from model_training import ModelEvaluator
                evaluator = ModelEvaluator(model_path)
                
                # Evaluate model
                evaluation_metrics = evaluator.evaluate_conversation_quality(test_conversations)
                
                validation_results[persona_id] = {
                    "evaluation_metrics": evaluation_metrics,
                    "test_conversations": len(test_conversations),
                    "model_path": model_path,
                    "validation_date": datetime.now().isoformat()
                }
                
                logger.info(f"Validated model for persona {persona_id}")
                
            except Exception as e:
                logger.error(f"Failed to validate model for persona {persona_id}: {e}")
        
        return validation_results
    
    def _load_test_conversations(self, persona_id: str) -> List[Dict]:
        """Load test conversations for validation"""
        # In a real implementation, this would load held-out test data
        # For now, return mock test conversations
        return [
            {
                "persona": persona_id,
                "context": "Customer is interested but has objections",
                "expected_response_type": "objection_handling"
            }
        ]
    
    def _prepare_deployment(self, training_results: List[Dict], validation_results: Dict) -> Dict:
        """Prepare deployment information"""
        deployment_info = {
            "trained_models": [],
            "deployment_ready": False,
            "recommended_model": None,
            "deployment_instructions": []
        }
        
        best_score = 0
        best_model = None
        
        for result in training_results:
            persona_id = result["persona_id"]
            
            if persona_id in validation_results:
                validation = validation_results[persona_id]
                avg_score = sum(validation["evaluation_metrics"].values()) / len(validation["evaluation_metrics"])
                
                deployment_info["trained_models"].append({
                    "persona_id": persona_id,
                    "model_path": result["model_path"],
                    "average_score": avg_score,
                    "recommended": avg_score > 0.7
                })
                
                if avg_score > best_score:
                    best_score = avg_score
                    best_model = persona_id
        
        deployment_info["recommended_model"] = best_model
        deployment_info["deployment_ready"] = best_score > 0.6
        
        if deployment_info["deployment_ready"]:
            deployment_info["deployment_instructions"] = [
                f"Copy model files from {self.config['output_paths']['models']}",
                "Update model configuration in main application",
                "Test model integration with existing chat system",
                "Monitor performance metrics in production"
            ]
        
        return deployment_info
    
    def _save_pipeline_results(self, results: Dict):
        """Save pipeline results to file"""
        results_path = Path(self.config["output_paths"]["validation"]) / "pipeline_results.json"
        results_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Pipeline results saved to {results_path}")

async def main():
    """Demo training coordinator"""
    logger.info("Initializing Training Pipeline Coordinator")
    
    coordinator = TrainingCoordinator()
    
    # For demo, just show what would happen
    logger.info("Training pipeline would execute the following stages:")
    logger.info("1. Process raw training data (YouTube videos, audio, transcripts)")
    logger.info("2. Validate data quality and filter low-quality samples")
    logger.info("3. Enhance with persona information and generate additional examples")
    logger.info("4. Train specialized models for different customer personas")
    logger.info("5. Validate model performance on held-out test data")
    logger.info("6. Prepare deployment packages for production integration")
    
    # Create example configuration
    config_path = "./training/config.json"
    if not Path(config_path).exists():
        example_config = {
            "data_sources": {
                "youtube_videos": "./training/raw_data/youtube/",
                "audio_recordings": "./training/raw_data/audio/",
                "transcripts": "./training/raw_data/transcripts/"
            },
            "output_paths": {
                "processed_data": "./training/processed_data/",
                "models": "./training/models/",
                "validation": "./training/validation/"
            },
            "training_params": {
                "model_name": "Qwen/Qwen2.5-0.5B-Instruct",
                "num_epochs": 3,
                "batch_size": 4,
                "learning_rate": 2e-5
            },
            "quality_thresholds": {
                "min_audio_quality": 0.7,
                "min_transcript_clarity": 0.8,
                "min_conversation_length": 100
            }
        }
        
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(example_config, f, indent=2)
        
        logger.info(f"Created example configuration at {config_path}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())