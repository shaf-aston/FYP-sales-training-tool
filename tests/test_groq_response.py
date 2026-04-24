#!/usr/bin/env python3
"""Developer smoke test for response parsing and live prospect chat behaviour."""

import sys
import os
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ['FLASK_ENV'] = 'testing'
pytestmark = pytest.mark.smoke

if os.getenv("RUN_SMOKE_TESTS") != "1":
    pytest.skip(
        "Set RUN_SMOKE_TESTS=1 to run developer conversation smoke tests.",
        allow_module_level=True,
    )


def test():
    """Test with mocked response to see if it's a parsing issue."""
    print("Testing response parsing...")

    # Import after path setup
    # Test 1: What the code expects
    body = {
        "choices": [
            {
                "message": {
                    "content": "This is the response"
                }
            }
        ]
    }

    choices = body.get("choices") or [{}]
    content = choices[0].get("message", {}).get("content", "").strip()

    print(f"Expected response: '{content}'")

    # Test 2: What if choices is empty
    body = {"choices": []}
    choices = body.get("choices") or [{}]
    content = choices[0].get("message", {}).get("content", "").strip()
    print(f"Empty choices: '{content}'")

    # Test 3: What if message is empty
    body = {"choices": [{"message": {}}]}
    choices = body.get("choices") or [{}]
    content = choices[0].get("message", {}).get("content", "").strip()
    print(f"Empty message: '{content}'")

    # Test 4: What if there's no content field
    body = {"choices": [{"message": {"role": "assistant"}}]}
    choices = body.get("choices") or [{}]
    content = choices[0].get("message", {}).get("content", "").strip()
    print(f"No content field: '{content}'")

    # Now test with the actual Groq provider by importing the app
    print("\n\nTesting Flask app...")
    from backend.app import app

    app.config['TESTING'] = True
    client = app.test_client()

    # Initialize a prospect session
    response = client.post(
        '/api/prospect/init',
        json={
            'difficulty': 'medium',
            'product_type': 'default',
        },
        content_type='application/json'
    )

    if response.status_code != 200:
        print(f"Failed to init: {response.status_code}")
        print(response.get_json())
        return

    session_id = response.get_json()['session_id']
    print(f"Session created: {session_id}")

    # Try a chat
    response = client.post(
        '/api/prospect/chat',
        json={'message': 'What can you help me with today?'},
        headers={'X-Session-ID': session_id},
        content_type='application/json'
    )

    data = response.get_json()
    print("\nChat response:")
    print(f"  Status: {response.status_code}")
    print(f"  Message: '{data.get('message', '')}'")
    print(f"  Message length: {len(data.get('message', ''))}")
    print(f"  Error in response: {data.get('error', 'None')}")
    print(f"  Full response: {data}")


if __name__ == "__main__":
    test()
