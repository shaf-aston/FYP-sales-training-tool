"""Patch content.py:
1. Add combined elicitation examples to TACTICS
2. Update consultative intent_low STRUCTURE
3. Update transactional intent_low STRUCTURE
4. Refactor tactic_guidance: decisive short-circuit + combined elicitation pattern
"""

filepath = r"c:/Users/Shaf/Downloads/Final Year Project pack folder/Sales roleplay chatbot/src/chatbot/content.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes_applied = 0

# ── CHANGE 1: Add combined elicitation subtype to TACTICS ─────────────────
old1 = (
    '        "curiosity_statement": [\n'
    '            "I\'m curious what sparked this\u2014though no pressure.",\n'
    '            "Would be interesting to know what\'s changed.",\n'
    '            "I\'d guess something prompted this, even if it\'s small.",\n'
    '        ],\n'
    '    },'
)
new1 = (
    '        "curiosity_statement": [\n'
    '            "I\'m curious what sparked this\u2014though no pressure.",\n'
    '            "Would be interesting to know what\'s changed.",\n'
    '            "I\'d guess something prompted this, even if it\'s small.",\n'
    '        ],\n'
    '        # Combined: participation statement + soft follow-up in one response.\n'
    '        # Pattern: observation about their situation \u2192 natural open question.\n'
    '        "combined": [\n'
    '            "Sounds like you\'ve probably looked at a few options already. What\'s felt closest to what you\'re after?",\n'
    '            "I imagine this isn\'t the first time you\'ve thought about this. What\'s been the main thing holding you back?",\n'
    '            "Seems like you\'ve got a pretty clear idea of what you don\'t want. What would actually work look like for you?",\n'
    '            "I don\'t know, feels like something specific shifted recently. What got you looking at this now?",\n'
    '            "Most people I talk to are usually juggling a couple of things at once. What\'s taking up the most headspace right now?",\n'
    '            "I\'d guess you\'ve seen a few versions of this before. What\'s been missing from what you\'ve already tried?",\n'
    '            "Sounds like you\'re weighing a few things up. What\'s the one thing that would make this a no-brainer?",\n'
    '            "I don\'t know if it\'s been on your radar for a while\u2014what finally made you start looking properly?",\n'
    '        ],\n'
    '    },'
)
if old1 in content:
    content = content.replace(old1, new1, 1)
    changes_applied += 1
    print("CHANGE 1 applied: combined elicitation added to TACTICS")
else:
    print("CHANGE 1 FAILED: curiosity_statement close not found")


# ── CHANGE 2: Consultative intent_low STRUCTURE ────────────────────────────
old2 = (
    'STRUCTURE:\n'
    '- Acknowledge briefly.\n'
    '- Use ONE elicitation statement.\n'
    '- Stop.\n'
    '\n'
    'ADVANCE WHEN:\n'
    '- User volunteers problem/goal.\n'
    '- OR 6 turns max.\n'
    '""",'
)
new2 = (
    'STRUCTURE:\n'
    '- Acknowledge briefly (max 5 words).\n'
    '- Make ONE participation/observation statement about their situation.\n'
    '- Follow with ONE soft, open-ended question to keep conversation flowing.\n'
    '  \u2705 "What\u2019s felt hardest to figure out so far?"\n'
    '  \u274c "Are you interested in X?" (binary \u2014 kills flow)\n'
    '  \u274c Stopping after the statement alone (leaves a dead end)\n'
    '\n'
    'ADVANCE WHEN:\n'
    '- User volunteers problem/goal.\n'
    '- OR 6 turns max.\n'
    '""",'
)
if old2 in content:
    content = content.replace(old2, new2, 1)
    changes_applied += 1
    print("CHANGE 2 applied: consultative intent_low STRUCTURE updated")
else:
    print("CHANGE 2 FAILED: consultative intent_low STRUCTURE not matched")


# ── CHANGE 3: Transactional intent_low STRUCTURE ───────────────────────────
old3 = (
    'STRUCTURE:\n'
    '- Acknowledge.\n'
    '- Use ONE elicitation statement.\n'
    '- Stop.\n'
    '\n'
    'DO NOT:\n'
    '- Ask direct questions.\n'
    '- Pitch products.\n'
    '""",'
)
new3 = (
    'STRUCTURE:\n'
    '- Acknowledge briefly (max 5 words).\n'
    '- Make ONE participation/observation statement about their situation.\n'
    '- Follow with ONE soft, open-ended question to keep conversation flowing.\n'
    '  \u2705 "What\u2019s been the main thing putting you off so far?"\n'
    '  \u274c "Do you want to see options?" (binary \u2014 kills flow)\n'
    '  \u274c Stopping after the statement alone (leaves a dead end)\n'
    '\n'
    'DO NOT:\n'
    '- Ask direct interrogation-style questions.\n'
    '- Pitch products.\n'
    '""",'
)
if old3 in content:
    content = content.replace(old3, new3, 1)
    changes_applied += 1
    print("CHANGE 3 applied: transactional intent_low STRUCTURE updated")
