# Training Pipeline - Architectural Overview

## 🏗️ High-Level Architecture

This training pipeline follows a **modular, multi-path architecture** designed for comprehensive sales roleplay chatbot training.

### Architecture Diagram

See `architecture_diagram.mmd` for the complete Mermaid diagram, or `ARCHITECTURE_OVERVIEW.md` for detailed breakdown.

---

## 📊 Pipeline Stages

### Stage 1: Raw Data Sources
Multiple data source integration:
- **Local Transcripts**: Text files from roleplay sessions
- **Audio Recordings**: Sales call recordings (with STT processing)
- **External Datasets**: HuggingFace, SalesBot, CallCenter datasets
- **Third-party APIs**: Fathom.ai, Fireflies.ai integration ready

**Location**: `pipeline/data_sources/`

### Stage 2: Foundation Layer
Data processing and feature extraction:
- **Audio Processing**: Speech-to-text, tone & pacing analysis
- **Text Processing**: Sales technique extraction, NEPQ analysis
- **Data Repository**: Centralized normalized data storage

**Location**: `pipeline/foundation/`

### Stage 3: Processing Pipeline
Data normalization and preparation:
- **Format Normalization**: Audio → Text, Video → Audio → Text
- **Training Pair Generation**: Input-output conversation pairs
- **Quality Filtering**: Remove low-quality data

**Location**: `pipeline/processing/`

### Stage 4A: Roleplay Partner Training Path
Trains the conversational AI partner:
- **Persona Response Generation**: Dynamic personality-based responses
- **Natural Dialogue Patterns**: Realistic conversation flow
- **Objection Handling**: Realistic sales objections

### Stage 4B: Feedback System Training Path
Trains the performance analysis system:
- **Performance Classification**: Skill level categorization
- **Suggestion Generation**: Actionable improvement tips
- **Analysis Components**: Communication effectiveness, NEPQ, Active listening

### Stage 5: Validation & Quality Control
Ensures training quality through expert comparison and metrics

### Stage 6: Continuous Improvement Loop
Feedback-driven refinement and model improvement

---

## 🚀 Quick Start

### Run Data Processing Pipeline

```bash
python training/run_architectural_pipeline.py
```

This processes all data sources, extracts features, creates training pairs, and saves to the repository.

---

## 📁 Directory Structure

```
training/
├── pipeline/                      # New modular pipeline
│   ├── data_sources/             # Data loaders
│   ├── foundation/               # Processing layer
│   ├── processing/               # Normalization
│   ├── training_paths/           # Training paths
│   └── validation/               # Quality control
├── data/                         # Data storage
│   ├── raw/                      # Raw data sources
│   └── processed/                # Processed repository
├── scripts/                      # Legacy scripts
├── run_architectural_pipeline.py # Main pipeline runner
└── architecture_diagram.mmd      # Architecture diagram
```

---

## 📚 Documentation

- `ARCHITECTURE_OVERVIEW.md` - Detailed architecture breakdown
- `architecture_diagram.mmd` - Visual architecture diagram
- `DOCUMENTATION_INDEX.md` - Complete documentation index

---

## Structure (Legacy):
- `conversations/` - Training conversation datasets
- `personas/` - Persona-specific training data
- `scenarios/` - Sales scenario datasets
- `feedback/` - Training feedback data