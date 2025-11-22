"""
AI Conversation Service
Handles AI model interactions and response generation
"""
import logging
import time
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass

from src.models.core import QualityMetrics
from src.utils.dependencies import (
    transformers, torch,
    DEPENDENCIES, validate_provider
)

logger = logging.getLogger(__name__)

@dataclass
class AIResponse:
    """AI response with metadata"""
    text: str
    confidence: float
    processing_time: float
    model_used: str
    token_count: int
    quality_metrics: QualityMetrics
    error: Optional[str] = None

class AIService:
    """AI conversation service with multiple providers"""
    
    def __init__(self, 
                 model_name: str = "microsoft/DialoGPT-medium",
                 max_length: int = 512,
                 temperature: float = 0.7,
                 device: str = "auto"):
        """
        Initialize AI service
        
        Args:
            model_name: Model to use for generation
            max_length: Maximum response length
            temperature: Response creativity (0.0-1.0)
            device: Device for inference
        """
        self.model_name = model_name
        self.max_length = max_length
        self.temperature = temperature
        self.device = self._get_device(device)
        
        self.model = None
        self.tokenizer = None
        self.conversation_history = []
        self._initialize_model()
    
    def _get_device(self, device: str) -> str:
        """Determine best device"""
        if device == "auto":
            if DEPENDENCIES["torch"] and torch.cuda.is_available():
                return "cuda"
            return "cpu"
        return device
    
    def _initialize_model(self):
        """Initialize the AI model"""
        if not validate_provider("ai", "transformers"):
            logger.error("Transformers not available")
            self._setup_fallback()
            return
        
        try:
            logger.info(f"Loading model: {self.model_name}")
            
            self.tokenizer = transformers.AutoTokenizer.from_pretrained(
                self.model_name,
                padding_side='left'
            )
            
            self.model = transformers.AutoLMHeadModel.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            
            self.model.to(self.device)
            self.model.eval()
            
            # Set pad token if needed
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            self._setup_fallback()
    
    def _setup_fallback(self):
        """Setup fallback response system"""
        logger.warning("Setting up fallback AI responses")
        self.model = None
        self.tokenizer = None
        
        # Load fallback responses
        try:
            from src.fallback_responses import get_fallback_response
            self.fallback_handler = get_fallback_response
        except ImportError:
            # Create simple fallback
            self.fallback_handler = lambda text: (
                "I understand you're saying: " + text + 
                ". How can I help you with that?"
            )
    
    def generate_response(self, user_input: str, 
                         context: Optional[List[str]] = None,
                         persona: Optional[str] = None) -> AIResponse:
        """
        Generate AI response
        
        Args:
            user_input: User's input text
            context: Previous conversation context
            persona: AI persona/character to use
            
        Returns:
            AIResponse with generated text and metadata
        """
        start_time = time.time()
        
        if not user_input.strip():
            return AIResponse(
                text="I didn't catch that. Could you please say that again?",
                confidence=1.0,
                processing_time=time.time() - start_time,
                model_used="fallback",
                token_count=0,
                quality_metrics=QualityMetrics(),
                error="Empty input"
            )
        
        # Use fallback if model not available
        if self.model is None:
            return self._generate_fallback_response(user_input, start_time)
        
        try:
            return self._generate_model_response(user_input, context, persona, start_time)
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return self._generate_fallback_response(user_input, start_time, str(e))
    
    def _generate_model_response(self, user_input: str,
                                context: Optional[List[str]],
                                persona: Optional[str],
                                start_time: float) -> AIResponse:
        """Generate response using loaded model"""
        # Prepare conversation history
        conversation_text = self._prepare_conversation_context(
            user_input, context, persona
        )
        
        # Tokenize input
        inputs = self.tokenizer.encode(
            conversation_text,
            return_tensors="pt",
            max_length=self.max_length // 2,
            truncation=True
        ).to(self.device)
        
        # Generate response
        with torch.no_grad():
            outputs = self.model.generate(
                inputs,
                max_length=inputs.shape[1] + self.max_length // 2,
                temperature=self.temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                num_return_sequences=1
            )
        
        # Decode response
        response_tokens = outputs[0][inputs.shape[1]:]
        response_text = self.tokenizer.decode(
            response_tokens, 
            skip_special_tokens=True
        ).strip()
        
        # Clean up response
        response_text = self._clean_response(response_text)
        
        processing_time = time.time() - start_time
        
        # Calculate confidence and quality metrics
        confidence = self._calculate_response_confidence(response_text, user_input)
        quality_metrics = self._calculate_quality_metrics(
            response_text, processing_time, confidence
        )
        
        return AIResponse(
            text=response_text,
            confidence=confidence,
            processing_time=processing_time,
            model_used=self.model_name,
            token_count=len(response_tokens),
            quality_metrics=quality_metrics
        )
    
    def _generate_fallback_response(self, user_input: str, 
                                   start_time: float,
                                   error: Optional[str] = None) -> AIResponse:
        """Generate fallback response"""
        try:
            response_text = self.fallback_handler(user_input)
        except:
            response_text = "I'm having trouble understanding. Could you rephrase that?"
        
        processing_time = time.time() - start_time
        
        return AIResponse(
            text=response_text,
            confidence=0.5,  # Medium confidence for fallback
            processing_time=processing_time,
            model_used="fallback",
            token_count=len(response_text.split()),
            quality_metrics=QualityMetrics(
                clarity=0.8,
                noise_level=0.1,
                volume=0.8
            ),
            error=error
        )
    
    def _prepare_conversation_context(self, user_input: str,
                                     context: Optional[List[str]],
                                     persona: Optional[str]) -> str:
        """Prepare conversation context for model"""
        conversation_parts = []
        
        # Add persona if provided
        if persona:
            conversation_parts.append(f"System: {persona}")
        
        # Add recent context
        if context:
            for turn in context[-3:]:  # Last 3 turns for context
                conversation_parts.append(turn)
        
        # Add current user input
        conversation_parts.append(f"User: {user_input}")
        conversation_parts.append("Assistant:")
        
        return "\n".join(conversation_parts)
    
    def _clean_response(self, response_text: str) -> str:
        """Clean and format AI response"""
        # Remove common artifacts
        response_text = response_text.replace("User:", "").replace("Assistant:", "")
        
        # Remove repetitive patterns
        lines = response_text.split('\n')
        cleaned_lines = []
        prev_line = ""
        
        for line in lines:
            line = line.strip()
            if line and line != prev_line:  # Remove empty and duplicate lines
                cleaned_lines.append(line)
                prev_line = line
        
        response_text = " ".join(cleaned_lines)
        
        # Ensure reasonable length
        if len(response_text) > 500:
            # Truncate at last complete sentence
            sentences = response_text.split('.')
            truncated = []
            length = 0
            
            for sentence in sentences:
                if length + len(sentence) < 400:
                    truncated.append(sentence)
                    length += len(sentence)
                else:
                    break
            
            response_text = '.'.join(truncated)
            if response_text and not response_text.endswith('.'):
                response_text += '.'
        
        return response_text or "I understand. Please continue."
    
    def _calculate_response_confidence(self, response: str, user_input: str) -> float:
        """Calculate confidence score for generated response"""
        # Basic heuristics for response quality
        confidence = 0.8  # Base confidence
        
        # Length appropriateness
        if 10 <= len(response) <= 300:
            confidence += 0.1
        elif len(response) < 5:
            confidence -= 0.3
        
        # Coherence indicators
        if any(word in response.lower() for word in ['understand', 'help', 'can', 'would']):
            confidence += 0.05
        
        # Avoid repetition with input
        input_words = set(user_input.lower().split())
        response_words = set(response.lower().split())
        overlap = len(input_words.intersection(response_words))
        
        if overlap > len(input_words) * 0.7:  # Too much repetition
            confidence -= 0.2
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_quality_metrics(self, response: str, 
                                  processing_time: float,
                                  confidence: float) -> QualityMetrics:
        """Calculate quality metrics for response"""
        # Clarity based on sentence structure
        sentences = response.count('.')
        words = len(response.split())
        
        if words > 0 and sentences > 0:
            avg_sentence_length = words / sentences
            clarity = min(1.0, confidence * (1.0 if 5 <= avg_sentence_length <= 20 else 0.8))
        else:
            clarity = confidence * 0.7
        
        # Processing efficiency
        if processing_time > 0:
            efficiency_score = min(1.0, 10.0 / processing_time)  # Target: <10s
        else:
            efficiency_score = 1.0
        
        return QualityMetrics(
            clarity=clarity,
            noise_level=max(0.0, 1.0 - confidence),
            volume=0.8  # Standard volume for text
        )
    
    def add_to_history(self, user_input: str, ai_response: str):
        """Add interaction to conversation history"""
        self.conversation_history.append({
            "user": user_input,
            "assistant": ai_response,
            "timestamp": time.time()
        })
        
        # Keep only recent history to manage memory
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_context_for_response(self) -> List[str]:
        """Get formatted context from conversation history"""
        context = []
        for turn in self.conversation_history[-3:]:  # Last 3 turns
            context.append(f"User: {turn['user']}")
            context.append(f"Assistant: {turn['assistant']}")
        return context
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_length": self.max_length,
            "temperature": self.temperature,
            "available": self.model is not None,
            "conversation_turns": len(self.conversation_history)
        }