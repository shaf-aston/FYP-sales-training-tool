"""
Data Processing Pipeline for Sales Training Model
Based on the architectural design diagram for model training
"""
import os
import json
import pandas as pd
import librosa
import whisper
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedData:
    """Container for processed training data"""
    text: str
    audio_features: Optional[Dict] = None
    sales_techniques: Optional[List[str]] = None
    performance_metrics: Optional[Dict] = None
    metadata: Optional[Dict] = None

class DataProcessingPipeline:
    """
    Main data processing pipeline for sales training data
    Handles: Audio → Speech-to-text, Video → Extract audio → transcribe,
    Text → Clean and standardize
    """
    
    def __init__(self, base_path: str = "training"):
        self.base_path = Path(base_path)
        self.raw_data_path = self.base_path / "raw_data"
        self.processed_data_path = self.base_path / "processed_data"
        
        # Create directories if they don't exist
        for path in [self.raw_data_path, self.processed_data_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        # Initialize Whisper model for speech-to-text
        # try:
        #     self.whisper_model = whisper.load_model("base")
        #     logger.info("Whisper model loaded successfully")
        # except Exception as e:
        #     logger.warning(f"Could not load Whisper model: {e}")
        #     self.whisper_model = None
    
    def process_youtube_videos(self, video_files: List[str]) -> List[ProcessedData]:
        """Process YouTube sales training videos"""
        logger.info(f"Processing {len(video_files)} YouTube videos")
        processed_data = []
        
        for video_file in video_files:
            try:
                # Extract audio from video
                audio_path = self._extract_audio_from_video(video_file)
                
                # Transcribe audio to text
                transcript = "Placeholder transcript for video file" # self._transcribe_audio(audio_path)
                
                # Process the transcript
                processed = self._process_transcript(transcript, source="youtube", file=video_file)
                processed_data.append(processed)
                
            except Exception as e:
                logger.error(f"Error processing video {video_file}: {e}")
        
        return processed_data
    
    def process_audio_recordings(self, audio_files: List[str]) -> List[ProcessedData]:
        """Process audio recordings (sales calls, training audio)"""
        logger.info(f"Processing {len(audio_files)} audio recordings")
        processed_data = []
        
        for audio_file in audio_files:
            try:
                # Transcribe audio to text
                transcript = "Placeholder transcript for audio file" # self._transcribe_audio(audio_file)
                
                # Extract audio features
                audio_features = self._extract_audio_features(audio_file)
                
                # Process the transcript
                processed = self._process_transcript(
                    transcript, 
                    source="audio_recording", 
                    file=audio_file,
                    audio_features=audio_features
                )
                processed_data.append(processed)
                
            except Exception as e:
                logger.error(f"Error processing audio {audio_file}: {e}")
        
        return processed_data
    
    def process_transcripts(self, transcript_files: List[str]) -> List[ProcessedData]:
        """Process existing text transcripts"""
        logger.info(f"Processing {len(transcript_files)} transcripts")
        processed_data = []
        
        for transcript_file in transcript_files:
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                
                processed = self._process_transcript(
                    transcript, 
                    source="transcript", 
                    file=transcript_file
                )
                processed_data.append(processed)
                
            except Exception as e:
                logger.error(f"Error processing transcript {transcript_file}: {e}")
        
        return processed_data
    
    def _extract_audio_from_video(self, video_path: str) -> str:
        """Extract audio from video file"""
        # This would use ffmpeg or similar to extract audio
        # For now, return a placeholder path
        audio_path = video_path.replace('.mp4', '.wav').replace('.avi', '.wav')
        logger.info(f"Extracting audio from {video_path} to {audio_path}")
        return audio_path
    
    # def _transcribe_audio(self, audio_path: str) -> str:
    #     """Convert audio to text using Whisper"""
    #     if not self.whisper_model:
    #         logger.warning("Whisper model not available, returning placeholder transcript")
    #         return "Placeholder transcript for audio file"
        
    #     try:
    #         result = self.whisper_model.transcribe(audio_path)
    #         return result["text"]
    #     except Exception as e:
    #         logger.error(f"Error transcribing audio: {e}")
    #         return "Error transcribing audio"
    
    def _extract_audio_features(self, audio_path: str) -> Dict:
        """Extract audio features for analysis"""
        try:
            # Load audio file
            y, sr = librosa.load(audio_path)
            
            # Extract features
            features = {
                'mfcc': librosa.feature.mfcc(y=y, sr=sr).mean(axis=1).tolist(),
                'spectral_centroid': float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
                'spectral_rolloff': float(librosa.feature.spectral_rolloff(y=y, sr=sr).mean()),
                'zero_crossing_rate': float(librosa.feature.zero_crossing_rate(y).mean()),
                'tempo': float(librosa.beat.tempo(y=y, sr=sr)[0]),
                'duration': float(len(y) / sr)
            }
            
            return features
        except Exception as e:
            logger.error(f"Error extracting audio features: {e}")
            return {}
    
    def _process_transcript(self, transcript: str, source: str, file: str, 
                           audio_features: Optional[Dict] = None) -> ProcessedData:
        """Clean and process transcript text"""
        # Clean text
        cleaned_text = self._clean_text(transcript)
        
        # Extract sales techniques
        sales_techniques = self._extract_sales_techniques(cleaned_text)
        
        # Analyze performance indicators
        performance_metrics = self._analyze_performance(cleaned_text, audio_features)
        
        # Create metadata
        metadata = {
            'source': source,
            'original_file': file,
            'processed_at': datetime.now().isoformat(),
            'word_count': len(cleaned_text.split()),
            'char_count': len(cleaned_text)
        }
        
        return ProcessedData(
            text=cleaned_text,
            audio_features=audio_features,
            sales_techniques=sales_techniques,
            performance_metrics=performance_metrics,
            metadata=metadata
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and standardize text"""
        # Remove special characters, fix encoding
        text = re.sub(r'[^\w\s.,!?;:-]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Basic text cleaning
        text = text.replace('\n', ' ').replace('\t', ' ')
        
        return text
    
    def _extract_sales_techniques(self, text: str) -> List[str]:
        """Extract sales techniques from text"""
        techniques = []
        text_lower = text.lower()
        
        # Define sales technique patterns
        technique_patterns = {
            'open_ended_questions': [r'what.*?', r'how.*?', r'why.*?', r'when.*?', r'where.*?'],
            'objection_handling': [r'i understand.*but', r'that\'s a great point.*however', r'many clients feel that way'],
            'value_proposition': [r'the benefit is', r'this will save you', r'roi', r'return on investment'],
            'closing_techniques': [r'would you like to move forward', r'shall we get started', r'ready to begin'],
            'rapport_building': [r'i appreciate', r'thank you for', r'i understand how you feel'],
            'active_listening': [r'let me make sure i understand', r'so what you\'re saying is', r'if i heard correctly']
        }
        
        for technique, patterns in technique_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    techniques.append(technique)
                    break
        
        return list(set(techniques))  # Remove duplicates
    
    def _analyze_performance(self, text: str, audio_features: Optional[Dict] = None) -> Dict:
        """Analyze communication performance"""
        metrics = {}
        
        # Text-based metrics
        words = text.split()
        metrics['word_count'] = len(words)
        metrics['avg_word_length'] = sum(len(word) for word in words) / len(words) if words else 0
        metrics['filler_words'] = self._count_filler_words(text)
        metrics['question_count'] = text.count('?')
        metrics['clarity_score'] = self._calculate_clarity_score(text)
        
        # Audio-based metrics (if available)
        if audio_features:
            metrics['speech_rate'] = metrics['word_count'] / audio_features.get('duration', 1)
            metrics['tempo'] = audio_features.get('tempo', 0)
            metrics['vocal_variety'] = audio_features.get('spectral_centroid', 0)
        
        return metrics
    
    def _count_filler_words(self, text: str) -> int:
        """Count filler words in text"""
        filler_words = ['um', 'uh', 'like', 'you know', 'so', 'actually', 'basically']
        text_lower = text.lower()
        count = 0
        for word in filler_words:
            count += text_lower.count(word)
        return count
    
    def _calculate_clarity_score(self, text: str) -> float:
        """Calculate a basic clarity score"""
        words = text.split()
        if not words:
            return 0.0
        
        # Simple clarity heuristics
        avg_word_length = sum(len(word) for word in words) / len(words)
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        avg_sentence_length = len(words) / max(sentence_count, 1)
        
        # Scoring logic (simplified)
        clarity_score = min(100, (20 - avg_sentence_length) * 5 + (10 - avg_word_length) * 10)
        return max(0, clarity_score)
    
    def normalize_formats(self, processed_data: List[ProcessedData]) -> List[Dict]:
        """Normalize all processed data into a standard format"""
        logger.info(f"Normalizing {len(processed_data)} processed data items")
        
        normalized_data = []
        for item in processed_data:
            normalized = {
                'id': f"training_{len(normalized_data):06d}",
                'text': item.text,
                'audio_features': item.audio_features or {},
                'sales_techniques': item.sales_techniques or [],
                'performance_metrics': item.performance_metrics or {},
                'metadata': item.metadata or {},
                'created_at': datetime.now().isoformat()
            }
            normalized_data.append(normalized)
        
        return normalized_data
    
    def save_processed_data(self, normalized_data: List[Dict], filename: str = None):
        """Save processed data to JSON file"""
        if filename is None:
            filename = f"processed_training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_path = self.processed_data_path / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(normalized_data)} processed items to {output_path}")
        return str(output_path)

def main():
    """Main function to demonstrate the pipeline"""
    logger.info("Initializing Data Processing Pipeline")
    
    pipeline = DataProcessingPipeline()
    
    # Example usage (with placeholder data)
    logger.info("Pipeline initialized successfully")
    logger.info("Ready to process:")
    logger.info("- YouTube videos in training/raw_data/youtube/")
    logger.info("- Audio recordings in training/raw_data/audio/")
    logger.info("- Transcripts in training/raw_data/transcripts/")
    
    # When you have actual data, you would run:
    # youtube_files = list(pipeline.raw_data_path.glob("youtube/*.mp4"))
    # audio_files = list(pipeline.raw_data_path.glob("audio/*.wav"))
    # transcript_files = list(pipeline.raw_data_path.glob("transcripts/*.txt"))
    # 
    # all_processed = []
    # all_processed.extend(pipeline.process_youtube_videos([str(f) for f in youtube_files]))
    # all_processed.extend(pipeline.process_audio_recordings([str(f) for f in audio_files]))
    # all_processed.extend(pipeline.process_transcripts([str(f) for f in transcript_files]))
    # 
    # normalized_data = pipeline.normalize_formats(all_processed)
    # pipeline.save_processed_data(normalized_data)

if __name__ == "__main__":
    main()