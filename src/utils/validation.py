"""
Validation Utilities
Input validation, data sanitization, and format checking
"""
import re
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom validation error"""
    pass

class Validator:
    """Input and data validation utilities"""
    
    # Common regex patterns
    PATTERNS = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'phone': re.compile(r'^\+?[\d\s\-\(\)]{10,15}$'),
        'url': re.compile(r'^https?://[^\s/$.?#].[^\s]*$'),
        'filename': re.compile(r'^[^<>:"/\\|?*\x00-\x1f]+$'),
        'alphanum': re.compile(r'^[a-zA-Z0-9]+$'),
        'alpha_space': re.compile(r'^[a-zA-Z\s]+$'),
        'numeric': re.compile(r'^\d+$'),
        'float': re.compile(r'^-?\d+\.?\d*$'),
    }
    
    @staticmethod
    def validate_text_input(text: str, 
                           min_length: int = 0,
                           max_length: int = 1000,
                           allow_empty: bool = False,
                           pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate text input
        
        Args:
            text: Input text to validate
            min_length: Minimum text length
            max_length: Maximum text length
            allow_empty: Whether to allow empty strings
            pattern: Regex pattern name or custom pattern
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "sanitized": text.strip() if text else ""
        }
        
        # Check if text is provided
        if not text:
            if not allow_empty:
                result["valid"] = False
                result["errors"].append("Text input is required")
            return result
        
        # Length validation
        text_length = len(result["sanitized"])
        
        if text_length < min_length:
            result["valid"] = False
            result["errors"].append(f"Text too short (minimum {min_length} characters)")
        
        if text_length > max_length:
            result["valid"] = False
            result["errors"].append(f"Text too long (maximum {max_length} characters)")
        
        # Pattern validation
        if pattern and result["sanitized"]:
            regex = Validator.PATTERNS.get(pattern)
            if regex is None:
                try:
                    regex = re.compile(pattern)
                except re.error as e:
                    logger.error(f"Invalid regex pattern: {e}")
                    result["errors"].append("Invalid validation pattern")
                    result["valid"] = False
                    return result
            
            if not regex.match(result["sanitized"]):
                result["valid"] = False
                result["errors"].append(f"Text doesn't match required pattern: {pattern}")
        
        return result
    
    @staticmethod
    def validate_audio_input(audio_data: Any,
                           min_duration: float = 0.1,
                           max_duration: float = 300.0,
                           required_format: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate audio input
        
        Args:
            audio_data: Audio data or file path
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds
            required_format: Required audio format
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "metadata": {}
        }
        
        # Check if audio data is provided
        if audio_data is None:
            result["valid"] = False
            result["errors"].append("Audio input is required")
            return result
        
        try:
            # If it's a file path
            if isinstance(audio_data, (str, Path)):
                from src.utils.audio_utils import AudioProcessor
                
                file_path = str(audio_data)
                validation = AudioProcessor.validate_audio_file(file_path)
                
                if not validation.get("valid", False):
                    result["valid"] = False
                    result["errors"].append(f"Invalid audio file: {validation.get('error', 'Unknown error')}")
                    return result
                
                result["metadata"] = validation
                duration = validation.get("duration", 0)
                
                # Format validation
                if required_format:
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext != required_format.lower():
                        result["valid"] = False
                        result["errors"].append(f"Audio format must be {required_format}")
            
            # If it's audio data array
            else:
                # Basic validation for audio arrays
                try:
                    import numpy as np
                    if hasattr(audio_data, '__len__'):
                        duration = len(audio_data) / 16000  # Assume 16kHz default
                        result["metadata"]["duration"] = duration
                        result["metadata"]["samples"] = len(audio_data)
                    else:
                        result["valid"] = False
                        result["errors"].append("Invalid audio data format")
                        return result
                except:
                    result["valid"] = False
                    result["errors"].append("Unable to process audio data")
                    return result
            
            # Duration validation
            if duration < min_duration:
                result["valid"] = False
                result["errors"].append(f"Audio too short (minimum {min_duration}s)")
            
            if duration > max_duration:
                result["valid"] = False
                result["errors"].append(f"Audio too long (maximum {max_duration}s)")
        
        except Exception as e:
            logger.error(f"Audio validation error: {e}")
            result["valid"] = False
            result["errors"].append(f"Audio validation failed: {str(e)}")
        
        return result
    
    @staticmethod
    def validate_confidence_score(confidence: float,
                                min_threshold: float = 0.0,
                                max_threshold: float = 1.0) -> Dict[str, Any]:
        """
        Validate confidence score
        
        Args:
            confidence: Confidence value to validate
            min_threshold: Minimum acceptable threshold
            max_threshold: Maximum acceptable threshold
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "level": "unknown"
        }
        
        # Type validation
        if not isinstance(confidence, (int, float)):
            result["valid"] = False
            result["errors"].append("Confidence must be a number")
            return result
        
        # Range validation
        if confidence < 0.0 or confidence > 1.0:
            result["valid"] = False
            result["errors"].append("Confidence must be between 0.0 and 1.0")
            return result
        
        # Threshold validation
        if confidence < min_threshold:
            result["valid"] = False
            result["errors"].append(f"Confidence below minimum threshold ({min_threshold})")
        
        if confidence > max_threshold:
            result["valid"] = False
            result["errors"].append(f"Confidence above maximum threshold ({max_threshold})")
        
        # Determine confidence level
        if confidence >= 0.8:
            result["level"] = "high"
        elif confidence >= 0.6:
            result["level"] = "medium"
        elif confidence >= 0.3:
            result["level"] = "low"
        else:
            result["level"] = "very_low"
        
        return result
    
    @staticmethod
    def validate_file_path(path: Union[str, Path],
                          must_exist: bool = True,
                          must_be_file: bool = True,
                          allowed_extensions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Validate file path
        
        Args:
            path: File path to validate
            must_exist: Whether file must exist
            must_be_file: Whether path must be a file (not directory)
            allowed_extensions: List of allowed file extensions
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "absolute_path": None,
            "metadata": {}
        }
        
        try:
            path_obj = Path(path)
            result["absolute_path"] = str(path_obj.resolve())
            
            # Existence validation
            if must_exist and not path_obj.exists():
                result["valid"] = False
                result["errors"].append("File does not exist")
                return result
            
            # Type validation
            if path_obj.exists():
                if must_be_file and not path_obj.is_file():
                    result["valid"] = False
                    result["errors"].append("Path is not a file")
                
                # Get file metadata
                stat = path_obj.stat()
                result["metadata"] = {
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime),
                    "extension": path_obj.suffix.lower()
                }
            
            # Extension validation
            if allowed_extensions:
                file_ext = path_obj.suffix.lower()
                if file_ext not in [ext.lower() for ext in allowed_extensions]:
                    result["valid"] = False
                    result["errors"].append(f"File extension must be one of: {allowed_extensions}")
            
            # Security validation (basic path traversal check)
            if ".." in str(path_obj) or str(path_obj).startswith("/"):
                logger.warning(f"Potentially unsafe path: {path}")
        
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            result["valid"] = False
            result["errors"].append(f"Path validation failed: {str(e)}")
        
        return result
    
    @staticmethod
    def sanitize_filename(filename: str,
                         max_length: int = 255,
                         replacement_char: str = "_") -> str:
        """
        Sanitize filename for safe file system use
        
        Args:
            filename: Original filename
            max_length: Maximum filename length
            replacement_char: Character to replace invalid chars
            
        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = filename
        
        for char in invalid_chars:
            sanitized = sanitized.replace(char, replacement_char)
        
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', replacement_char, sanitized)
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Truncate if too long
        if len(sanitized) > max_length:
            name, ext = os.path.splitext(sanitized)
            available_length = max_length - len(ext)
            sanitized = name[:available_length] + ext
        
        # Ensure not empty
        if not sanitized:
            sanitized = "untitled"
        
        return sanitized
    
    @staticmethod
    def validate_json_structure(data: Dict[str, Any],
                               required_fields: List[str],
                               optional_fields: Optional[List[str]] = None,
                               field_types: Optional[Dict[str, type]] = None) -> Dict[str, Any]:
        """
        Validate JSON structure
        
        Args:
            data: JSON data to validate
            required_fields: List of required field names
            optional_fields: List of optional field names
            field_types: Dictionary mapping field names to expected types
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "missing_fields": [],
            "extra_fields": [],
            "type_errors": []
        }
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                result["missing_fields"].append(field)
                result["valid"] = False
        
        # Check for extra fields
        allowed_fields = set(required_fields)
        if optional_fields:
            allowed_fields.update(optional_fields)
        
        for field in data:
            if field not in allowed_fields:
                result["extra_fields"].append(field)
        
        # Type validation
        if field_types:
            for field, expected_type in field_types.items():
                if field in data:
                    if not isinstance(data[field], expected_type):
                        result["type_errors"].append({
                            "field": field,
                            "expected": expected_type.__name__,
                            "actual": type(data[field]).__name__
                        })
                        result["valid"] = False
        
        # Compile errors
        if result["missing_fields"]:
            result["errors"].append(f"Missing required fields: {result['missing_fields']}")
        
        if result["type_errors"]:
            for error in result["type_errors"]:
                result["errors"].append(
                    f"Field '{error['field']}' expects {error['expected']}, got {error['actual']}"
                )
        
        return result
    
    @staticmethod
    def validate_ranges(value: Union[int, float],
                       min_val: Optional[Union[int, float]] = None,
                       max_val: Optional[Union[int, float]] = None,
                       inclusive: bool = True) -> Dict[str, Any]:
        """
        Validate numeric ranges
        
        Args:
            value: Value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            inclusive: Whether to include boundary values
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": []
        }
        
        if not isinstance(value, (int, float)):
            result["valid"] = False
            result["errors"].append("Value must be numeric")
            return result
        
        if min_val is not None:
            if inclusive and value < min_val:
                result["valid"] = False
                result["errors"].append(f"Value {value} below minimum {min_val}")
            elif not inclusive and value <= min_val:
                result["valid"] = False
                result["errors"].append(f"Value {value} must be greater than {min_val}")
        
        if max_val is not None:
            if inclusive and value > max_val:
                result["valid"] = False
                result["errors"].append(f"Value {value} above maximum {max_val}")
            elif not inclusive and value >= max_val:
                result["valid"] = False
                result["errors"].append(f"Value {value} must be less than {max_val}")
        
        return result