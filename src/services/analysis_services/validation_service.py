"""
Comprehensive Validation Service for Sales Training System
Handles input validation, output verification, safety checks, and quality assurance
"""

import re
import json
import time
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import unicodedata

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ValidationType(Enum):
    """Types of validation checks"""
    INPUT_SAFETY = "input_safety"
    OUTPUT_QUALITY = "output_quality"
    CONTENT_APPROPRIATENESS = "content_appropriateness"
    TECHNICAL_COMPLIANCE = "technical_compliance"
    BUSINESS_RULES = "business_rules"
    PERFORMANCE = "performance"

@dataclass
class ValidationResult:
    """Container for validation results"""
    validation_id: str
    validation_type: ValidationType
    level: ValidationLevel
    passed: bool
    message: str
    details: Dict[str, Any]
    timestamp: str
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['validation_type'] = self.validation_type.value
        data['level'] = self.level.value
        return data

@dataclass
class ValidationConfig:
    """Configuration for validation system"""
    enable_input_sanitization: bool = True
    enable_profanity_filter: bool = True
    enable_pii_detection: bool = True
    enable_content_safety: bool = True
    enable_output_quality_checks: bool = True
    enable_business_rules: bool = True
    max_input_length: int = 2000
    max_output_length: int = 1000
    allowed_languages: List[str] = None
    blocked_patterns: List[str] = None
    
    def __post_init__(self):
        if self.allowed_languages is None:
            self.allowed_languages = ["en", "es", "fr", "de"]
        if self.blocked_patterns is None:
            self.blocked_patterns = []