else:
    print("CHANGE 3 FAILED: transactional intent_low STRUCTURE not matched")


# ── CHANGE 4: Tactic guidance — decisive short-circuit + combined pattern ──
old4 = (
    '    # Standard adaptive prompting\n'
    '    tactic_guidance = ""\n'
    '    if state["intent"] == \'low\' or state["guarded"] or state["question_fatigue"]:\n'
    '        if user_asking_literal_question:\n'
    '            # Speech Act Theory: literal questions override elicitation mode\n'
    '            # User asked a real question \u2014 answer it directly, don\'t elicit\n'
    '            tactic_guidance = """\n'
    'LITERAL QUESTION DETECTED (direct answer required):\n'
    'User asked a direct question. ANSWER IT with specific information.\n'
    'Do NOT respond with an elicitation statement \u2014 that would ignore their request.\n'
    '"""\n'
    '        else:\n'
    '            elicitation_example = get_tactic("elicitation")\n'
    '            reason = "low intent detected" if state["intent"] == \'low\' else "guarded response" if state["guarded"] else "question fatigue (2+ recent questions)"\n'
    '            tactic_guidance = f"""\n'
    'TACTIC OVERRIDE: Use ELICITATION (not direct questions)\n'
    'REASON: {reason}\n'
    'SUGGESTED STATEMENT: "{elicitation_example}"\n'
    '"""'
)
new4 = (
    '    # Standard adaptive prompting\n'
    '    tactic_guidance = ""\n'
    '\n'
    '    # Decisive short-circuit: short + commitment/high_intent \u2192 advance, never elicit\n'
    '    if state.get("decisive"):\n'
    '        advance_note = ("Move directly to pitch." if strategy == "transactional"\n'
    '                        else "Acknowledge and move the conversation forward \u2014 don\'t re-ask or loop.")\n'
    '        tactic_guidance = f"""\n'
    'DECISIVE USER DETECTED:\n'
    'User gave a short response containing commitment or high-intent signal.\n'
    'This is action, not hesitation. Treat it as affirmative.\n'
    '\u2192 DO NOT use elicitation or repeat exploratory questions.\n'
    '\u2192 {advance_note}\n'
    '\u2192 Match their energy: direct and efficient.\n'
    '"""\n'
    '    elif state["intent"] == \'low\' or state["guarded"] or state["question_fatigue"]:\n'
    '        if user_asking_literal_question:\n'
    '            # Speech Act Theory: literal questions override elicitation mode\n'
    '            # User asked a real question \u2014 answer it directly, don\'t elicit\n'
    '            tactic_guidance = """\n'
    'LITERAL QUESTION DETECTED (direct answer required):\n'
    'User asked a direct question. ANSWER IT with specific information.\n'
    'Do NOT respond with an elicitation statement \u2014 that would ignore their request.\n'
    '"""\n'
    '        else:\n'
    '            elicitation_example = get_tactic("elicitation", "combined")\n'
    '            reason = "low intent detected" if state["intent"] == \'low\' else "guarded response" if state["guarded"] else "question fatigue (2+ recent questions)"\n'
    '            tactic_guidance = f"""\n'
    'TACTIC OVERRIDE: Use ELICITATION with soft follow-up (not a direct question)\n'
    'REASON: {reason}\n'
    'PATTERN: [Participation/observation statement] \u2192 [ONE soft open-ended follow-up]\n'
    'EXAMPLE: "{elicitation_example}"\n'
    'RULES:\n'
    '- Statement first: make an observation about their situation (no interrogation)\n'
    '- Then ONE natural follow-up that keeps the conversation moving forward\n'
    '- Follow-up must be open-ended, not binary (no "Do you want X?" or "Are you Y?")\n'
    '- Every bot response should leave the conversation somewhere to go\n'
    '"""'
)
if old4 in content:
    content = content.replace(old4, new4, 1)
    changes_applied += 1
    print("CHANGE 4 applied: tactic_guidance refactored")
else:
    print("CHANGE 4 FAILED: tactic_guidance block not matched")
    idx = content.find('# Standard adaptive prompting')
    if idx >= 0:
        print("Nearby raw content:")
        print(repr(content[idx:idx+600]))


# ── Write out ───────────────────────────────────────────────────────────────
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"\nDone. {changes_applied}/4 changes applied to content.py")
