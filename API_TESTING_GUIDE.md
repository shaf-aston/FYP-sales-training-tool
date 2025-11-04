# 🚀 API Testing Guide - Sales Roleplay Chatbot

## Quick Start - Test All Features via curl

### 🔧 **Server Setup**
```bash
# Start the server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Verify server is running
curl -X GET "http://localhost:8000/api/test/system/health"
```

## 🎯 **Core API Testing Commands**

### **1. General Chat (Renamed from Direct Chat)**
```bash
# Test general conversation
curl -X POST "http://localhost:8000/api/test/chat/general" \
     -H "Content-Type: application/json" \
     -d '{"message": "Tell me about effective sales techniques"}'

# Test with user ID
curl -X POST "http://localhost:8000/api/test/chat/general" \
     -H "Content-Type: application/json" \
     -d '{"message": "How do I handle price objections?", "user_id": "my_test_user"}'
```

### **2. Persona Chat Testing**
```bash
# Chat with Mary (Cautious Retiree)
curl -X POST "http://localhost:8000/api/test/chat/persona" \
     -H "Content-Type: application/json" \
     -d '{"message": "I have a retirement savings product for you", "persona": "mary"}'

# Chat with Jake (Skeptical Executive)
curl -X POST "http://localhost:8000/api/test/chat/persona" \
     -H "Content-Type: application/json" \
     -d '{"message": "This could benefit your business", "persona": "jake"}'

# Chat with Sarah (Budget-conscious Student)
curl -X POST "http://localhost:8000/api/test/chat/persona" \
     -H "Content-Type: application/json" \
     -d '{"message": "I have something affordable for students", "persona": "sarah"}'

# Chat with David (Busy Doctor)
curl -X POST "http://localhost:8000/api/test/chat/persona" \
     -H "Content-Type: application/json" \
     -d '{"message": "Quick question about medical insurance", "persona": "david"}'
```

### **3. Training Session Management**
```bash
# Start training session
curl -X POST "http://localhost:8000/api/test/training/start" \
     -H "Content-Type: application/json" \
     -d '{"persona_name": "mary", "user_id": "test_user", "session_duration_minutes": 10}'

# Send message in training (use session_id from previous response)
curl -X POST "http://localhost:8000/api/test/training/message/test_session_20251031_143000" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hi Mary, I understand you are looking for retirement planning options"}'
```

### **4. Feedback and Analysis**
```bash
# Analyze completed session
curl -X POST "http://localhost:8000/api/test/feedback/analyze" \
     -H "Content-Type: application/json" \
     -d '{"session_id": "test_session_20251031_143000", "user_id": "test_user", "success_rating": 8}'
```

### **5. Voice Simulation Testing**
```bash
# Test voice functionality (simulated)
curl -X POST "http://localhost:8000/api/test/voice/simulate" \
     -F "text=Hello, I would like to discuss your insurance products" \
     -F "persona=jake"
```

### **6. System Health and Monitoring**
```bash
# Comprehensive health check
curl -X GET "http://localhost:8000/api/test/system/health"

# List all available endpoints
curl -X GET "http://localhost:8000/api/test/system/endpoints"

# Run full test suite
curl -X POST "http://localhost:8000/api/test/run/full-test-suite"
```

## 🎭 **Persona Quick Reference**

| Persona | Character | Best Test Messages |
|---------|-----------|-------------------|
| **mary** | Cautious Retiree | "I have retirement planning advice", "This could help your fixed income" |
| **jake** | Skeptical Executive | "This will boost your ROI", "Quick business opportunity" |
| **sarah** | Budget Student | "Student discount available", "This fits your budget" |
| **david** | Busy Doctor | "Medical professional rates", "Just 2 minutes of your time" |

## 🔄 **Complete Testing Workflow**

### **Scenario 1: Full Sales Training Session**
```bash
# 1. Start training
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/test/training/start" \
           -H "Content-Type: application/json" \
           -d '{"persona_name": "mary", "user_id": "tester"}')

# 2. Extract session ID (requires jq)
SESSION_ID=$(echo $RESPONSE | jq -r '.response.session_id')

# 3. Practice conversation
curl -X POST "http://localhost:8000/api/test/training/message/$SESSION_ID" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hi Mary, I noticed you might be interested in secure retirement investments"}'

# 4. Get feedback
curl -X POST "http://localhost:8000/api/test/feedback/analyze" \
     -H "Content-Type: application/json" \
     -d "{\"session_id\": \"$SESSION_ID\", \"success_rating\": 7}"
```

### **Scenario 2: Multi-Persona Testing**
```bash
# Test all personas quickly
for persona in mary jake sarah david; do
  echo "Testing $persona..."
  curl -s -X POST "http://localhost:8000/api/test/chat/persona" \
       -H "Content-Type: application/json" \
       -d "{\"message\": \"Hello, I have something that might interest you\", \"persona\": \"$persona\"}" | jq '.response.persona_response'
done
```

## 🚀 **Performance Testing**

### **Load Testing**
```bash
# Test response times (requires Apache Bench - ab)
ab -n 100 -c 10 -T 'application/json' -p test_data.json http://localhost:8000/api/test/chat/general

# Where test_data.json contains:
# {"message": "Hello"}
```

### **Concurrent Testing**
```bash
# Run multiple requests in parallel
for i in {1..5}; do
  curl -X POST "http://localhost:8000/api/test/chat/general" \
       -H "Content-Type: application/json" \
       -d '{"message": "Concurrent test '$i'"}' &
done
wait
```

## 📊 **Response Analysis**

All test endpoints return standardized responses:
```json
{
  "success": true,
  "test_type": "endpoint_name",
  "request": { /* your request data */ },
  "response": { /* AI/system response */ },
  "timestamp": "2025-10-31T14:30:00",
  "processing_time": "0.4s"
}
```

## 🐛 **Troubleshooting**

### **Common Issues**
```bash
# Server not responding
curl -X GET "http://localhost:8000/docs"  # Check if server is up

# Model not loaded
curl -X GET "http://localhost:8000/api/test/system/health"  # Check model status

# Invalid persona
curl -X GET "http://localhost:8000/api/test/system/endpoints"  # List valid options
```

### **Debug Mode**
```bash
# Enable verbose logging and restart server
export LOG_LEVEL=DEBUG
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

## 🎯 **Future Testing Automation**

Save this as `test_suite.sh`:
```bash
#!/bin/bash
echo "🧪 Running AI Sales Chatbot Test Suite..."

# Run full test suite
curl -s -X POST "http://localhost:8000/api/test/run/full-test-suite" | jq '.'

echo "✅ Test suite completed!"
```

Make executable and run:
```bash
chmod +x test_suite.sh
./test_suite.sh
```