class ComprehensiveValidationService:
    """Advanced validation service for comprehensive input/output validation and safety"""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        
        # Validation history and statistics
        self.validation_history = []
        self.validation_stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'by_type': {},
            'by_level': {}
        }
        
        # Initialize validation components
        self.input_validator = InputValidator(self.config)
        self.output_validator = OutputValidator(self.config)
        self.safety_validator = SafetyValidator(self.config)
        self.quality_validator = QualityValidator(self.config)
        self.business_validator = BusinessRulesValidator(self.config)
        
        logger.info("Comprehensive Validation Service initialized")
    
    def validate_input(self, input_data: Dict[str, Any], 
                      validation_context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Comprehensive input validation"""
        start_time = time.time()
        results = []
        
        # Basic input validation
        results.extend(self.input_validator.validate_basic_input(input_data))
        
        # Safety validation
        if self.config.enable_content_safety:
            results.extend(self.safety_validator.validate_input_safety(input_data))
        
        # Business rules validation
        if self.config.enable_business_rules and validation_context:
            results.extend(self.business_validator.validate_input_rules(input_data, validation_context))
        
        # Update statistics
        self._update_validation_stats(results)
        
        # Store validation history
        validation_record = {
            'type': 'input_validation',
            'timestamp': datetime.now().isoformat(),
            'processing_time': time.time() - start_time,
            'results': [r.to_dict() for r in results],
            'total_checks': len(results),
            'failed_checks': len([r for r in results if not r.passed])
        }
        
        self.validation_history.append(validation_record)
        
        return results
    
    def validate_output(self, output_data: Dict[str, Any], 
                       input_context: Optional[Dict[str, Any]] = None,
                       validation_context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Comprehensive output validation"""
        start_time = time.time()
        results = []
        
        # Basic output validation
        results.extend(self.output_validator.validate_basic_output(output_data))
        
        # Quality validation
        if self.config.enable_output_quality_checks:
            results.extend(self.quality_validator.validate_output_quality(output_data, input_context))
        
        # Safety validation
        if self.config.enable_content_safety:
            results.extend(self.safety_validator.validate_output_safety(output_data))
        
        # Business rules validation
        if self.config.enable_business_rules and validation_context:
            results.extend(self.business_validator.validate_output_rules(output_data, validation_context))
        
        # Update statistics
        self._update_validation_stats(results)
        
        # Store validation history
        validation_record = {
            'type': 'output_validation',
            'timestamp': datetime.now().isoformat(),
            'processing_time': time.time() - start_time,
            'results': [r.to_dict() for r in results],
            'total_checks': len(results),
            'failed_checks': len([r for r in results if not r.passed])
        }
        
        self.validation_history.append(validation_record)
        
        return results
    
    def validate_conversation(self, conversation_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate entire conversation flow"""
        start_time = time.time()
        results = []
        
        # Validate conversation structure
        results.extend(self._validate_conversation_structure(conversation_data))
        
        # Validate conversation content
        results.extend(self._validate_conversation_content(conversation_data))
        
        # Validate conversation flow
        results.extend(self._validate_conversation_flow(conversation_data))
        
        # Update statistics
        self._update_validation_stats(results)
        
        return results
    
    def sanitize_input(self, input_text: str) -> Tuple[str, List[ValidationResult]]:
        """Sanitize input text and return cleaned version with validation results"""
        start_time = time.time()
        results = []
        sanitized_text = input_text
        
        if not self.config.enable_input_sanitization:
            return sanitized_text, results
        
        # Remove potentially harmful characters
        sanitized_text = self._remove_harmful_characters(sanitized_text)
        
        # Normalize unicode
        sanitized_text = unicodedata.normalize('NFKD', sanitized_text)
        
        # Remove excessive whitespace
        sanitized_text = re.sub(r'\s+', ' ', sanitized_text).strip()
        
        # Truncate if too long
        if len(sanitized_text) > self.config.max_input_length:
            original_length = len(sanitized_text)
            sanitized_text = sanitized_text[:self.config.max_input_length]
            
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.INPUT_SAFETY,
                level=ValidationLevel.WARNING,
                passed=True,
                message=f"Input truncated from {original_length} to {len(sanitized_text)} characters",
                details={'original_length': original_length, 'truncated_length': len(sanitized_text)},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        # Check for and remove blocked patterns
        for pattern in self.config.blocked_patterns:
            if re.search(pattern, sanitized_text, re.IGNORECASE):
                sanitized_text = re.sub(pattern, '[FILTERED]', sanitized_text, flags=re.IGNORECASE)
                
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.INPUT_SAFETY,
                    level=ValidationLevel.WARNING,
                    passed=True,
                    message=f"Blocked pattern removed: {pattern}",
                    details={'pattern': pattern},
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                ))
        
        return sanitized_text, results
    
    def _validate_conversation_structure(self, conversation_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate conversation structure and format"""
        results = []
        start_time = time.time()
        
        required_fields = ['session_id', 'conversation_history', 'timestamp']
        for field in required_fields:
            if field not in conversation_data:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.TECHNICAL_COMPLIANCE,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Missing required field: {field}",
                    details={'missing_field': field},
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                ))
        
        # Validate conversation history structure
        history = conversation_data.get('conversation_history', [])
        if not isinstance(history, list):
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.TECHNICAL_COMPLIANCE,
                level=ValidationLevel.ERROR,
                passed=False,
                message="conversation_history must be a list",
                details={'actual_type': type(history).__name__},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        # Validate individual conversation exchanges
        for i, exchange in enumerate(history):
            if not isinstance(exchange, dict):
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.TECHNICAL_COMPLIANCE,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Conversation exchange {i} must be a dictionary",
                    details={'exchange_index': i, 'actual_type': type(exchange).__name__},
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                ))
                continue
            
            required_exchange_fields = ['user_message', 'persona_response', 'timestamp']
            for field in required_exchange_fields:
                if field not in exchange:
                    results.append(ValidationResult(
                        validation_id=self._generate_validation_id(),
                        validation_type=ValidationType.TECHNICAL_COMPLIANCE,
                        level=ValidationLevel.WARNING,
                        passed=False,
                        message=f"Exchange {i} missing field: {field}",
                        details={'exchange_index': i, 'missing_field': field},
                        timestamp=datetime.now().isoformat(),
                        processing_time=time.time() - start_time
                    ))
        
        return results
    
    def _validate_conversation_content(self, conversation_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate conversation content quality and safety"""
        results = []
        start_time = time.time()
        
        history = conversation_data.get('conversation_history', [])
        
        for i, exchange in enumerate(history):
            if not isinstance(exchange, dict):
                continue
            
            user_message = exchange.get('user_message', '')
            persona_response = exchange.get('persona_response', '')
            
            # Validate user message
            if user_message:
                message_results = self.safety_validator.validate_text_content(user_message, 'user_message')
                for result in message_results:
                    result.details['exchange_index'] = i
                results.extend(message_results)
            
            # Validate persona response
            if persona_response:
                response_results = self.safety_validator.validate_text_content(persona_response, 'persona_response')
                for result in response_results:
                    result.details['exchange_index'] = i
                results.extend(response_results)
        
        return results
    
    def _validate_conversation_flow(self, conversation_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate conversation flow and logic"""
        results = []
        start_time = time.time()
        
        history = conversation_data.get('conversation_history', [])
        
        if len(history) == 0:
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.BUSINESS_RULES,
                level=ValidationLevel.WARNING,
                passed=False,
                message="Empty conversation history",
                details={'history_length': 0},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
            return results
        
        # Check for conversation continuity
        for i in range(1, len(history)):
            current_exchange = history[i]
            previous_exchange = history[i-1]
            
            # Validate timestamp ordering
            current_time = current_exchange.get('timestamp')
            previous_time = previous_exchange.get('timestamp')
            
            if current_time and previous_time:
                try:
                    current_dt = datetime.fromisoformat(current_time)
                    previous_dt = datetime.fromisoformat(previous_time)
                    
                    if current_dt < previous_dt:
                        results.append(ValidationResult(
                            validation_id=self._generate_validation_id(),
                            validation_type=ValidationType.TECHNICAL_COMPLIANCE,
                            level=ValidationLevel.WARNING,
                            passed=False,
                            message=f"Timestamp ordering issue at exchange {i}",
                            details={'exchange_index': i, 'current_time': current_time, 'previous_time': previous_time},
                            timestamp=datetime.now().isoformat(),
                            processing_time=time.time() - start_time
                        ))
                except ValueError:
                    results.append(ValidationResult(
                        validation_id=self._generate_validation_id(),
                        validation_type=ValidationType.TECHNICAL_COMPLIANCE,
                        level=ValidationLevel.ERROR,
                        passed=False,
                        message=f"Invalid timestamp format at exchange {i}",
                        details={'exchange_index': i, 'timestamp': current_time},
                        timestamp=datetime.now().isoformat(),
                        processing_time=time.time() - start_time
                    ))
        
        return results
    
    def _remove_harmful_characters(self, text: str) -> str:
        """Remove potentially harmful characters from text"""
        # Remove control characters except newline and tab
        cleaned = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t')
        
        # Remove potential script injection patterns
        script_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'on\w+\s*=',
            r'data:text/html'
        ]
        
        for pattern in script_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        return cleaned
    
    def _update_validation_stats(self, results: List[ValidationResult]):
        """Update validation statistics"""
        self.validation_stats['total_validations'] += len(results)
        
        for result in results:
            if result.passed:
                self.validation_stats['passed_validations'] += 1
            else:
                self.validation_stats['failed_validations'] += 1
            
            # Update by type
            val_type = result.validation_type.value
            if val_type not in self.validation_stats['by_type']:
                self.validation_stats['by_type'][val_type] = {'passed': 0, 'failed': 0}
            
            if result.passed:
                self.validation_stats['by_type'][val_type]['passed'] += 1
            else:
                self.validation_stats['by_type'][val_type]['failed'] += 1
            
            # Update by level
            level = result.level.value
            if level not in self.validation_stats['by_level']:
                self.validation_stats['by_level'][level] = 0
            self.validation_stats['by_level'][level] += 1
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get comprehensive validation statistics"""
        pass_rate = (self.validation_stats['passed_validations'] / 
                    max(self.validation_stats['total_validations'], 1)) * 100
        
        return {
            'total_validations': self.validation_stats['total_validations'],
            'pass_rate': round(pass_rate, 2),
            'failed_validations': self.validation_stats['failed_validations'],
            'breakdown_by_type': self.validation_stats['by_type'],
            'breakdown_by_level': self.validation_stats['by_level'],
            'recent_validations': len(self.validation_history[-100:])  # Last 100 validations
        }
    
    def get_validation_report(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        cutoff_time = datetime.now() - timedelta(hours=timeframe_hours)
        
        recent_validations = [
            v for v in self.validation_history
            if datetime.fromisoformat(v['timestamp']) > cutoff_time
        ]
        
        total_checks = sum(v['total_checks'] for v in recent_validations)
        failed_checks = sum(v['failed_checks'] for v in recent_validations)
        avg_processing_time = sum(v['processing_time'] for v in recent_validations) / max(len(recent_validations), 1)
        
        return {
            'report_period': f"{timeframe_hours} hours",
            'total_validation_sessions': len(recent_validations),
            'total_checks_performed': total_checks,
            'failed_checks': failed_checks,
            'success_rate': round(((total_checks - failed_checks) / max(total_checks, 1)) * 100, 2),
            'average_processing_time': round(avg_processing_time, 4),
            'validation_types_used': list(set(
                result['validation_type'] for v in recent_validations
                for result in v['results']
            )),
            'most_common_failures': self._analyze_common_failures(recent_validations)
        }
    
    def _analyze_common_failures(self, recent_validations: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze most common validation failures"""
        failure_counts = {}
        
        for validation in recent_validations:
            for result in validation['results']:
                if not result['passed']:
                    key = f"{result['validation_type']}:{result['message']}"
                    failure_counts[key] = failure_counts.get(key, 0) + 1
        
        # Sort by frequency and return top 5
        sorted_failures = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return [
            {
                'failure_type': failure[0].split(':')[0],
                'message': failure[0].split(':', 1)[1],
                'count': failure[1]
            }
            for failure in sorted_failures
        ]

