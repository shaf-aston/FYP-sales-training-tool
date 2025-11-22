"""
Transcript Processing Service
Handles post-processing of STT transcripts including:
- Diarization (speaker labeling)
- Sentence segmentation
- Key concept labeling
- STT corrections
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """Represents a segment of speech from a specific speaker"""
    speaker_id: str
    text: str
    start_time: float
    end_time: float
    confidence: float
    words: List[Dict]


@dataclass
class TrainingAnnotation:
    """Represents a training point or technique annotation"""
    annotation_type: str
    label: str
    description: str
    position: int


class TranscriptProcessor:
    """Processes transcripts to add structure and annotations"""
    
    def __init__(self):
        self.stt_corrections = {
            'restaurant': 'rationale',
            'cast': 'Cass',
            'cassidy': 'Cassidy',
            'weapon': 'or have a family',
            'milk': 'correct',
            'period': 'nope',
            
            '3632 months': '3, 6, or 12 months',
            'tree months': '3 months',
            'sex months': '6 months',
            
            'clothes': 'close',
            'by': 'buy',
            'sale': 'sell',
            'lead': 'lead',
            
            'um': '',
            'uh': '',
            'ah': '',
        }
        
        self.speaker_names = {
            'speaker_0': 'Trainer',
            'speaker_1': 'Aiden',
            'speaker_2': 'Cassidy',
            'speaker_3': 'Tammy',
            'speaker_4': 'Nico',
        }
        
        self.training_patterns = {
            'acknowledge': 'Acknowledge prospect\'s reasoning',
            'timing_objection': 'Timing Objection Handling',
            'identify_objection': 'Identify Objection',
            'lock_in': 'Lock-in Timing',
            'reflection': 'Reflection',
            'open_ended_question': 'Open-Ended Question',
            'active_listening': 'Active Listening',
            'build_rapport': 'Build Rapport',
            'handle_objection': 'Handle Objection',
            'close': 'Close the Sale',
        }

    def process_transcript(self, stt_result: Dict) -> Dict:
        """
        Main processing pipeline for transcripts
        
        Args:
            stt_result: Raw STT result from Google Cloud
            
        Returns:
            Processed transcript with annotations
        """
        logger.info("Processing transcript...")
        
        corrected_result = self.apply_stt_corrections(stt_result)
        
        diarized_result = self.add_speaker_labels(corrected_result)
        
        segmented_result = self.segment_sentences(diarized_result)
        
        annotated_result = self.add_training_annotations(segmented_result)
        
        logger.info("Transcript processing complete")
        return annotated_result

    def apply_stt_corrections(self, stt_result: Dict) -> Dict:
        """
        Apply common STT corrections to improve accuracy
        
        Corrections include:
        - Common mishearings (restaurant → rationale)
        - Proper noun corrections (cast → Cass)
        - Number corrections (3632 → 3, 6, or 12)
        - Context-specific terms
        """
        text = stt_result.get('text', '')
        segments = stt_result.get('segments', [])
        
        corrected_text = text
        corrections_applied = []
        
        for incorrect, correct in self.stt_corrections.items():
            if incorrect.lower() in corrected_text.lower():
                pattern = re.compile(re.escape(incorrect), re.IGNORECASE)
                corrected_text = pattern.sub(correct, corrected_text)
                corrections_applied.append({
                    'incorrect': incorrect,
                    'correct': correct,
                    'explanation': self._get_correction_explanation(incorrect, correct)
                })
        
        corrected_segments = []
        for segment in segments:
            segment_text = segment.get('text', '')
            for incorrect, correct in self.stt_corrections.items():
                pattern = re.compile(re.escape(incorrect), re.IGNORECASE)
                segment_text = pattern.sub(correct, segment_text)
            
            corrected_segment = segment.copy()
            corrected_segment['text'] = segment_text
            corrected_segments.append(corrected_segment)
        
        result = stt_result.copy()
        result['text'] = corrected_text
        result['segments'] = corrected_segments
        result['corrections_applied'] = corrections_applied
        
        if corrections_applied:
            logger.info(f"Applied {len(corrections_applied)} STT corrections")
        
        return result

    def _get_correction_explanation(self, incorrect: str, correct: str) -> str:
        """Get explanation for why a correction was made"""
        explanations = {
            'restaurant': 'Misheard word; changes meaning in context.',
            'cast': 'Proper noun correction.',
            '3632 months': 'Numbers mis-transcribed, clarified.',
            'weapon': 'Complete mishearing; correct phrase restored.',
            'milk': 'Single-word error correction.',
            'period': 'Misinterpreted filler or response.',
        }
        return explanations.get(incorrect, 'Common STT error correction.')

    def add_speaker_labels(self, stt_result: Dict) -> Dict:
        """
        Add speaker labels to create diarization
        
        Labels speakers as: [Trainer]:, [Aiden]:, [Cassidy]:, etc.
        Uses speaker_tag from Google Cloud STT or heuristics
        """
        segments = stt_result.get('segments', [])
        speaker_tags = stt_result.get('speaker_tags', {})
        
        speaker_segments = []
        current_speaker = None
        current_text = []
        current_start = None
        current_end = None
        current_words = []
        
        for segment in segments:
            speaker_tag = segment.get('speaker_tag')
            
            if speaker_tag is not None:
                speaker_name = self.speaker_names.get(f'speaker_{speaker_tag}', f'Speaker {speaker_tag}')
            else:
                speaker_name = self._infer_speaker(segment.get('text', ''))
            
            if speaker_name != current_speaker:
                if current_speaker and current_text:
                    speaker_segments.append(SpeakerSegment(
                        speaker_id=current_speaker,
                        text=' '.join(current_text),
                        start_time=current_start or 0,
                        end_time=current_end or 0,
                        confidence=segment.get('confidence', 1.0),
                        words=current_words
                    ))
                
                current_speaker = speaker_name
                current_text = [segment.get('text', '')]
                current_start = segment.get('start', 0)
                current_end = segment.get('end', 0)
                current_words = [segment]
            else:
                current_text.append(segment.get('text', ''))
                current_end = segment.get('end', 0)
                current_words.append(segment)
        
        if current_speaker and current_text:
            speaker_segments.append(SpeakerSegment(
                speaker_id=current_speaker,
                text=' '.join(current_text),
                start_time=current_start or 0,
                end_time=current_end or 0,
                confidence=1.0,
                words=current_words
            ))
        
        labeled_text = self._format_speaker_segments(speaker_segments)
        
        result = stt_result.copy()
        result['labeled_text'] = labeled_text
        result['speaker_segments'] = [
            {
                'speaker': seg.speaker_id,
                'text': seg.text,
                'start': seg.start_time,
                'end': seg.end_time,
                'confidence': seg.confidence
            }
            for seg in speaker_segments
        ]
        
        logger.info(f"Added speaker labels for {len(speaker_segments)} segments")
        return result

    def _infer_speaker(self, text: str) -> str:
        """Infer speaker based on content if speaker_tag not available"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['awesome', 'great job', 'how did that feel', 'let\'s practice']):
            return 'Trainer'
        
        if any(word in text_lower for word in ['i can understand', 'let me ask', 'what would you say']):
            return 'Aiden'
        
        if any(word in text_lower for word in ['i guess', 'i suppose', 'i\'m not sure']):
            return 'Cassidy'
        
        return 'Unknown'

    def _format_speaker_segments(self, segments: List[SpeakerSegment]) -> str:
        """Format speaker segments into labeled text"""
        lines = []
        for segment in segments:
            lines.append(f"[{segment.speaker_id}]: {segment.text}")
        return '\n\n'.join(lines)

    def segment_sentences(self, stt_result: Dict) -> Dict:
        """
        Segment transcript into proper sentences
        
        Transforms: "i might need to step off i have a couple of appointments..."
        Into: "I might need to step off. I have a couple of appointments..."
        """
        speaker_segments = stt_result.get('speaker_segments', [])
        
        segmented_segments = []
        for segment in speaker_segments:
            text = segment['text']
            
            sentences = self._segment_into_sentences(text)
            
            segmented_segment = segment.copy()
            segmented_segment['sentences'] = sentences
            segmented_segment['text'] = ' '.join(sentences)
            segmented_segments.append(segmented_segment)
        
        labeled_lines = []
        for segment in segmented_segments:
            for sentence in segment['sentences']:
                labeled_lines.append(f"[{segment['speaker']}]: {sentence}")
        
        result = stt_result.copy()
        result['speaker_segments'] = segmented_segments
        result['labeled_text'] = '\n\n'.join(labeled_lines)
        result['sentence_segmented'] = True
        
        logger.info(f"Segmented into sentences")
        return result

    def _segment_into_sentences(self, text: str) -> List[str]:
        """Segment text into proper sentences with capitalization and punctuation"""
        text = ' '.join(text.split())
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        if len(sentences) == 1:
            sentences = re.split(r'[,;]\s+(?=and|but|so|or|yet|however|therefore|i\s)', text, flags=re.IGNORECASE)
        
        formatted_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
            
            if not sentence[-1] in '.!?':
                if any(sentence.lower().startswith(q) for q in ['what', 'where', 'when', 'why', 'how', 'who', 'is', 'are', 'can', 'do', 'does']):
                    sentence += '?'
                else:
                    sentence += '.'
            
            formatted_sentences.append(sentence)
        
        return formatted_sentences

    def add_training_annotations(self, stt_result: Dict) -> Dict:
        """
        Add training point and technique annotations
        
        Identifies and labels:
        - [TRAINING POINT - Label]: Description
        - [TECHNIQUE - Label]: Description
        - [ROLE PLAY START/END]
        """
        speaker_segments = stt_result.get('speaker_segments', [])
        
        annotations = []
        annotated_segments = []
        
        for i, segment in enumerate(speaker_segments):
            text = segment['text']
            speaker = segment['speaker']
            
            if self._is_role_play_start(text, speaker):
                annotations.append(TrainingAnnotation(
                    annotation_type='ROLE PLAY',
                    label='START',
                    description=f'{speaker} as Coach/Prospect',
                    position=i
                ))
            
            training_point = self._identify_training_point(text, speaker)
            if training_point:
                annotations.append(TrainingAnnotation(
                    annotation_type='TRAINING POINT',
                    label=training_point['label'],
                    description=training_point['description'],
                    position=i
                ))
            
            technique = self._identify_technique(text, speaker)
            if technique:
                annotations.append(TrainingAnnotation(
                    annotation_type='TECHNIQUE',
                    label=technique['label'],
                    description=technique['description'],
                    position=i
                ))
            
            segment_annotations = [a for a in annotations if a.position == i]
            annotated_segment = segment.copy()
            annotated_segment['annotations'] = [
                {
                    'type': a.annotation_type,
                    'label': a.label,
                    'description': a.description
                }
                for a in segment_annotations
            ]
            annotated_segments.append(annotated_segment)
        
        annotated_text = self._format_annotated_text(annotated_segments)
        
        result = stt_result.copy()
        result['speaker_segments'] = annotated_segments
        result['annotated_text'] = annotated_text
        result['annotations'] = [
            {
                'type': a.annotation_type,
                'label': a.label,
                'description': a.description,
                'position': a.position
            }
            for a in annotations
        ]
        
        logger.info(f"Added {len(annotations)} training annotations")
        return result

    def _is_role_play_start(self, text: str, speaker: str) -> bool:
        """Detect if this is the start of a role play"""
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in [
            'let\'s start',
            'let\'s practice',
            'role play',
            'let\'s try',
            'begin the scenario'
        ]) and speaker == 'Trainer'

    def _identify_training_point(self, text: str, speaker: str) -> Optional[Dict]:
        """Identify training points in the conversation"""
        text_lower = text.lower()
        
        if 'i can understand' in text_lower or 'i see' in text_lower or 'that makes sense' in text_lower:
            return {
                'label': 'Acknowledge prospect\'s reasoning',
                'description': 'Recognize why the prospect wants to take action.'
            }
        
        if speaker in ['Cassidy', 'Prospect'] and any(word in text_lower for word in ['procrastinate', 'not sure', 'maybe', 'i guess']):
            return {
                'label': 'Identify Objection',
                'description': 'Prospect admits potential delay if not acted on immediately.'
            }
        
        if speaker == 'Trainer' and any(phrase in text_lower for phrase in ['how did that feel', 'what did you notice', 'how was that']):
            return {
                'label': 'Reflection',
                'description': 'Coach reviews role-play to reinforce learning.'
            }
        
        return None

    def _identify_technique(self, text: str, speaker: str) -> Optional[Dict]:
        """Identify sales techniques being demonstrated"""
        text_lower = text.lower()
        
        if 'why' in text_lower and any(time in text_lower for time in ['now', 'later', 'months', 'weeks']):
            return {
                'label': 'Timing Objection Handling',
                'description': 'Ask why they want to start now versus later.'
            }
        
        if 'urgency' in text_lower or 'commitment' in text_lower or ('have to' in text_lower and 'now' in text_lower):
            return {
                'label': 'Lock-in Timing',
                'description': 'Use their urgency to motivate commitment.'
            }
        
        if text.strip().endswith('?') and any(word in text_lower for word in ['what', 'how', 'why', 'tell me']):
            return {
                'label': 'Open-Ended Question',
                'description': 'Encourage prospect to share more information.'
            }
        
        return None

    def _format_annotated_text(self, segments: List[Dict]) -> str:
        """Format segments with inline annotations"""
        lines = []
        
        for segment in segments:
            speaker = segment['speaker']
            text = segment['text']
            annotations = segment.get('annotations', [])
            
            lines.append(f"[{speaker}]: \"{text}\"")
            
            for annotation in annotations:
                lines.append(f"[{annotation['type']} - {annotation['label']}]: {annotation['description']}")
            
            lines.append('')
        
        return '\n'.join(lines)

    def generate_correction_table(self, corrections: List[Dict]) -> str:
        """Generate a formatted table of STT corrections"""
        if not corrections:
            return "No corrections applied."
        
        table = "| Incorrect (STT) | Corrected | Explanation |\n"
        table += "|-----------------|-----------|-------------|\n"
        
        for correction in corrections:
            table += f"| {correction['incorrect']} | {correction['correct']} | {correction['explanation']} |\n"
        
        return table


_transcript_processor = None


def get_transcript_processor() -> TranscriptProcessor:
    """Get or create global transcript processor instance"""
    global _transcript_processor
    if _transcript_processor is None:
        _transcript_processor = TranscriptProcessor()
    return _transcript_processor
