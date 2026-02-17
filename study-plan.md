Sales Chatbot User Acceptance Testing (UAT) Plan
Study Methodology
Format: Online remote testing (Zoom/Teams screen sharing)
Duration: 30-35 minutes per participant
Sample Size: 10-15 participants
Participant Profile: 50% sales professionals, 50% university students (no sales background)
Hybrid approach: Self-completed questionnaire + optional brief verbal debrief (2-3 mins)
Rationale for Online Testing:
•	Wider participant pool (no geographic constraints)
•	Natural environment (participants use own devices)
•	Screen-sharing for interviewer analysis (with explicit consent) 
________________________________________
Session Structure
1. Introduction & Consent (5 mins)
•	Explain project purpose: AI sales training chatbot evaluation
•	Review informed consent form 
•	Brief overview: "You'll test two sales conversation styles, have exploratory time and feedback at the end. Feel free to say ‘no’ to payment at the end"
2. Scenario 1: Fitness Prospect (7 mins)
Task: "Act as a fitness enthusiast wanting to lose fat and put on muscle. You're unsure about the best approach to achieve your goals."
Examiner Observation Metrics:
•	Stage progression accuracy (Intent → Logical → Emotional → Pitch → Objection)
•	Information extraction (5 fields: outcome, problem, goal, consequence, duration)
•	Tone matching (does bot mirror user's formality level?)
•	Conversation naturalness (awkward moments, repetition, over-probing)
•	Handling objections (if user says "too expensive," does bot reframe effectively?)
3. Scenario 2: Midrange Car Buyer (5 mins)
Task: "You want to buy a midrange car from the SEAT brand. You have a budget in mind and want quick answers about features and pricing."
1.	Time-to-Pitch:
o	Target: ≤2 conversational turns after Transactional selling initiates
o	Rationale: Prioritizes quick responses for high-intent buyers.
2.	Action-Oriented Closing:
o	Target: 100% of pitches end with clear actions (e.g., "This model is $25,000 and available next week.", or package options).
o	Prohibited: Permission-style questions (e.g., "Would you like...?").
3.	Feature Clarity:
o	Target: 90% of feature queries answered in ≤2 turns.
o	Rationale: Ensures concise, relevant responses.
4.	Budget Alignment:
o	Target: 100% of recommendations align with the buyer's budget.
o	Rationale: Maintains trust and relevance.
5.	Tone Matching:
o	Target: ≥95% tone alignment with buyer communication style.
o	Rationale: Builds rapport and ensures seamless interaction.
6.	Stage Progression:
o	Target: ≥90% appropriate stage progression (intent → pitch → objection handling).
o	Rationale: Ensures efficient transactional flow.

4. Free Exploration (5 mins)
Task: "Try any conversation style you want. Test edge cases, be difficult, act disinterested OR be really interested."
Examiner Observation Metrics:
•	Low-intent handling (user says "just browsing" → bot should not force pitch and attempt to drive conversation into intent)
•	Appropriate strategy selection and switching (consultative ↔ transactional)
•	Error recovery (API failures, nonsensical inputs)

5. Questionnaire Completion (10 mins)
Participants complete structured feedback form (see Questionnaire section below)
6. Brief Verbal Debrief (0 – 1.5 mins)
________________________________________
Quantitative Metrics Tracking Sheet (For Examiner)
For each participant, record:
Metric	Target	Actual	Pass/Fail
Stage Progression Accuracy	Intent → Logical → Emotional → Pitch → Objection (consultative) OR Intent → Pitch → Objection (transactional)	[Count correct transitions / total transitions]	≥85% = Pass
Information Extraction Completeness	5 fields captured (outcome, problem, goal, consequence, duration) overall and 	[Fields extracted: X/5]	≥3/5 = Pass
Tone Matching	Bot mirrors user formality (casual user → casual bot, formal user → formal bot)	Yes/No	Yes = Pass
Time-to-Pitch (Transactional)	≤3 conversational turns before pitch	[Turns: X]	≤3 = Pass
Response Latency	<2 seconds per response	[Avg: Xms]	<2000ms = Pass
Low-Intent Handling	No forced pitch when user disinterested	Appropriate/Forced	Appropriate = Pass
Error Recovery	Graceful handling of API errors, nonsensical input	Yes/No	Yes = Pass
			
Aggregate Analysis: Calculate pass rate across all participants for each metric (e.g., "Stage Progression: 12/15 participants = 80% pass rate")
________________________________________
Questionnaire (Post-Session)
Hybrid Approach Rationale:
- Written component: Standardized data collection, reduced social desirability bias, minimizes examiner’s influence on questionnaire hence study, quantitative analysis, faster administration
- Verbal component: Captures nuanced reasoning, clarifies ambiguous responses, probes specific technical issues

1. Demographics
•	Age Range: (18–24, 25–34, 35–44, 45+)
•	Gender: Male / Female / Other / Prefer not to say
•	Education Level: (High school, Undergraduate, Postgraduate)
•	Professional background or area of expertise: (open-ended, e.g. technology, pharmacy, education)
•	Are you currently employed in sales or have prior sales experience? (Yes / No)
◦	  If Yes: Years of experience (0–1, 2–5, 6–10, 10+)
◦	  If Yes: Have you received formal training in sales methodologies (SPIN, IMPACT, Challenger, etc.)? (Yes / No / Unsure)
◦	  If No: Are you familiar with sales techniques? (Yes / No)
•	Have you used a chatbot before? (Yes / No)
◦	  If Yes: For what purpose? (e.g. customer service, personal assistant)

2. Chatbot Performance for each below (Likert Scale: 1=Strongly Disagree, 5=Strongly Agree)
•	The chatbot's conversation felt natural and realistic
•	The chatbot's responses were relevant to my input
•	The chatbot maintained appropriate conversation flow (didn't ask too many questions at once)
•	The chatbot adapted to my communication style (tone, formality)
•	The chatbot would be useful for sales training
•	The chatbot's interface was intuitive and easy to use
Analysis Target: Calculate mean score per question; identify strengths (≥4.0) and weaknesses (<2.5)
•	Did you notice any repetitive or awkward responses? (Yes/No)
o	If Yes: Please describe briefly (open-ended)
•	Did the chatbot handle objections effectively (if you raised any)? (Yes/No/Did not test)
Rationale: These questions map directly to technical requirements (R1-R5) and fixed issues (tone matching, over-probing)
3. Comparative Usefulness
•	Would you recommend this chatbot to sales professionals for practice? (Yes/No/Maybe)
•	Would you recommend this chatbot to students starting-out/learning sales? (Yes/No/Maybe)
•	In your opinion, compared to traditional roleplay with human partners, this chatbot is: (Much worse / Worse / About the same / Better / Much better)
Rationale: Validates business value proposition (cost-effective alternative to human roleplay)
4. Qualitative Feedback (Open-Ended)
•	What did you find most helpful about the chatbot?
•	What was the most frustrating or confusing aspect?
•	Did you encounter any technical issues (errors, slow responses, unclear behavior)?
•	What one feature would most improve your experience?
Analysis Method: Thematic coding of responses; identify recurring issues (e.g., if 5+ participants mention "repetitive questions," this indicates systematic problem)
5. Feature Prioritization (Rate Importance: 1=Not Important, 5=Very Important) [OPTIONAL – Not key features; allows people to finish early if they wish]
•	Ability to edit or retry chatbot responses
•	Voice input (dictation) instead of typing
•	Text-to-speech audio for chatbot responses
•	Timestamps for each message
•	Performance feedback at end of conversation (score, areas to improve)
•	Ability to export conversation transcript
Rationale: Identifies future development priorities based on user demand; validates scope decisions (e.g., if TTS rated <2.5, confirms it's appropriate to exclude)

6. Brief Verbal Debrief
• Examiner unmutes and asks: "Anything else you'd like to add that wasn't in the form?"
• Asks 1-2 probing questions based on questionnaire responses (see Verbal Debrief Protocol section)
• Flow: Summary question → Listen → 1-2 targeted follow-ups → Closing
• Examiner to take notes of answers
________________________________________
Ethical Considerations
Informed Consent:
•	Participants receive plain-language consent form explaining: study purpose, data usage, screen recording, withdrawal rights
•	Explicit consent required for screen recording and data retention
•	Participants can withdraw at any point and skip any questions without penalty 
Data Protection:
•	Responses anonymized (no personal identifiers unless participant consents)
•	Screen recordings stored securely (password-protected, deleted after analysis)
•	GDPR compliance: participants can request data deletion within 30 days
Risk Assessment:
•	Minimal risk (no sensitive data collection, no deception, no physical harm)
•	Debrief provided at end (project goals explained, contact info for questions)
________________________________________
































REMOVE FROM ETHICS APPLICATION
Study Timeline
Week 1: Ethics approval submission
Week 2-3: Participant recruitment (social media, university forums, professional networks)
Week 4-5: Conduct testing sessions (2-3 per day)
Week 6: Data analysis and report integration
________________________________________
Expected Outcomes
Success Criteria:
•	≥80% of participants rate chatbot ≥4/5 on usefulness
•	≥85% pass rate on stage progression accuracy
•	≥70% recommend chatbot for sales training
Risk Mitigation:
•	If <70% satisfaction: Conduct 2-3 follow-up interviews to diagnose issues
•	If technical failures >20%: Debug before reporting results
•	If recruitment slow: Extend timeline or reduce sample size to n=8 minimum
________________________________________
Purpose of This Study
This UAT validates:
1.	Requirements Satisfaction (R1-R5, NF1-NF4): Do features work as designed?
2.	User Acceptance: Would real users find this valuable for sales training?
3.	Comparative Value: Is this better/worse/equivalent to human roleplay?
4.	Evidence-Based Evaluation: Transforms developer claims (92% accuracy) into independent validation
Academic Contribution: Demonstrates systematic evaluation methodology required for CS3IP 70%+ marks; provides empirical evidence for project's effectiveness beyond self-assessment.