class InputValidator:
    """Specialized validator for input validation"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
    
    def validate_basic_input(self, input_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate basic input requirements"""
        results = []
        start_time = time.time()
        
        # Check required fields
        if 'message' not in input_data:
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.INPUT_SAFETY,
                level=ValidationLevel.ERROR,
                passed=False,
                message="Missing required 'message' field in input",
                details={},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        # Validate message length
        message = input_data.get('message', '')
        if len(message) > self.config.max_input_length:
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.INPUT_SAFETY,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"Input message exceeds maximum length of {self.config.max_input_length} characters",
                details={'message_length': len(message), 'max_length': self.config.max_input_length},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        # Validate message is not empty
        if not message.strip():
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.INPUT_SAFETY,
                level=ValidationLevel.WARNING,
                passed=False,
                message="Input message is empty or whitespace only",
                details={},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        return results
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

class OutputValidator:
    """Specialized validator for output validation"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
    
    def validate_basic_output(self, output_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate basic output requirements"""
        results = []
        start_time = time.time()
        
        # Check required fields
        required_fields = ['response', 'timestamp']
        for field in required_fields:
            if field not in output_data:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.OUTPUT_QUALITY,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Missing required '{field}' field in output",
                    details={'missing_field': field},
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                ))
        
        # Validate response length
        response = output_data.get('response', '')
        if len(response) > self.config.max_output_length:
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.OUTPUT_QUALITY,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"Output response exceeds maximum length of {self.config.max_output_length} characters",
                details={'response_length': len(response), 'max_length': self.config.max_output_length},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        # Validate response is not empty
        if not response.strip():
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.OUTPUT_QUALITY,
                level=ValidationLevel.ERROR,
                passed=False,
                message="Output response is empty or whitespace only",
                details={},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            ))
        
        return results
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

