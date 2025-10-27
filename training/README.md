# Sales Training Model - Training Infrastructure

This directory contains the complete model training infrastructure for the sales roleplay chatbot system.

## Overview

The training system is designed to process various types of sales conversation data and train specialized models for different customer personas and sales scenarios.

## Architecture Components

### 1. Data Processing Pipeline (`data_processing_pipeline.py`)
- **Purpose**: Processes raw training data from multiple sources
- **Capabilities**:
  - YouTube video processing with speech-to-text transcription
  - Audio recording analysis with feature extraction
  - Transcript processing and normalization
  - Sales technique identification and scoring
  - Performance analysis (clarity, filler words, pacing)

### 2. Roleplay Training Components (`roleplay_training.py`)
- **PersonaResponseGenerator**: Dynamic personality-consistent reply generation
- **ObjectionHandler**: Realistic challenge generation for sales training
- **FeatureExtraction**: Customer personality trait extraction from conversations
- **Persona Profiles**: Predefined customer personas (skeptical manager, busy executive, etc.)

### 3. Model Training (`model_training.py`)
- **ModelTrainer**: Handles fine-tuning of the base Qwen model
- **SalesConversationDataset**: Custom dataset class for sales conversation data
- **ModelEvaluator**: Comprehensive model performance evaluation
- **TrainingConfig**: Configurable training parameters

### 4. Feedback System (`feedback_system.py`)
- **SalesPerformanceClassifier**: Multi-dimensional performance analysis
- **FeedbackGenerator**: Specific, actionable improvement suggestions
- **ProgressTracker**: Long-term improvement tracking and analytics
- **Performance Metrics**: Comprehensive scoring across sales techniques

### 5. Training Coordinator (`training_coordinator.py`)
- **TrainingCoordinator**: Orchestrates the complete training pipeline
- **Pipeline Stages**: Data processing → Validation → Enhancement → Training → Validation → Deployment
- **Configuration Management**: Centralized training parameter management

## Directory Structure

```
training/
├── raw_data/                    # Raw training materials
│   ├── youtube/                 # YouTube video files (.mp4)
│   ├── audio/                   # Audio recordings (.wav, .mp3)
│   └── transcripts/             # Text transcripts (.txt, .json)
├── processed_data/              # Processed and normalized training data
├── models/                      # Trained model outputs
│   ├── persona_skeptical_manager/
│   ├── persona_busy_executive/
│   └── persona_friendly_small_business/
├── validation/                  # Validation results and metrics
└── config.json                  # Training configuration
```

## Usage

### 1. Prepare Training Data
Place your training materials in the appropriate raw_data subdirectories:
- YouTube videos: `raw_data/youtube/`
- Audio recordings: `raw_data/audio/`
- Text transcripts: `raw_data/transcripts/`

### 2. Configure Training
Edit `config.json` to adjust training parameters:
```json
{
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
```

### 3. Run Training Pipeline
```python
from training.training_coordinator import TrainingCoordinator
import asyncio

async def run_training():
    coordinator = TrainingCoordinator()
    results = await coordinator.run_full_pipeline()
    print(f"Training completed: {results['success']}")

asyncio.run(run_training())
```

### 4. Individual Component Usage

#### Data Processing
```python
from training.data_processing_pipeline import DataProcessingPipeline

processor = DataProcessingPipeline()
processed_data = await processor.process_youtube_video("path/to/video.mp4")
```

#### Persona Training
```python
from training.roleplay_training import PersonaResponseGenerator

generator = PersonaResponseGenerator()
response = generator.generate_persona_response(
    "skeptical_manager", 
    "I'm not sure about the price"
)
```

#### Performance Analysis
```python
from training.feedback_system import SalesPerformanceClassifier

classifier = SalesPerformanceClassifier()
performance = classifier.analyze_conversation(
    conversation_text, 
    user_responses
)
```

## Key Features

### Persona-Based Training
- **Multiple Customer Personas**: Skeptical Manager, Busy Executive, Friendly Small Business Owner
- **Personality-Consistent Responses**: Each persona has distinct communication styles and objection patterns
- **Adaptive Difficulty**: Training scenarios adjust based on learner progress

### Comprehensive Analysis
- **Sales Technique Recognition**: Rapport building, needs discovery, value presentation, objection handling, closing
- **Performance Scoring**: Multi-dimensional evaluation of sales conversations
- **Progress Tracking**: Long-term improvement analytics and trend analysis

### Quality Control
- **Data Validation**: Automatic filtering of low-quality training data
- **Audio Quality Assessment**: MFCC analysis for audio clarity scoring
- **Transcript Normalization**: Consistent formatting and structure

### Feedback Generation
- **Specific Suggestions**: Actionable improvement recommendations
- **Priority Ranking**: High/medium/low priority feedback items
- **Example-Based Learning**: Concrete examples of better responses

## Dependencies

Core dependencies for the training system:
- `transformers`: Hugging Face model training
- `torch`: PyTorch for neural network operations
- `whisper`: OpenAI Whisper for speech-to-text
- `librosa`: Audio feature extraction
- `pandas`: Data manipulation
- `scikit-learn`: Machine learning utilities
- `wandb`: Experiment tracking (optional)

## Integration with Main Application

The training system is designed to be completely separate from the main chatbot application, allowing for:
- **Independent Development**: Training improvements don't affect production
- **Model Versioning**: Multiple trained models can be maintained
- **A/B Testing**: Different models can be evaluated in controlled experiments
- **Continuous Learning**: New training data can be processed without downtime

## Future Enhancements

Planned improvements to the training infrastructure:
1. **Real-time Learning**: Incorporation of user feedback into model updates
2. **Advanced Metrics**: More sophisticated conversation quality measures
3. **Multi-modal Training**: Integration of visual cues and body language
4. **Automated Data Collection**: APIs for gathering training data from various sources
5. **Distributed Training**: Support for training across multiple GPUs/machines

## Monitoring and Logging

The training system includes comprehensive logging and monitoring:
- **Pipeline Progress**: Real-time updates on training stages
- **Performance Metrics**: Detailed evaluation results
- **Error Handling**: Graceful failure recovery and reporting
- **Resource Usage**: CPU/GPU/memory utilization tracking

This training infrastructure provides a robust foundation for developing and improving the sales roleplay chatbot's conversation capabilities.