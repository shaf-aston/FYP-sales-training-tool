"""
Role-Play Analysis Component
Specialized analyzer for sales role-play interactions
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import re

from .audio_analysis_models import (
    TimestampedSegment, RolePlayBlock, RolePlayPhase, Speaker, ContextSection
)

logger = logging.getLogger(__name__)

class RolePlayAnalyzer:
    """
    Specialized analyzer for sales role-play scenarios
    Identifies phases, techniques, and effectiveness patterns
    """
    
    def __init__(self):
        """Initialize the role-play analyzer"""
        self.phase_keywords = {
            RolePlayPhase.OPENING: [
                'hello', 'hi', 'good morning', 'good afternoon', 'introduction',
                'my name is', 'calling from', 'reaching out'
            ],
            RolePlayPhase.DISCOVERY: [
                'tell me', 'what are', 'how do you', 'current situation',
                'challenge', 'problem', 'need', 'goal', 'objective'
            ],
            RolePlayPhase.PRESENTATION: [
                'solution', 'product', 'service', 'feature', 'benefit',
                'can help', 'offer', 'provide', 'deliver'
            ],
            RolePlayPhase.HANDLING_OBJECTIONS: [
                'but', 'however', 'concern', 'issue', 'worry', 'problem',
                'understand', 'appreciate', 'i see your point'
            ],
            RolePlayPhase.CLOSING: [
                'next step', 'move forward', 'agreement', 'contract',
                'sign up', 'get started', 'schedule', 'meeting'
            ]
        }
        
        self.sales_techniques = {
            'questioning': ['what', 'how', 'when', 'where', 'why', '?'],
            'empathy': ['understand', 'appreciate', 'feel', 'realize'],
            'benefit_selling': ['benefit', 'advantage', 'value', 'save', 'increase'],
            'storytelling': ['story', 'example', 'client', 'customer', 'similar situation'],
            'assumptive_close': ['when we', 'after you', 'once you start'],
            'trial_close': ['how does that sound', 'what do you think', 'make sense']
        }
        
        logger.info("✅ Role-Play Analyzer initialized")
    
    def analyze(self, segments: List[TimestampedSegment], 
               speakers: List[Speaker],
               context_sections: List[ContextSection]) -> List[RolePlayBlock]:
        """
        Analyze segments to identify role-play blocks and phases
        
        Args:
            segments: Conversation segments
            speakers: Identified speakers
            context_sections: Context analysis results
            
        Returns:
            List of identified role-play blocks
        """
        try:
            if not segments:
                return []
            
            logger.info(f"Analyzing {len(segments)} segments for role-play patterns")
            
            # Step 1: Identify phase transitions
            phase_segments = self._identify_phases(segments)
            
            # Step 2: Group segments into blocks
            blocks = self._create_roleplay_blocks(phase_segments, speakers)
            
            # Step 3: Analyze techniques used in each block
            for block in blocks:
                block.techniques_used = self._identify_techniques(block.segments)
                block.effectiveness_score = self._calculate_block_effectiveness(block)
            
            logger.info(f"Identified {len(blocks)} role-play blocks")
            return blocks
            
        except Exception as e:
            logger.error(f"Role-play analysis failed: {e}")
            return []
    
    def _identify_phases(self, segments: List[TimestampedSegment]) -> List[Tuple[TimestampedSegment, RolePlayPhase]]:
        """Identify the role-play phase for each segment"""
        phase_segments = []
        
        for segment in segments:
            text_lower = segment.text.lower()
            phase_scores = {}
            
            # Score each phase based on keyword matches
            for phase, keywords in self.phase_keywords.items():
                score = sum(1 for keyword in keywords if keyword in text_lower)
                if score > 0:
                    phase_scores[phase] = score
            
            # Assign the phase with highest score, or DISCOVERY as default
            if phase_scores:
                best_phase = max(phase_scores.keys(), key=lambda p: phase_scores[p])
            else:
                best_phase = RolePlayPhase.DISCOVERY
            
            phase_segments.append((segment, best_phase))
        
        return phase_segments
    
    def _create_roleplay_blocks(self, phase_segments: List[Tuple[TimestampedSegment, RolePlayPhase]], 
                               speakers: List[Speaker]) -> List[RolePlayBlock]:
        """Group consecutive segments of same phase into blocks"""
        if not phase_segments:
            return []
        
        blocks = []
        current_phase = None
        current_segments = []
        block_id = 0
        
        for segment, phase in phase_segments:
            if phase != current_phase:
                # Start new block if we have accumulated segments
                if current_segments:
                    block = self._create_block(block_id, current_phase, current_segments)
                    blocks.append(block)
                    block_id += 1
                
                # Start new accumulation
                current_phase = phase
                current_segments = [segment]
            else:
                # Continue current block
                current_segments.append(segment)
        
        # Don't forget the last block
        if current_segments:
            block = self._create_block(block_id, current_phase, current_segments)
            blocks.append(block)
        
        return blocks
    
    def _create_block(self, block_id: int, phase: RolePlayPhase, 
                     segments: List[TimestampedSegment]) -> RolePlayBlock:
        """Create a role-play block from segments"""
        start_time = segments[0].start_time
        end_time = segments[-1].end_time
        
        return RolePlayBlock(
            id=f"roleplay_block_{block_id}",
            phase=phase,
            start_time=start_time,
            end_time=end_time,
            segments=segments,
            techniques_used=[],  # Will be filled by _identify_techniques
            effectiveness_score=0.0,  # Will be calculated later
            metadata={
                'segment_count': len(segments),
                'duration': end_time - start_time,
                'created_at': datetime.now().isoformat()
            }
        )
    
    def _identify_techniques(self, segments: List[TimestampedSegment]) -> List[str]:
        """Identify sales techniques used in the given segments"""
        techniques = set()
        
        for segment in segments:
            text_lower = segment.text.lower()
            
            # Check for each technique
            for technique, keywords in self.sales_techniques.items():
                if any(keyword in text_lower for keyword in keywords):
                    techniques.add(technique)
        
        return list(techniques)
    
    def _calculate_block_effectiveness(self, block: RolePlayBlock) -> float:
        """Calculate effectiveness score for a role-play block"""
        score = 0.5  # Base score
        
        # Technique diversity bonus
        technique_count = len(block.techniques_used)
        score += min(technique_count * 0.1, 0.3)  # Max 0.3 bonus
        
        # Phase-specific scoring
        if block.phase == RolePlayPhase.DISCOVERY:
            # Discovery should have questioning
            if 'questioning' in block.techniques_used:
                score += 0.1
        elif block.phase == RolePlayPhase.PRESENTATION:
            # Presentation should have benefit selling
            if 'benefit_selling' in block.techniques_used:
                score += 0.1
        elif block.phase == RolePlayPhase.HANDLING_OBJECTIONS:
            # Objection handling should have empathy
            if 'empathy' in block.techniques_used:
                score += 0.1
        elif block.phase == RolePlayPhase.CLOSING:
            # Closing should have closing techniques
            if any(tech in block.techniques_used for tech in ['assumptive_close', 'trial_close']):
                score += 0.1
        
        # Duration appropriateness (not too short, not too long)
        duration = block.end_time - block.start_time
        if 10 <= duration <= 120:  # 10 seconds to 2 minutes is good
            score += 0.1
        
        # Engagement level (based on segment count)
        if len(block.segments) >= 3:
            score += 0.05
        
        return min(score, 1.0)
    
    def get_phase_statistics(self, blocks: List[RolePlayBlock]) -> Dict[str, Any]:
        """Get statistics about phase distribution and effectiveness"""
        if not blocks:
            return {}
        
        phase_stats = {}
        
        for phase in RolePlayPhase:
            phase_blocks = [b for b in blocks if b.phase == phase]
            
            if phase_blocks:
                total_duration = sum(b.end_time - b.start_time for b in phase_blocks)
                avg_effectiveness = sum(b.effectiveness_score for b in phase_blocks) / len(phase_blocks)
                
                phase_stats[phase.value] = {
                    'block_count': len(phase_blocks),
                    'total_duration': total_duration,
                    'average_duration': total_duration / len(phase_blocks),
                    'average_effectiveness': avg_effectiveness,
                    'techniques_used': list(set(
                        tech for block in phase_blocks for tech in block.techniques_used
                    ))
                }
            else:
                phase_stats[phase.value] = {
                    'block_count': 0,
                    'total_duration': 0,
                    'average_duration': 0,
                    'average_effectiveness': 0,
                    'techniques_used': []
                }
        
        return phase_stats
    
    def get_technique_analysis(self, blocks: List[RolePlayBlock]) -> Dict[str, Any]:
        """Analyze technique usage across all blocks"""
        technique_usage = {technique: 0 for technique in self.sales_techniques.keys()}
        
        for block in blocks:
            for technique in block.techniques_used:
                if technique in technique_usage:
                    technique_usage[technique] += 1
        
        total_blocks = len(blocks)
        
        return {
            'technique_counts': technique_usage,
            'technique_percentages': {
                tech: (count / total_blocks * 100) if total_blocks > 0 else 0
                for tech, count in technique_usage.items()
            },
            'most_used_technique': max(technique_usage.keys(), key=technique_usage.get) if technique_usage else None,
            'total_techniques_identified': sum(technique_usage.values())
        }