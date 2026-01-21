"""Shared prompt utilities for all strategies (DRY principle)"""


def get_base_rules():
    """Core conversational rules applied to all strategies"""
    return """CORE RULES:
- ONE question maximum per response (count your '?' marks)
- Never use 'but' after compliments (use 'and' or separate sentences)
- Match user's communication style (short replies = be direct)
- If user frustrated/annoyed: acknowledge, don't probe that turn
- Brief and conversational"""


def format_extracted_context(extracted):
    """Format extracted info for prompt injection"""
    lines = []
    
    if extracted.get("desired_outcome"):
        lines.append(f"✓ KNOWN OUTCOME: {extracted['desired_outcome'][:100]}")
    
    if extracted.get("problem"):
        lines.append(f"✓ KNOWN PROBLEM: {extracted['problem'][:100]}")
    
    if extracted.get("current_strategy"):
        lines.append(f"✓ CURRENT APPROACH: {extracted['current_strategy'][:100]}")
    
    if extracted.get("duration"):
        lines.append(f"✓ TIMELINE: {extracted['duration'][:50]}")
    
    goals = extracted.get("goals", [])
    if goals:
        lines.append(f"✓ GOALS: {len(goals)} identified")
    
    consequences = extracted.get("consequences", [])
    if consequences:
        lines.append(f"✓ CONSEQUENCES: {len(consequences)} identified")
    
    if not lines:
        return "📋 NO CONTEXT EXTRACTED YET"
    
    return "\n".join(lines)


def get_base_prompt(product_context, strategy_type, extracted):
    """Shared prompt foundation for all strategies"""
    return f"""You are a natural sales professional. PRODUCT: {product_context}

{get_base_rules()}

STRATEGY: {strategy_type.upper()}

EXTRACTED CONTEXT:
{format_extracted_context(extracted)}
"""
