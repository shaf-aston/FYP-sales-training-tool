#!/usr/bin/env python3
"""
Generate sample training data for testing
"""
import json
from pathlib import Path

def generate_sample_data():
    conversations = [
        {
            "input": "I'm interested in your product but the price seems high.",
            "output": "I understand your concern about pricing. Let me explain the value you'll receive. Our product includes premium features that save you time and money in the long run. Can I walk you through the ROI calculation?"
        },
        {
            "input": "What makes your solution different from competitors?",
            "output": "Great question! Our unique approach focuses on three key differentiators: personalized implementation support, integrated analytics dashboard, and 24/7 customer success team. Which of these matters most to you?"
        },
        {
            "input": "I need to think about it.",
            "output": "Of course, this is an important decision. What specific aspects would you like to think over? I'm happy to provide any additional information that would help you make a confident choice."
        },
        {
            "input": "Do you offer a trial period?",
            "output": "Yes, we offer a 14-day free trial with full access to all features. This gives you time to experience the value firsthand. Would you like me to set that up for you today?"
        },
        {
            "input": "How long does implementation take?",
            "output": "Implementation typically takes 2-3 weeks depending on your specific needs. Our team handles the technical setup while training your staff. We also provide ongoing support to ensure a smooth transition."
        },
        {
            "input": "I'm not the decision maker. I need to discuss with my team.",
            "output": "I completely understand. Would it be helpful if I joined your team discussion to answer any technical questions? Or I can provide you with materials to share with stakeholders?"
        },
        {
            "input": "What's included in the support package?",
            "output": "Our support package includes 24/7 technical assistance, dedicated account manager, quarterly strategy reviews, and unlimited training sessions. We're committed to your long-term success."
        },
        {
            "input": "Can you send me more information?",
            "output": "Absolutely. I'd be happy to send detailed information. To make sure I send the most relevant materials, what specific areas are you most interested in learning about?"
        }
    ]
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    with open(data_dir / "sample_training.jsonl", "w") as f:
        for conv in conversations:
            f.write(json.dumps(conv) + "\n")
    
    print(f"Generated {len(conversations)} sample conversations")
    print(f"Saved to: data/sample_training.jsonl")
    print("\nTo train with this data:")
    print("  python train.py --data_path data/sample_training.jsonl --epochs 5 --batch_size 2")

if __name__ == "__main__":
    generate_sample_data()
