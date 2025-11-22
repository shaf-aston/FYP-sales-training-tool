import os
import json
import re
from pathlib import Path
import nltk
from nltk.tokenize import sent_tokenize

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class NEPQProcessor:
    def __init__(self):
        self.processed_path = Path("../processed")
        self.transcripts_path = self.processed_path / "transcripts"
        self.scripts_path = self.processed_path / "scripts"
        self.output_path = self.processed_path / "nepq_data"
        self.output_path.mkdir(exist_ok=True, parents=True)
        
        self.nepq_keywords = {
            "rapport": ["curious", "brought you here", "what made you", "how did you hear", "what's going on", 
                       "tell me about", "what's happening", "getting to know", "background", "introduction"],
            "pain_discovery": ["challenge", "problem", "issue", "struggle", "difficulty", "frustrate", 
                              "concern", "worry", "pain", "trouble", "obstacle", "bottleneck", "what if", 
                              "how would", "what would happen", "cost you", "impact", "affect"],
            "solution": ["would it help", "imagine if", "what if", "benefit", "value", "solution", 
                        "resolve", "improve", "enhance", "opportunity", "advantage", "help you"],
            "closing": ["next step", "move forward", "decision", "invest", "purchase", "buy", 
                       "implementation", "timeline", "when can", "how soon", "budget", "plan to"]
        }
        
        self.speaker_patterns = [
            r'(?i)(sales|rep|agent|representative|john|associate|advisor|seller)[\s:]+(.+)',
            r'(?i)(customer|client|prospect|lead|buyer)[\s:]+(.+)',
            r'(?i)(q:|question:)(.+)',
            r'(?i)(a:|answer:)(.+)',
        ]
    
    def clean_text(self, text):
        """Clean and normalize text"""
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]|\(\d{2}:\d{2}\)', '', text)
        
        text = re.sub(r'^(Sales|Customer|Rep|Agent|Client)[\s:]+', '', text, flags=re.IGNORECASE)
        
        filler_words = r'\b(uh|um|you know|like|sort of|kind of|basically|actually|literally|just)\b'
        text = re.sub(filler_words, '', text, flags=re.IGNORECASE)
        
        text = re.sub(r'\s+', ' ', text).strip()
        
        text = re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '<NAME>', text)
        text = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '<PHONE>', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '<EMAIL>', text)
        
        return text
    
    def detect_speaker(self, text):
        """Attempt to detect if a piece of text is from sales or customer"""
        for pattern in self.speaker_patterns:
            match = re.search(pattern, text)
            if match:
                speaker_hint = match.group(1).lower()
                message = match.group(2).strip()
                
                if any(term in speaker_hint for term in ["sales", "rep", "agent", "john", "associate", "advisor", "q:", "seller"]):
                    return "assistant", message
                else:
                    return "user", message
        
        text_lower = text.lower()
        
        if text.endswith("?") or any(phrase in text_lower for phrase in 
                                     ["how", "what", "why", "could you", "would you", "tell me"]):
            for category, keywords in self.nepq_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    return "assistant", text
        
        return "user", text
    
    def identify_nepq_stage(self, text):
        """Identify which NEPQ stage this text belongs to"""
        text_lower = text.lower()
        
        for stage, keywords in self.nepq_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return stage
        
        return "general"
    
    def segment_raw_text(self, content):
        """Break raw text into conversational segments"""
        content = re.sub(r'(?i)^(transcript|recording|call log|date|time|duration).*\n', '', content, flags=re.MULTILINE)
        
        segments = []
        
        speaker_split = re.split(r'\n(?=(?:Sales|Customer|Rep|Agent|Client|Q:|A:))', content)
        
        if len(speaker_split) <= 1:
            speaker_split = [seg.strip() for seg in re.split(r'\n\s*\n', content) if seg.strip()]
            
            if len(speaker_split) <= 1:
                speaker_split = sent_tokenize(content)
        
        for segment in speaker_split:
            segment = segment.strip()
            if not segment:
                continue
                
            role, clean_message = self.detect_speaker(segment)
            clean_message = self.clean_text(clean_message)
            
            if clean_message:
                stage = self.identify_nepq_stage(clean_message)
                segments.append({
                    "role": role, 
                    "content": clean_message,
                    "stage": stage
                })
        
        return segments
    
    def group_into_conversations(self, segments, min_exchanges=3):
        """Group segments into meaningful conversations"""
        conversations = []
        current_conversation = []
        
        for segment in segments:
            current_conversation.append(segment)
            
            greeting_patterns = ["hi", "hello", "good morning", "good afternoon", "thanks for"]
            if (segment["role"] == "assistant" and 
                any(pattern in segment["content"].lower() for pattern in greeting_patterns) and 
                len(current_conversation) > min_exchanges):
                conversations.append(current_conversation)
                current_conversation = [segment]
        
        if len(current_conversation) >= min_exchanges:
            conversations.append(current_conversation)
            
        return conversations
    
    def format_for_training(self, conversations):
        """Format conversations for model training"""
        formatted_data = []
        
        for conversation in conversations:
            if len(conversation) < 2:
                continue
            
            messages = [
                {"role": "system", "content": "You are a sales assistant trained in the NEPQ framework. Ask emotionally engaging questions to uncover pain points and guide prospects to self-discovery."}
            ]
            
            for msg in conversation:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            formatted_data.append({"messages": messages})
        
        return formatted_data
    
    def process_transcript_file(self, file_path):
        """Process a single transcript file"""
        print(f"Processing: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        segments = self.segment_raw_text(content)
        
        conversations = self.group_into_conversations(segments)
        
        return conversations
    
    def process_all_files(self):
        """Process all transcript and script files"""
        all_conversations = []
        
        if self.transcripts_path.exists():
            for file_path in self.transcripts_path.glob("*.txt"):
                conversations = self.process_transcript_file(file_path)
                all_conversations.extend(conversations)
        
        if self.scripts_path.exists():
            for file_path in self.scripts_path.glob("*.txt"):
                conversations = self.process_transcript_file(file_path)
                all_conversations.extend(conversations)
            
        formatted_data = self.format_for_training(all_conversations)
        
        output_file = self.output_path / "nepq_dataset.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in formatted_data:
                f.write(json.dumps(item) + '\n')
        
        output_file_json = self.output_path / "nepq_dataset.json"
        with open(output_file_json, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2)
        
        readable_file = self.output_path / "nepq_dataset_readable.txt"
        with open(readable_file, 'w', encoding='utf-8') as f:
            for i, item in enumerate(formatted_data):
                f.write(f"=== Conversation {i+1} ===\n")
                for msg in item["messages"]:
                    f.write(f"{msg['role']}: {msg['content']}\n")
                f.write("\n\n")
        
        stats = {
            "total_conversations": len(formatted_data),
            "total_messages": sum(len(conv["messages"]) for conv in formatted_data),
            "average_conversation_length": sum(len(conv["messages"]) for conv in formatted_data) / len(formatted_data) if formatted_data else 0,
            "stage_distribution": {}
        }
        
        stage_counts = {}
        for conv in all_conversations:
            for msg in conv:
                stage = msg.get("stage", "general")
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        stats["stage_distribution"] = stage_counts
        
        stats_file = self.output_path / "nepq_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        
        print(f"Processed {len(formatted_data)} conversations")
        print(f"Saved to: {self.output_path}")
        
        return formatted_data

if __name__ == "__main__":
    processor = NEPQProcessor()
    processed_data = processor.process_all_files()