#!/usr/bin/env python3
"""Simple API test to debug 500 error."""
import requests

BASE_URL = "http://localhost:8000"

# Login
print("1. Login...")
login_resp = requests.post(
    f"{BASE_URL}/login",
    data={"username": "debug_test", "password": "test1234"},
    allow_redirects=False,
)
print(f"   Status: {login_resp.status_code}")
cookies = login_resp.cookies

# Create session
print("\n2. Create session...")
session_resp = requests.post(
    f"{BASE_URL}/sessions",
    json={"scenario_id": 1},
    cookies=cookies,
)
print(f"   Status: {session_resp.status_code}")
if session_resp.status_code in [200, 201]:
    session_data = session_resp.json()
    session_id = session_data["id"]
    print(f"   Session ID: {session_id}")

    # Send message - This is where the error occurs
    print("\n3. Send message...")
    msg_resp = requests.post(
        f"{BASE_URL}/sessions/{session_id}/messages",
        json={"content": "Test message"},
        cookies=cookies,
    )
    print(f"   Status: {msg_resp.status_code}")
    print(f"   Response: {msg_resp.text}")
else:
    print(f"   Failed to create session: {session_resp.text}")
