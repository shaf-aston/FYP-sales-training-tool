"""
Sales Roleplay Chatbot - Main Application Entry Point
Clean orchestration with proper error handling and service management
"""
import logging
import asyncio
import signal
import sys
from typing import Optional, Dict, Any
from pathlib import Path

# Import core services
from src.config.settings import get_config, get_config_manager
from src.services.voice_manager import VoiceManager
from src.services.ai_service import AIService
from src.models.core import VoiceProfile, ConversationTurn
from src.utils.dependencies import initialize_all, get_available_providers
from src.utils.file_utils import FileManager
from src.utils.validation import Validator

logger = logging.getLogger(__name__)

class ChatbotApplication:
    """Main chatbot application with clean service orchestration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize chatbot application
        
        Args:
            config_path: Path to configuration file
        """
        self.config_manager = None
        self.config = None
        self.voice_manager = None
        self.ai_service = None
        self.file_manager = None
        self.is_running = False
        
        # Initialize application
        self._initialize_app(config_path)
    
    def _initialize_app(self, config_path: Optional[str]):
        """Initialize application components"""
        try:
            # Initialize dependencies first
            initialize_all()
            
            # Load configuration
            if config_path:
                from src.config.settings import reload_config
                reload_config(config_path)
            
            self.config_manager = get_config_manager()
            self.config = self.config_manager.get_config()
            
            # Setup logging
            self._setup_logging()
            
            # Validate configuration
            validation = self.config_manager.validate_config()
            if not validation["valid"]:
                logger.warning(f"Configuration issues: {validation['issues']}")
            
            # Initialize file manager
            self.file_manager = FileManager(
                base_path=str(Path.cwd())
            )
            
            # Initialize voice manager
            voice_profile = VoiceProfile(
                model_name=self.config.tts.model_name,
                speaker_name=self.config.tts.speaker_name,
                gender=self.config.tts.gender,
                speed=self.config.tts.speed,
                volume=self.config.tts.volume,
                language="en"
            )
            
            confidence_thresholds = {
                "high": self.config.stt.high_confidence,
                "medium": self.config.stt.medium_confidence,
                "low": self.config.stt.low_confidence
            }
            
            self.voice_manager = VoiceManager(
                stt_provider=self.config.stt.provider,
                tts_provider=self.config.tts.provider,
                voice_profile=voice_profile,
                confidence_thresholds=confidence_thresholds
            )
            
            # Initialize AI service
            self.ai_service = AIService(
                model_name=self.config.ai.model_name,
                max_length=self.config.ai.max_length,
                temperature=self.config.ai.temperature,
                device=self.config.ai.device
            )
            
            logger.info("Chatbot application initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise
    
    def _setup_logging(self):
        """Setup application logging"""
        log_config = self.config.logging
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_config.level.upper()),
            format=log_config.format,
            handlers=[]
        )
        
        # Console handler
        if log_config.log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(log_config.format))
            logging.getLogger().addHandler(console_handler)
        
        # File handler
        if log_config.log_to_file:
            try:
                log_dir = Path(log_config.log_dir)
                log_dir.mkdir(parents=True, exist_ok=True)
                
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_dir / log_config.log_file,
                    maxBytes=log_config.max_file_size_mb * 1024 * 1024,
                    backupCount=log_config.backup_count
                )
                file_handler.setFormatter(logging.Formatter(log_config.format))
                logging.getLogger().addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Failed to setup file logging: {e}")
    
    def process_voice_input(self, audio_data: Any, 
                           language: Optional[str] = None) -> Dict[str, Any]:
        """
        Process voice input and generate response
        
        Args:
            audio_data: Audio input data
            language: Optional language specification
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Validate audio input
            audio_validation = Validator.validate_audio_input(
                audio_data,
                min_duration=0.1,
                max_duration=60.0
            )
            
            if not audio_validation["valid"]:
                return {
                    "success": False,
                    "error": f"Invalid audio: {'; '.join(audio_validation['errors'])}",
                    "suggestions": ["Please provide valid audio input"]
                }
            
            # Process audio with STT
            logger.info("Processing voice input...")
            stt_result = self.voice_manager.process_audio_input(audio_data, language)
            
            # Check if transcription was successful
            if not stt_result.text.strip():
                return {
                    "success": False,
                    "error": "No speech detected in audio",
                    "stt_result": stt_result,
                    "suggestions": [
                        "Speak more clearly",
                        "Check microphone settings",
                        "Reduce background noise"
                    ]
                }
            
            # Generate AI response
            logger.info(f"Generating AI response for: '{stt_result.text[:50]}...'")
            
            # Get conversation context
            context = self.ai_service.get_context_for_response()
            
            # Generate response
            ai_response = self.ai_service.generate_response(
                stt_result.text,
                context=context
            )
            
            # Generate TTS output
            tts_result = None
            if ai_response.text.strip():
                logger.info("Generating speech output...")
                tts_result = self.voice_manager.generate_speech_response(ai_response.text)
            
            # Create conversation turn
            conversation_turn = self.voice_manager.create_conversation_turn(
                stt_result=stt_result,
                ai_response=ai_response.text,
                tts_result=tts_result
            )
            
            # Update AI service history
            self.ai_service.add_to_history(stt_result.text, ai_response.text)
            
            # Generate feedback
            feedback = self.voice_manager.get_conversation_feedback()
            
            return {
                "success": True,
                "user_input": stt_result.text,
                "ai_response": ai_response.text,
                "audio_output": tts_result.audio_path if tts_result and tts_result.success else None,
                "conversation_turn": conversation_turn,
                "feedback": feedback,
                "confidence_level": stt_result.get_confidence_level(
                    self.voice_manager.confidence_thresholds["high"],
                    self.voice_manager.confidence_thresholds["medium"]
                ).value
            }
        
        except Exception as e:
            logger.error(f"Voice input processing failed: {e}")
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "suggestions": [
                    "Check audio format and quality",
                    "Ensure all services are running",
                    "Try again with clearer audio"
                ]
            }
    
    def process_text_input(self, text: str) -> Dict[str, Any]:
        """
        Process text input and generate response
        
        Args:
            text: Text input from user
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Validate text input
            text_validation = Validator.validate_text_input(
                text,
                min_length=1,
                max_length=500,
                allow_empty=False
            )
            
            if not text_validation["valid"]:
                return {
                    "success": False,
                    "error": f"Invalid text: {'; '.join(text_validation['errors'])}",
                    "suggestions": ["Please provide valid text input"]
                }
            
            sanitized_text = text_validation["sanitized"]
            
            # Generate AI response
            logger.info(f"Processing text input: '{sanitized_text[:50]}...'")
            
            context = self.ai_service.get_context_for_response()
            ai_response = self.ai_service.generate_response(
                sanitized_text,
                context=context
            )
            
            # Generate TTS output if enabled
            tts_result = None
            if ai_response.text.strip():
                logger.info("Generating speech output...")
                tts_result = self.voice_manager.generate_speech_response(ai_response.text)
            
            # Update AI service history
            self.ai_service.add_to_history(sanitized_text, ai_response.text)
            
            return {
                "success": True,
                "user_input": sanitized_text,
                "ai_response": ai_response.text,
                "audio_output": tts_result.audio_path if tts_result and tts_result.success else None,
                "ai_metadata": {
                    "confidence": ai_response.confidence,
                    "processing_time": ai_response.processing_time,
                    "model_used": ai_response.model_used,
                    "token_count": ai_response.token_count
                }
            }
        
        except Exception as e:
            logger.error(f"Text input processing failed: {e}")
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "suggestions": ["Please try again with different text"]
            }
    
    def get_session_analysis(self) -> Dict[str, Any]:
        """Get comprehensive session analysis"""
        try:
            # Voice session analysis
            voice_analysis = self.voice_manager.analyze_session_quality()
            
            # AI service info
            ai_info = self.ai_service.get_model_info()
            
            # Service availability
            available_providers = get_available_providers()
            
            # Service info
            service_info = self.voice_manager.get_service_info()
            
            return {
                "session_analysis": voice_analysis,
                "ai_service_info": ai_info,
                "available_providers": available_providers,
                "service_info": service_info,
                "configuration": {
                    "stt_provider": self.config.stt.provider,
                    "tts_provider": self.config.tts.provider,
                    "ai_model": self.config.ai.model_name,
                    "confidence_thresholds": self.voice_manager.confidence_thresholds
                }
            }
        
        except Exception as e:
            logger.error(f"Session analysis failed: {e}")
            return {"error": str(e)}
    
    def export_session_data(self, output_path: Optional[str] = None) -> str:
        """
        Export session data to file
        
        Args:
            output_path: Optional output file path
            
        Returns:
            Path to exported file
        """
        try:
            # Get session data
            session_data = self.voice_manager.export_session_data()
            
            # Add configuration and analysis
            session_data["configuration"] = {
                "app_name": self.config.app_name,
                "version": self.config.version,
                "stt_config": self.config.stt.__dict__,
                "tts_config": self.config.tts.__dict__,
                "ai_config": self.config.ai.__dict__
            }
            
            session_data["analysis"] = self.get_session_analysis()
            
            # Generate output path if not provided
            if not output_path:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"session_export_{timestamp}.json"
            
            # Save to file
            success = self.file_manager.safe_write_json(session_data, output_path)
            
            if success:
                logger.info(f"Session data exported to {output_path}")
                return output_path
            else:
                raise Exception("Failed to save export file")
        
        except Exception as e:
            logger.error(f"Session export failed: {e}")
            raise
    
    def shutdown(self):
        """Clean shutdown of application"""
        logger.info("Shutting down chatbot application...")
        
        try:
            # Cleanup file manager
            if self.file_manager:
                self.file_manager.cleanup_temp_files()
            
            # Clear AI service history
            if self.ai_service:
                self.ai_service.clear_history()
            
            logger.info("Chatbot application shut down successfully")
        
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def main():
    """Main entry point for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sales Roleplay Chatbot")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--export-session", help="Export session data to file")
    
    args = parser.parse_args()
    
    try:
        # Initialize application
        app = ChatbotApplication(config_path=args.config)
        
        if args.debug:
            app.config.debug = True
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Setup signal handlers for clean shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            app.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Chatbot application started successfully")
        logger.info("Use Ctrl+C to exit")
        
        # Keep application running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        sys.exit(1)
    
    finally:
        if 'app' in locals():
            app.shutdown()

if __name__ == "__main__":
    main()