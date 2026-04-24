#!/usr/bin/env python3
"""Developer smoke test to inspect full prospect responses."""

import sys
import os
import json
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
    print("DETAILED PROSPECT TEST")
    print("=" * 80)

    from backend.app import app

    app.config['TESTING'] = True
    client = app.test_client()

    # Test 1: Initialize
    print("\n[1] Initialize session...")
    response = client.post(
        '/api/prospect/init',
        json={'difficulty': 'medium', 'product_type': 'default'},
        content_type='application/json'
    )

    data = response.get_json()
    session_id = data.get('session_id')
    opening_msg = data.get('message', '')

    print(f"Status: {response.status_code}")
    print(f"Session ID: {session_id}")
    print(f"Opening message: '{opening_msg}'")
    print(f"Opening message length: {len(opening_msg)}")
    print("Full init response:")
    print(json.dumps(data, indent=2))

    if not opening_msg:
        print("\n[ERROR] Opening message is empty!")

    # Test 2: Chat
    print("\n[2] Send chat message...")
    response = client.post(
        '/api/prospect/chat',
        json={'message': 'What are your main concerns?'},
        headers={'X-Session-ID': session_id},
        content_type='application/json'
    )

    data = response.get_json()
    chat_msg = data.get('message', '')

    print(f"Status: {response.status_code}")
    print(f"Chat message: '{chat_msg}'")
    print(f"Chat message length: {len(chat_msg)}")
    print(f"Provider: {data.get('provider')}")
    print(f"Model: {data.get('model')}")
    print(f"Latency: {data.get('latency_ms')}ms")
    print("Full chat response:")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    test()
