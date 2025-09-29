"""
Enhanced Conversational Response System
Makes characters more flexible and natural in conversations
"""

def generate_conversational_response(message, character, character_type):
    """Generate natural, flexible responses that stay in character"""
    message_lower = message.lower()
    name = character['name']
    
    # Food-related responses
    if any(word in message_lower for word in ['food', 'eat', 'meal', 'diet', 'nutrition', 'hungry']):
        if character_type == "mary_senior":
            return f"Well, at my age I try to eat healthy! I love vegetables from my garden, though I do have a sweet tooth for cookies. What about you - do you have favorite healthy foods? I'm always looking for new ideas that are good for someone with my health concerns."
        elif character_type == "jake_athlete":
            return f"Nutrition is huge for my performance! I'm big on lean proteins, complex carbs for energy, and tons of vegetables. I time my meals around training. What's your approach to nutrition? Are you looking to fuel workouts or more general health?"
        elif character_type == "sarah_mom":
            return f"Oh gosh, with two kids it's chaos! I try to cook healthy meals but sometimes it's whatever's fastest. The kids love pasta and I sneak vegetables in where I can. Do you have any quick healthy meal ideas that actually taste good?"
        else:  # tom_executive
            return f"Honestly, I eat whatever's convenient - probably part of my health problems. My assistant orders lunch, I grab coffee constantly. My doctor says I need to be more intentional about nutrition. What do busy people like us actually do to eat better?"
    
    # Personal questions (name, age, etc.)
    elif any(word in message_lower for word in ['name', 'who are you', 'tell me about yourself']):
        if character_type == "mary_senior":
            return f"I'm Mary! I'm 65 and recently retired after teaching for 35 years. I have some arthritis in my knees and occasional back pain, but I'm determined to get healthier. I want to be strong enough to keep up with my grandkids! What brings you here today?"
        elif character_type == "jake_athlete":
            return f"I'm Jake, 28, professional athlete. I train 6 days a week but I'm always looking to optimize performance and prevent injury - had an ACL issue before. Every edge matters in competition. What's your fitness background?"
        elif character_type == "sarah_mom":
            return f"Hi! I'm Sarah, 35, working mom of two amazing but exhausting kids. I used to be active but now I'm lucky if I get 5 minutes to myself! I need to find realistic ways to get healthy again. Do you work with busy parents?"
        else:  # tom_executive
            return f"Tom here, 45, business executive. Doctor gave me a wake-up call about pre-diabetes and blood pressure. I was athletic in college but work consumed everything. I need efficient, proven results. What's your track record with executives?"
    
    # Greeting responses
    elif any(word in message_lower for word in ['hi', 'hello', 'hey', 'greetings']):
        if character_type == "mary_senior":
            return f"Hello there! I'm Mary. It's so nice to meet you! I'm hoping you can help me figure out safe ways to get stronger at my age. I'm a bit nervous about doing the wrong thing, but I'm ready to start!"
        elif character_type == "jake_athlete":
            return f"Hey! Jake here. Good to meet you. I'm looking to take my training and performance to the next level. Always interested in what the latest research shows. What's your approach?"
        elif character_type == "sarah_mom":
            return f"Hi! I'm Sarah - thanks for fitting me into your schedule! I know how busy everyone is. I'm really hoping we can find something that works with my crazy mom life. Do you have experience with parents?"
        else:  # tom_executive
            return f"Hello. I'm Tom. Let's get straight to business - my time is limited but my health situation is serious. I need to see clear results efficiently. What's your methodology?"
    
    # Goals and motivation
    elif any(word in message_lower for word in ['goal', 'want', 'need', 'help', 'achieve']):
        if character_type == "mary_senior":
            return f"I really want to lose some weight and get stronger, but safely! I don't want to hurt my knees or back. I'd love to have the energy to garden more and keep up with my grandchildren. What do you think is realistic for someone like me?"
        elif character_type == "jake_athlete":
            return f"My goals are maintaining peak performance, injury prevention, and finding any edge I can get. I can't afford to be sidelined again. What does cutting-edge sports science say about optimization?"
        elif character_type == "sarah_mom":
            return f"I want to lose this baby weight and have energy to actually enjoy my kids instead of just surviving each day! I also want to be a good role model for them about healthy living. What's actually achievable for busy moms?"
        else:  # tom_executive
            return f"I need to lose 40-50 pounds, get my blood pressure and pre-diabetes under control, and reduce stress. Doctor's orders. I want measurable results and ROI on my time investment. What's your success rate?"
    
    # Time and schedule questions
    elif any(word in message_lower for word in ['time', 'busy', 'schedule', 'when', 'how long']):
        if character_type == "mary_senior":
            return f"Well, now that I'm retired I actually have more time than I've had in years! But I want to use it wisely. How often should someone my age exercise? I don't want to overdo it."
        elif character_type == "jake_athlete":
            return f"I train 6 days a week already, but I'm always looking to optimize the time. Recovery timing is crucial too. What does your research show about training frequency for athletes?"
        elif character_type == "sarah_mom":
            return f"Time is my biggest challenge! Between work, kids, household stuff... I might have 15-20 minutes here and there. Is that even worth it? Can you actually get results with tiny time chunks?"
        else:  # tom_executive
            return f"Time is money. I need maximum efficiency. What's the minimum effective dose to get health results? I can probably commit 30-45 minutes if I see ROI. What's realistic?"
    
    # Money/cost questions  
    elif any(word in message_lower for word in ['cost', 'money', 'price', 'afford', 'investment']):
        if character_type == "mary_senior":
            return f"I'm comfortable financially since I retired, but I want to be smart about spending. I see this as an investment in my health. What are we looking at cost-wise? I want to make sure I can stick with it."
        elif character_type == "jake_athlete":
            return f"I invest heavily in my performance - it's my career. If you can show me proven results and give me a competitive edge, cost isn't the primary concern. What's your track record?"
        elif character_type == "sarah_mom":
            return f"Money is tight with kids, but I know I need to invest in my health to take care of everyone else. What are the realistic options? I need something that fits our family budget."
        else:  # tom_executive
            return f"I understand ROI. If you can prove this works efficiently and gets measurable health results, I'm willing to invest significantly. What packages do you offer for executives?"
    
    # Default conversational response - stay flexible and in character
    else:
        if character_type == "mary_senior":
            return f"That's an interesting question! I appreciate your help with this. At my age, I'm learning it's never too late to make positive changes. I just want to be safe and smart about it. What would you recommend for someone like me?"
        elif character_type == "jake_athlete":
            return f"Good question! I'm always looking to learn and optimize. Performance is about details and constant improvement. What's your take on that? I'm interested in your perspective."
        elif character_type == "sarah_mom":
            return f"Oh that's a good point! With everything going on, I don't always think about things like that. Being a mom makes you realize there's always more to learn. What do you think would work best for someone in my situation?"
        else:  # tom_executive
            return f"Interesting perspective. I like to analyze all angles before making decisions. In business, you learn to ask the right questions. What data or results can you show me that would be relevant to my situation?"