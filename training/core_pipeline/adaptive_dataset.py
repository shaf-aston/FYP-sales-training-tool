"""
Adaptive PyTorch Dataset Classes
Automatically detects and adapts to dataset size/structure changes
Provides flexible data loading for maintainable training
"""
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Dict, List, Optional, Union, Tuple
import json
from pathlib import Path
import logging
from dataclasses import dataclass
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DatasetStats:
    """Statistics about the dataset for adaptive configuration"""
    total_samples: int
    avg_input_length: float
    avg_output_length: float
    max_input_length: int
    max_output_length: int
    personas: List[str]
    persona_distribution: Dict[str, int]
    contexts: List[Dict]
    data_sources: List[str]
    recommended_batch_size: int
    recommended_max_length: int
    estimated_training_time_minutes: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'total_samples': self.total_samples,
            'avg_input_length': self.avg_input_length,
            'avg_output_length': self.avg_output_length,
            'max_input_length': self.max_input_length,
            'max_output_length': self.max_output_length,
            'personas': self.personas,
            'persona_distribution': self.persona_distribution,
            'contexts': self.contexts,
            'data_sources': self.data_sources,
            'recommended_batch_size': self.recommended_batch_size,
            'recommended_max_length': self.recommended_max_length,
            'estimated_training_time_minutes': self.estimated_training_time_minutes
        }