class SafetyValidator:
    """Specialized validator for safety and content validation"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        
        # Initialize safety patterns
        self.profanity_patterns = self._load_profanity_patterns()
        self.pii_patterns = self._load_pii_patterns()
        self.inappropriate_patterns = self._load_inappropriate_patterns()
    
    def validate_input_safety(self, input_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate input for safety concerns"""
        results = []
        message = input_data.get('message', '')
        
        if message:
            results.extend(self.validate_text_content(message, 'input'))
        
        return results
    
    def validate_output_safety(self, output_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate output for safety concerns"""
        results = []
        response = output_data.get('response', '')
        
        if response:
            results.extend(self.validate_text_content(response, 'output'))
        
        return results
    
    def validate_text_content(self, text: str, context: str) -> List[ValidationResult]:
        """Validate text content for safety issues"""
        results = []
        start_time = time.time()
        
        # Check for profanity
        if self.config.enable_profanity_filter:
            profanity_results = self._check_profanity(text, context)
            results.extend(profanity_results)
        
        # Check for PII
        if self.config.enable_pii_detection:
            pii_results = self._check_pii(text, context)
            results.extend(pii_results)
        
        # Check for inappropriate content
        inappropriate_results = self._check_inappropriate_content(text, context)
        results.extend(inappropriate_results)
        
        return results
    
    def _load_profanity_patterns(self) -> List[str]:
        """Load profanity detection patterns"""
        # Basic profanity patterns - in production, use a comprehensive list
        return [
            r'\b(damn|hell|crap|stupid|idiot)\b',  # Mild profanity
            # Add more patterns as needed
        ]
    
    def _load_pii_patterns(self) -> List[str]:
        """Load PII detection patterns"""
        return [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b',  # Credit card pattern
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email pattern
            r'\b\d{3}-\d{3}-\d{4}\b',  # Phone pattern
        ]
    
    def _load_inappropriate_patterns(self) -> List[str]:
        """Load inappropriate content patterns"""
        return [
            r'\b(violence|threat|harm|kill|hurt)\b',  # Violence-related
            r'\b(discrimination|racist|sexist|hate)\b',  # Discrimination
            # Add more patterns as needed
        ]
    
    def _check_profanity(self, text: str, context: str) -> List[ValidationResult]:
        """Check for profanity in text"""
        results = []
        
        for pattern in self.profanity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.CONTENT_APPROPRIATENESS,
                    level=ValidationLevel.WARNING,
                    passed=False,
                    message=f"Potential profanity detected in {context}",
                    details={'matches': matches, 'pattern': pattern},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        return results
    
    def _check_pii(self, text: str, context: str) -> List[ValidationResult]:
        """Check for personally identifiable information"""
        results = []
        
        for pattern in self.pii_patterns:
            matches = re.findall(pattern, text)
            if matches:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.INPUT_SAFETY,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Potential PII detected in {context}",
                    details={'pattern_type': 'pii', 'matches_count': len(matches)},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        return results
    
    def _check_inappropriate_content(self, text: str, context: str) -> List[ValidationResult]:
        """Check for inappropriate content"""
        results = []
        
        for pattern in self.inappropriate_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.CONTENT_APPROPRIATENESS,
                    level=ValidationLevel.WARNING,
                    passed=False,
                    message=f"Potentially inappropriate content detected in {context}",
                    details={'matches': matches, 'pattern': pattern},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        return results
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

class QualityValidator:
    """Specialized validator for output quality assessment"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
    
    def validate_output_quality(self, output_data: Dict[str, Any], 
                              input_context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate output quality metrics"""
        results = []
        start_time = time.time()
        
        response = output_data.get('response', '')
        
        # Check response relevance
        if input_context and 'message' in input_context:
            relevance_results = self._check_response_relevance(response, input_context['message'])
            results.extend(relevance_results)
        
        # Check response completeness
        completeness_results = self._check_response_completeness(response)
        results.extend(completeness_results)
        
        # Check response coherence
        coherence_results = self._check_response_coherence(response)
        results.extend(coherence_results)
        
        return results
    
    def _check_response_relevance(self, response: str, input_message: str) -> List[ValidationResult]:
        """Check if response is relevant to input"""
        results = []
        
        # Simple keyword overlap check
        input_words = set(input_message.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stop words for better analysis
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        input_words -= stop_words
        response_words -= stop_words
        
        if input_words and response_words:
            overlap = len(input_words & response_words)
            overlap_ratio = overlap / len(input_words)
            
            if overlap_ratio < 0.1:  # Less than 10% overlap
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.OUTPUT_QUALITY,
                    level=ValidationLevel.WARNING,
                    passed=False,
                    message="Low relevance between input and response",
                    details={'overlap_ratio': overlap_ratio, 'common_words': overlap},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        return results
    
    def _check_response_completeness(self, response: str) -> List[ValidationResult]:
        """Check if response is complete and well-formed"""
        results = []
        
        # Check for abrupt endings
        if len(response) > 10 and not response.rstrip().endswith(('.', '!', '?', '"', "'")):
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.OUTPUT_QUALITY,
                level=ValidationLevel.INFO,
                passed=False,
                message="Response may be incomplete (doesn't end with punctuation)",
                details={'last_chars': response[-10:]},
                timestamp=datetime.now().isoformat(),
                processing_time=0.001
            ))
        
        # Check minimum length for substantive responses
        if len(response.split()) < 5:
            results.append(ValidationResult(
                validation_id=self._generate_validation_id(),
                validation_type=ValidationType.OUTPUT_QUALITY,
                level=ValidationLevel.WARNING,
                passed=False,
                message="Response may be too brief",
                details={'word_count': len(response.split())},
                timestamp=datetime.now().isoformat(),
                processing_time=0.001
            ))
        
        return results
    
    def _check_response_coherence(self, response: str) -> List[ValidationResult]:
        """Check response coherence and readability"""
        results = []
        
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Check for extremely long sentences
        for i, sentence in enumerate(sentences):
            words_in_sentence = len(sentence.split())
            if words_in_sentence > 50:  # Very long sentence
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.OUTPUT_QUALITY,
                    level=ValidationLevel.INFO,
                    passed=False,
                    message=f"Sentence {i+1} may be too long",
                    details={'sentence_length': words_in_sentence, 'sentence_index': i},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        # Check for repeated phrases (potential generation issues)
        words = response.lower().split()
        if len(words) > 10:
            # Check for 3-word phrase repetitions
            phrases = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
            phrase_counts = {}
            for phrase in phrases:
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
            
            for phrase, count in phrase_counts.items():
                if count > 2:  # Phrase repeated more than twice
                    results.append(ValidationResult(
                        validation_id=self._generate_validation_id(),
                        validation_type=ValidationType.OUTPUT_QUALITY,
                        level=ValidationLevel.WARNING,
                        passed=False,
                        message="Repetitive phrases detected",
                        details={'repeated_phrase': phrase, 'repetition_count': count},
                        timestamp=datetime.now().isoformat(),
                        processing_time=0.001
                    ))
        
        return results
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

class BusinessRulesValidator:
    """Specialized validator for business rules and compliance"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        
        # Define business rules
        self.sales_compliance_rules = self._initialize_sales_rules()
        self.conversation_rules = self._initialize_conversation_rules()
    
    def validate_input_rules(self, input_data: Dict[str, Any], 
                           validation_context: Dict[str, Any]) -> List[ValidationResult]:
        """Validate input against business rules"""
        results = []
        
        # Check sales compliance rules
        if validation_context.get('conversation_type') == 'sales':
            results.extend(self._validate_sales_input_rules(input_data, validation_context))
        
        return results
    
    def validate_output_rules(self, output_data: Dict[str, Any], 
                            validation_context: Dict[str, Any]) -> List[ValidationResult]:
        """Validate output against business rules"""
        results = []
        
        # Check sales compliance rules
        if validation_context.get('conversation_type') == 'sales':
            results.extend(self._validate_sales_output_rules(output_data, validation_context))
        
        return results
    
    def _initialize_sales_rules(self) -> Dict[str, Any]:
        """Initialize sales compliance rules"""
        return {
            'required_disclaimers': [
                'terms and conditions',
                'pricing subject to change',
                'results may vary'
            ],
            'prohibited_claims': [
                'guaranteed results',
                'no risk',
                'instant success',
                '100% effective'
            ],
            'required_disclosures': [
                'material risks',
                'terms of service',
                'refund policy'
            ]
        }
    
    def _initialize_conversation_rules(self) -> Dict[str, Any]:
        """Initialize conversation flow rules"""
        return {
            'max_consecutive_questions': 3,
            'min_acknowledgment_ratio': 0.2,
            'required_closing_elements': [
                'next steps',
                'contact information',
                'timeline'
            ]
        }
    
    def _validate_sales_input_rules(self, input_data: Dict[str, Any], 
                                  validation_context: Dict[str, Any]) -> List[ValidationResult]:
        """Validate sales-specific input rules"""
        results = []
        
        message = input_data.get('message', '').lower()
        
        # Check for prohibited claims in user input
        for claim in self.sales_compliance_rules['prohibited_claims']:
            if claim in message:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.BUSINESS_RULES,
                    level=ValidationLevel.WARNING,
                    passed=False,
                    message=f"User input contains prohibited claim: {claim}",
                    details={'prohibited_claim': claim},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        return results
    
    def _validate_sales_output_rules(self, output_data: Dict[str, Any], 
                                   validation_context: Dict[str, Any]) -> List[ValidationResult]:
        """Validate sales-specific output rules"""
        results = []
        
        response = output_data.get('response', '').lower()
        
        # Check for prohibited claims in response
        for claim in self.sales_compliance_rules['prohibited_claims']:
            if claim in response:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.BUSINESS_RULES,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Response contains prohibited claim: {claim}",
                    details={'prohibited_claim': claim},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        # Check for required disclaimers when making claims
        claim_indicators = ['will', 'guarantee', 'promise', 'ensure', 'definitely']
        has_claims = any(indicator in response for indicator in claim_indicators)
        
        if has_claims:
            has_disclaimer = any(disclaimer in response for disclaimer in self.sales_compliance_rules['required_disclaimers'])
            if not has_disclaimer:
                results.append(ValidationResult(
                    validation_id=self._generate_validation_id(),
                    validation_type=ValidationType.BUSINESS_RULES,
                    level=ValidationLevel.WARNING,
                    passed=False,
                    message="Response makes claims but lacks required disclaimers",
                    details={'detected_claims': [ind for ind in claim_indicators if ind in response]},
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.001
                ))
        
        return results
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

# Global validation service instance
validation_service = ComprehensiveValidationService()