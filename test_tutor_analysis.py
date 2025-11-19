#!/usr/bin/env python3
"""Test tutor analysis functionality."""
import requests

BASE_URL = "http://localhost:8000"

# Login
print("1. Login...")
login_resp = requests.post(
    f"{BASE_URL}/login",
    data={"student_uid": "tutor_test", "nickname": "Tutor Tester"},
    allow_redirects=False,
)
cookies = login_resp.cookies

# Get existing session with messages
session_id = 20  # From previous test

# First, need to end the session to trigger analysis
print(f"\n2. Ending session {session_id} to trigger analysis...")
end_resp = requests.post(
    f"{BASE_URL}/sessions/{session_id}/end",
    cookies=cookies,
)
print(f"   End session status: {end_resp.status_code}")

# Test tutor analysis
print(f"\n3. Getting tutor analysis for session {session_id}...")
analysis_resp = requests.get(
    f"{BASE_URL}/sessions/{session_id}/analysis",
    cookies=cookies,
)

print(f"   Status: {analysis_resp.status_code}")
print(f"   Content-Type: {analysis_resp.headers.get('content-type')}")

if analysis_resp.status_code == 200:
    try:
        data = analysis_resp.json()
        print(f"\n✓ Tutor Analysis Response:")
        print(f"   Analysis: {data.get('analysis', 'N/A')[:200]}...")
        print(f"\n✅ Tutor bot is working!")
    except:
        print(f"   Response: {analysis_resp.text[:300]}")
else:
    print(f"   ❌ Failed: {analysis_resp.text}")
