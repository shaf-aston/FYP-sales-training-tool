#!/usr/bin/env python3
"""Developer smoke test for full prospect route flow."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

import pytest

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ['FLASK_ENV'] = 'testing'
pytestmark = pytest.mark.smoke

if os.getenv("RUN_SMOKE_TESTS") != "1":
    pytest.skip(
        "Set RUN_SMOKE_TESTS=1 to run developer conversation smoke tests.",
        allow_module_level=True,
    )


def _run_prospect_routes():
    """Test prospect routes with Flask test client."""
    print("=" * 60)
    print("PROSPECT ROUTES TEST")
    print("=" * 60)

    # Import and set up Flask app
    print("\n[*] Setting up Flask app...")
    from backend.app import app

    app.config['TESTING'] = True
    client = app.test_client()

    print("[OK] Flask app configured")

    # Test 1: Initialize prospect session
    print("\n[*] Test 1: Initialize prospect session...")
    response = client.post(
        '/api/prospect/init',
        json={
            'difficulty': 'medium',
            'product_type': 'default',
        },
        content_type='application/json'
    )

    print(f"  Status: {response.status_code}")
    data = response.get_json()

    if response.status_code != 200:
        print(f"[FAIL] Expected 200, got {response.status_code}")
        print(f"  Response: {data}")
        assert False, f"Expected 200, got {response.status_code}: {data}"

    if not data.get('success'):
        print("[FAIL] Response doesn't have 'success': True")
        print(f"  Response: {data}")
        assert False, f"Response missing success=True: {data}"

    session_id = data.get('session_id')
    if not session_id:
        print("[FAIL] No session_id returned")
        print(f"  Response: {data}")
        assert False, f"No session_id returned: {data}"

    print(f"[OK] Session created: {session_id}")
    print(f"  Persona: {data.get('persona', {}).get('name', 'Unknown')}")
    print(f"  Opening message: {data.get('message', '')[:60]}...")

    # Test 2: Get current state
    print("\n[*] Test 2: Get prospect state...")
    response = client.get(
        '/api/prospect/state',
        headers={'X-Session-ID': session_id}
    )

    print(f"  Status: {response.status_code}")
    data = response.get_json()

    if response.status_code != 200:
        print(f"[FAIL] Expected 200, got {response.status_code}")
        print(f"  Response: {data}")
        assert False, f"Expected 200, got {response.status_code}: {data}"

    if not data.get('success'):
        print("[FAIL] Response doesn't have 'success': True")
        assert False, f"Response missing success=True: {data}"

    print("[OK] State retrieved")
    print(f"  Conversation history: {len(data.get('conversation_history', []))} messages")
    print(f"  Prospect readiness: {data.get('state', {}).get('readiness', 'N/A')}")

    # Test 3: Send chat message
    print("\n[*] Test 3: Send prospect a chat message...")
    response = client.post(
        '/api/prospect/chat',
        json={'message': 'What are your main concerns about adopting a new solution?'},
        headers={'X-Session-ID': session_id},
        content_type='application/json'
    )

    print(f"  Status: {response.status_code}")
    data = response.get_json()

    if response.status_code != 200:
        print(f"[FAIL] Expected 200, got {response.status_code}")
        print(f"  Response: {data}")
        assert False, f"Expected 200, got {response.status_code}: {data}"

    if not data.get('success'):
        print("[FAIL] Response doesn't have 'success': True")
        print(f"  Response: {data}")
        assert False, f"Response missing success=True: {data}"

    prospect_message = data.get('message', '')
    if prospect_message:
        print("[OK] Prospect responded")
        print(f"  Message: {prospect_message[:80]}...")
    else:
        print("[WARN] Prospect returned an empty message, but the route contract succeeded")

    print(f"  Ended: {data.get('ended', False)}")
    print(f"  Outcome: {data.get('outcome', 'N/A')}")

    # Test 4: Get evaluation
    print("\n[*] Test 4: Get session evaluation...")
    response = client.post(
        '/api/prospect/evaluate',
        headers={'X-Session-ID': session_id}
    )

    print(f"  Status: {response.status_code}")
    data = response.get_json()

    if response.status_code != 200:
        print(f"[FAIL] Expected 200, got {response.status_code}")
        print(f"  Response: {data}")
        assert False, f"Expected 200, got {response.status_code}: {data}"

    if not data.get('success'):
        print("[FAIL] Response doesn't have 'success': True")
        print(f"  Response: {data}")
        assert False, f"Response missing success=True: {data}"

    print("[OK] Evaluation generated")
    print(f"  Overall score: {data.get('overall_score', 'N/A')}")
    print(f"  Grade: {data.get('grade', 'N/A')}")
    print(f"  Outcome: {data.get('outcome', 'N/A')}")

    # Check evaluation structure
    criteria_scores = data.get('criteria_scores', {})
    if criteria_scores:
        print("  Criteria scores:")
        for name, info in criteria_scores.items():
            score = info.get('score', 'N/A')
            feedback = info.get('feedback', '')[:40]
            print(f"    - {name}: {score} ({feedback}...)")

    print("\n[OK] All tests passed!")
    return True


def test_prospect_routes():
    """Pytest entrypoint for the prospect route smoke test."""
    assert _run_prospect_routes() is True


if __name__ == "__main__":
    try:
        success = _run_prospect_routes()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
