#!/bin/bash

BASE_URL="http://localhost:5000/api"

echo "========================================="
echo "TEST 1: CONSULTATIVE - CAR"
echo "========================================="

# Init
INIT=$(curl -s -X POST "$BASE_URL/init" \
  -H "Content-Type: application/json" \
  -d '{"product_type":"car","force_strategy":"consultative","admin_token":"dev-admin-token"}')

SID=$(echo "$INIT" | grep -o '"session_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Session: $SID"
echo "Greeting: $(echo "$INIT" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 100)..."

# Turn 1
echo -e "\n--- T1: Vague interest ---"
T1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SID" \
  -d '{"message":"I am looking for a car"}')
echo "Stage: $(echo "$T1" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)"
echo "Bot: $(echo "$T1" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 150)..."

# Turn 2
echo -e "\n--- T2: HIGH intent ---"
T2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SID" \
  -d '{"message":"I am ready to purchase a reliable family sedan right now"}')
echo "Stage: $(echo "$T2" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)"
echo "Bot: $(echo "$T2" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 150)..."

# Turn 3 - PRICE TEST
echo -e "\n--- T3: Ask for PRICE (critical test) ---"
T3=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SID" \
  -d '{"message":"What is the price? How much will it cost?"}')
echo "Stage: $(echo "$T3" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)"
echo "Bot (should NOT waver):"
echo "$T3" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4

echo ""
echo "========================================="
echo "TEST 2: TRANSACTIONAL - LAPTOP"
echo "========================================="

INIT=$(curl -s -X POST "$BASE_URL/init" \
  -H "Content-Type: application/json" \
  -d '{"product_type":"laptop","force_strategy":"transactional","admin_token":"dev-admin-token"}')

SID=$(echo "$INIT" | grep -o '"session_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Session: $SID"
echo "Strategy: TRANSACTIONAL"

# Turn 1
echo -e "\n--- T1: Budget + needs ---"
T1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SID" \
  -d '{"message":"I need a laptop under 1500 dollars for software development"}')
echo "Stage: $(echo "$T1" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)"
echo "Bot: $(echo "$T1" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 150)..."

# Turn 2
echo -e "\n--- T2: Ask for options ---"
T2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SID" \
  -d '{"message":"What options do you have that fit my budget?"}')
echo "Stage: $(echo "$T2" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)"
echo "Bot: $(echo "$T2" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 150)..."

echo ""
echo "========================================="
echo "TEST 3: STAGE CONTROL - PHONE"
echo "========================================="

INIT=$(curl -s -X POST "$BASE_URL/init" \
  -H "Content-Type: application/json" \
  -d '{"product_type":"phone","force_strategy":"consultative","admin_token":"dev-admin-token"}')

SID=$(echo "$INIT" | grep -o '"session_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Session: $SID (CONSULTATIVE)"

# Turn 1 - Try to jump
echo -e "\n--- T1: Try to jump to pitch ---"
T1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SID" \
  -d '{"message":"Just tell me the price of your most expensive phone"}')
STAGE=$(echo "$T1" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)
echo "Stage: $STAGE (should NOT be PITCH)"
echo "Bot (should stay in intent/logical):"
echo "$T1" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4

echo -e "\n========================================="
echo "TEST COMPLETE"
echo "========================================="