class AdaptiveSalesDataset(Dataset):
    """
    PyTorch Dataset that automatically adapts to data size and structure changes.
    
    Features:
    - Automatically detects data format (JSONL, JSON array, structured conversations)
    - Computes statistics for optimal hyperparameter selection
    - Handles missing fields gracefully with defaults
    - Supports multiple data sources with automatic weighting
    - Validates data quality and reports issues
    """
    
    def __init__(
        self,
        data_path: Union[str, Path, List[Union[str, Path]]],
        tokenizer,
        max_length: Optional[int] = None,
        auto_configure: bool = True,
        min_length: int = 10,
        max_length_percentile: float = 95.0,
        cache_tokenized: bool = False
    ):
        """
        Initialize adaptive dataset.
        
        Args:
            data_path: Path(s) to data file(s). Supports JSONL, JSON arrays, or list of paths
            tokenizer: Hugging Face tokenizer for text encoding
            max_length: Maximum sequence length (auto-computed if None)
            auto_configure: Automatically compute optimal parameters
            min_length: Minimum valid sample length (filters out too-short samples)
            max_length_percentile: Percentile for auto max_length (prevents outliers)
            cache_tokenized: Cache tokenized samples in memory (faster but more RAM)
        """
        self.tokenizer = tokenizer
        self.min_length = min_length
        self.max_length_percentile = max_length_percentile
        self.cache_tokenized = cache_tokenized
        self._tokenized_cache = {} if cache_tokenized else None
        
        # Load and validate data
        self.data = self._load_data(data_path)
        logger.info(f"Loaded {len(self.data)} samples from {data_path}")
        
        # Compute statistics
        self.stats = self._compute_statistics() if auto_configure else None
        
        # Set max_length
        if max_length is None and self.stats:
            self.max_length = self.stats.recommended_max_length
            logger.info(f"Auto-configured max_length: {self.max_length}")
        else:
            self.max_length = max_length or 512
        
        # Validate data quality
        self._validate_data_quality()
    
    def _load_data(self, data_path: Union[str, Path, List[Union[str, Path]]]) -> List[Dict]:
        """
        Load data from various formats, handling structure changes gracefully.
        
        Supported formats:
        - JSONL (one JSON object per line)
        - JSON array
        - Structured conversations JSON
        - Multiple files (automatically merged)
        """
        all_data = []
        
        # Handle single path or list of paths
        paths = [data_path] if not isinstance(data_path, list) else data_path
        
        for path in paths:
            path = Path(path)
            if not path.exists():
                logger.warning(f"Data file not found: {path}")
                continue
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    # Try JSONL format first (most common for training)
                    if path.suffix == '.jsonl':
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                data_item = json.loads(line)
                                data_item['_source_file'] = str(path)
                                data_item['_line_number'] = line_num
                                all_data.append(data_item)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Invalid JSON at {path}:{line_num}: {e}")
                    else:
                        # Try JSON array or object
                        content = json.load(f)
                        if isinstance(content, list):
                            for idx, item in enumerate(content):
                                item['_source_file'] = str(path)
                                item['_index'] = idx
                                all_data.append(item)
                        elif isinstance(content, dict):
                            # Handle structured format (e.g., {"conversations": [...], "metadata": ...})
                            if 'conversations' in content:
                                for idx, item in enumerate(content['conversations']):
                                    item['_source_file'] = str(path)
                                    item['_index'] = idx
                                    all_data.append(item)
                            else:
                                # Single conversation object
                                content['_source_file'] = str(path)
                                all_data.append(content)
                
                logger.info(f"Loaded {len(all_data)} samples from {path}")
            
            except Exception as e:
                logger.error(f"Error loading {path}: {e}")
                continue
        
        if not all_data:
            raise ValueError(f"No valid data loaded from {data_path}")
        
        return all_data
    
    def _compute_statistics(self) -> DatasetStats:
        """
        Compute comprehensive dataset statistics for adaptive configuration.
        """
        logger.info("Computing dataset statistics...")
        
        input_lengths = []
        output_lengths = []
        personas = []
        contexts = []
        sources = []
        
        for item in self.data:
            # Extract text for length computation
            input_text = self._extract_input_text(item)
            output_text = self._extract_output_text(item)
            
            if input_text:
                input_lengths.append(len(self.tokenizer.encode(input_text)))
            if output_text:
                output_lengths.append(len(self.tokenizer.encode(output_text)))
            
            # Extract metadata
            if 'persona' in item:
                personas.append(item['persona'])
            if 'context' in item:
                contexts.append(item['context'])
            if '_source_file' in item:
                sources.append(Path(item['_source_file']).stem)
        
        # Compute statistics
        total_samples = len(self.data)
        avg_input = np.mean(input_lengths) if input_lengths else 0
        avg_output = np.mean(output_lengths) if output_lengths else 0
        max_input = max(input_lengths) if input_lengths else 512
        max_output = max(output_lengths) if output_lengths else 512
        
        # Use percentile for recommended max_length (avoids outliers)
        all_lengths = input_lengths + output_lengths
        recommended_max_length = int(np.percentile(all_lengths, self.max_length_percentile)) if all_lengths else 512
        # Ensure it's at least 128 and round to nearest 64
        recommended_max_length = max(128, (recommended_max_length + 63) // 64 * 64)
        
        # Persona distribution
        persona_counter = Counter(personas)
        unique_personas = list(persona_counter.keys())
        
        # Recommended batch size based on dataset size
        if total_samples < 100:
            recommended_batch_size = 2
        elif total_samples < 500:
            recommended_batch_size = 4
        elif total_samples < 2000:
            recommended_batch_size = 8
        else:
            recommended_batch_size = 16
        
        # Estimate training time (rough approximation)
        # Assumes ~0.5 seconds per sample on average hardware
        estimated_time = (total_samples * 0.5) / 60.0  # minutes
        
        stats = DatasetStats(
            total_samples=total_samples,
            avg_input_length=float(avg_input),
            avg_output_length=float(avg_output),
            max_input_length=max_input,
            max_output_length=max_output,
            personas=unique_personas,
            persona_distribution=dict(persona_counter),
            contexts=contexts[:10],  # Sample of contexts
            data_sources=list(set(sources)),
            recommended_batch_size=recommended_batch_size,
            recommended_max_length=recommended_max_length,
            estimated_training_time_minutes=estimated_time
        )
        
        logger.info(f"Dataset Statistics:")
        logger.info(f"  Total samples: {stats.total_samples}")
        logger.info(f"  Avg input length: {stats.avg_input_length:.1f} tokens")
        logger.info(f"  Avg output length: {stats.avg_output_length:.1f} tokens")
        logger.info(f"  Recommended max_length: {stats.recommended_max_length}")
        logger.info(f"  Recommended batch_size: {stats.recommended_batch_size}")
        logger.info(f"  Unique personas: {len(stats.personas)}")
        logger.info(f"  Estimated training time: {stats.estimated_training_time_minutes:.1f} minutes")
        
        return stats
    
    def _extract_input_text(self, item: Dict) -> str:
        """Extract input text from various data formats"""
        # Try multiple field names
        for field in ['input', 'input_text', 'user_message', 'question', 'prompt']:
            if field in item:
                return str(item[field])
        
        # Try conversation format
        if 'conversation' in item:
            if isinstance(item['conversation'], list):
                # Find first user/human message
                for turn in item['conversation']:
                    if turn.get('role') in ['user', 'human']:
                        return turn.get('content', '')
            elif isinstance(item['conversation'], str):
                return item['conversation']
        
        return ""
    
    def _extract_output_text(self, item: Dict) -> str:
        """Extract output/target text from various data formats"""
        # Try multiple field names
        for field in ['output', 'target_text', 'assistant_message', 'answer', 'response']:
            if field in item:
                return str(item[field])
        
        # Try conversation format
        if 'conversation' in item:
            if isinstance(item['conversation'], list):
                # Find first assistant/AI message
                for turn in item['conversation']:
                    if turn.get('role') in ['assistant', 'ai']:
                        return turn.get('content', '')
        
        return ""
    
    def _validate_data_quality(self):
        """Validate data quality and report issues"""
        issues = []
        valid_samples = 0
        
        for idx, item in enumerate(self.data):
            input_text = self._extract_input_text(item)
            output_text = self._extract_output_text(item)
            
            if not input_text or not output_text:
                issues.append(f"Sample {idx}: Missing input or output")
            elif len(input_text) < self.min_length or len(output_text) < self.min_length:
                issues.append(f"Sample {idx}: Text too short (input: {len(input_text)}, output: {len(output_text)})")
            else:
                valid_samples += 1
        
        if issues:
            logger.warning(f"Data quality issues found: {len(issues)}/{len(self.data)} samples")
            for issue in issues[:10]:  # Show first 10
                logger.warning(f"  {issue}")
            if len(issues) > 10:
                logger.warning(f"  ... and {len(issues) - 10} more issues")
        
        logger.info(f"Valid samples: {valid_samples}/{len(self.data)} ({100*valid_samples/len(self.data):.1f}%)")
    
    def _format_sample(self, item: Dict) -> str:
        """
        Format a sample into a conversation string for training.
        Handles various input formats flexibly.
        """
        conversation_parts = []
        
        # Add system prompt if persona exists
        if 'persona' in item:
            persona = item['persona']
            system_prompt = f"You are a {persona} in a sales conversation. Respond naturally and consistently with this persona."
            conversation_parts.append(f"<|im_start|>system\n{system_prompt}<|im_end|>")
        
        # Handle conversation array format
        if 'conversation' in item and isinstance(item['conversation'], list):
            for turn in item['conversation']:
                role = turn.get('role', 'user')
                content = turn.get('content', '')
                conversation_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        
        # Handle input/output format
        else:
            input_text = self._extract_input_text(item)
            output_text = self._extract_output_text(item)
            
            if input_text:
                conversation_parts.append(f"<|im_start|>user\n{input_text}<|im_end|>")
            if output_text:
                conversation_parts.append(f"<|im_start|>assistant\n{output_text}<|im_end|>")
        
        return '\n'.join(conversation_parts)
    
    def __len__(self) -> int:
        return len(self.data)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        Get a tokenized sample.
        Returns dict with input_ids, attention_mask, and labels.
        """
        # Check cache first
        if self.cache_tokenized and idx in self._tokenized_cache:
            return self._tokenized_cache[idx]
        
        item = self.data[idx]
        formatted_text = self._format_sample(item)
        
        # Tokenize
        encoded = self.tokenizer(
            formatted_text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        # Prepare output
        result = {
            'input_ids': encoded['input_ids'].squeeze(0),
            'attention_mask': encoded['attention_mask'].squeeze(0),
            'labels': encoded['input_ids'].squeeze(0).clone()  # For language modeling
        }
        
        # Cache if enabled
        if self.cache_tokenized:
            self._tokenized_cache[idx] = result
        
        return result
    
    def get_dataloader(
        self,
        batch_size: Optional[int] = None,
        shuffle: bool = True,
        num_workers: int = 0,
        **kwargs
    ) -> DataLoader:
        """
        Create a DataLoader with optimal settings based on dataset stats.
        
        Args:
            batch_size: Batch size (uses recommended if None)
            shuffle: Whether to shuffle data
            num_workers: Number of worker processes
            **kwargs: Additional DataLoader arguments
        """
        if batch_size is None and self.stats:
            batch_size = self.stats.recommended_batch_size
        elif batch_size is None:
            batch_size = 4  # Default fallback
        
        return DataLoader(
            self,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            **kwargs
        )
    
    def save_statistics(self, output_path: Union[str, Path]):
        """Save dataset statistics to JSON file"""
        if self.stats:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.stats.to_dict(), f, indent=2)
            
            logger.info(f"Statistics saved to {output_path}")


def create_train_val_split(
    dataset: AdaptiveSalesDataset,
    val_ratio: float = 0.1,
    stratify_by: Optional[str] = 'persona'
) -> Tuple[AdaptiveSalesDataset, AdaptiveSalesDataset]:
    """
    Split dataset into training and validation sets.
    
    Args:
        dataset: Source dataset to split
        val_ratio: Fraction of data for validation
        stratify_by: Field to stratify split (e.g., 'persona' for balanced personas)
    
    Returns:
        Tuple of (train_dataset, val_dataset)
    """
    # This is a simplified implementation
    # For production, use sklearn's train_test_split with stratification
    total_samples = len(dataset.data)
    val_size = int(total_samples * val_ratio)
    train_size = total_samples - val_size
    
    indices = np.random.permutation(total_samples)
    train_indices = indices[:train_size]
    val_indices = indices[train_size:]
    
    # Create subsets (simplified - in production, create proper subset classes)
    train_data = [dataset.data[i] for i in train_indices]
    val_data = [dataset.data[i] for i in val_indices]
    
    train_dataset = AdaptiveSalesDataset.__new__(AdaptiveSalesDataset)
    train_dataset.data = train_data
    train_dataset.tokenizer = dataset.tokenizer
    train_dataset.max_length = dataset.max_length
    train_dataset.min_length = dataset.min_length
    train_dataset.max_length_percentile = dataset.max_length_percentile
    train_dataset.cache_tokenized = dataset.cache_tokenized
    train_dataset._tokenized_cache = {} if dataset.cache_tokenized else None
    train_dataset.stats = None  # Will recompute if needed
    
    val_dataset = AdaptiveSalesDataset.__new__(AdaptiveSalesDataset)
    val_dataset.data = val_data
    val_dataset.tokenizer = dataset.tokenizer
    val_dataset.max_length = dataset.max_length
    val_dataset.min_length = dataset.min_length
    val_dataset.max_length_percentile = dataset.max_length_percentile
    val_dataset.cache_tokenized = dataset.cache_tokenized
    val_dataset._tokenized_cache = {} if dataset.cache_tokenized else None
    val_dataset.stats = None
    
    logger.info(f"Split dataset: {len(train_data)} train, {len(val_data)} val")
    
    return train_dataset, val_dataset
