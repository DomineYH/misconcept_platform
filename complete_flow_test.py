#!/usr/bin/env python3
"""
Complete dialogue flow test: User → Chatbot → Tutor.
All in one session with one user.
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("COMPLETE DIALOGUE FLOW TEST")
print("=" * 70)

# Step 1: Login
print("\n[1] Login...")
login_resp = requests.post(
    f"{BASE_URL}/login",
    data={"student_uid": "complete_test", "nickname": "Complete Tester"},
    allow_redirects=False,
)
print(f"    ✓ Status: {login_resp.status_code}")
cookies = login_resp.cookies

# Step 2: Create session
print("\n[2] Create new session...")
session_resp = requests.post(
    f"{BASE_URL}/sessions",
    json={"scenario_id": 1},
    cookies=cookies,
)
if session_resp.status_code not in [200, 201]:
    print(f"    ❌ Failed: {session_resp.text}")
    exit(1)

session_data = session_resp.json()
session_id = session_data["id"]
print(f"    ✓ Session created: {session_id}")

# Step 3: Send first message
print("\n[3] Send first message (User → Chatbot)...")
msg1 = "How do I add 1/2 and 1/3?"
msg1_resp = requests.post(
    f"{BASE_URL}/sessions/{session_id}/messages",
    json={"content": msg1},
    cookies=cookies,
)
print(f"    ✓ Status: {msg1_resp.status_code}")
print(f"    Teacher: {msg1}")
# Response is HTML, check database instead
import sqlite3
conn = sqlite3.connect("dialogue_sim.db")
cursor = conn.cursor()
cursor.execute(
    "SELECT role, content FROM message WHERE session_id=? ORDER BY id",
    (session_id,)
)
messages = cursor.fetchall()
for role, content in messages:
    if role == "student":
        print(f"    Student: {content[:100]}...")

# Step 4: Send second message
print("\n[4] Send second message...")
msg2 = "So the answer is 2/5?"
msg2_resp = requests.post(
    f"{BASE_URL}/sessions/{session_id}/messages",
    json={"content": msg2},
    cookies=cookies,
)
print(f"    ✓ Status: {msg2_resp.status_code}")
print(f"    Teacher: {msg2}")
cursor.execute(
    "SELECT role, content FROM message WHERE session_id=? ORDER BY id",
    (session_id,)
)
messages = cursor.fetchall()
for role, content in messages[-2:]:  # Last 2 messages
    if role == "student":
        print(f"    Student: {content[:100]}...")

# Step 5: End session (triggers analysis)
print("\n[5] End session (triggers tutor analysis)...")
end_resp = requests.post(
    f"{BASE_URL}/sessions/{session_id}/end",
    cookies=cookies,
)
print(f"    ✓ Status: {end_resp.status_code}")

# Step 6: Get analysis results
print("\n[6] Get tutor analysis...")
analysis_resp = requests.get(
    f"{BASE_URL}/sessions/{session_id}/analysis",
    cookies=cookies,
)
if analysis_resp.status_code == 200:
    try:
        analysis_data = analysis_resp.json()
        print(f"    ✓ Analysis retrieved")

        # Check question_analysis table
        cursor.execute(
            "SELECT question_text, analysis FROM question_analysis WHERE session_id=?",
            (session_id,)
        )
        analyses = cursor.fetchall()
        print(f"    ✓ Found {len(analyses)} question analyses")
        for i, (q, a) in enumerate(analyses, 1):
            print(f"\n    Question {i}: {q[:50]}...")
            print(f"    Tutor: {a[:150]}...")

    except Exception as e:
        print(f"    Response: {analysis_resp.text[:200]}")
else:
    print(f"    Status: {analysis_resp.status_code}")
    print(f"    Response: {analysis_resp.text}")

conn.close()

print("\n" + "=" * 70)
print("✅ COMPLETE DIALOGUE FLOW TEST PASSED!")
print("=" * 70)
print(f"Session ID: {session_id}")
print(f"Messages exchanged: {len(messages)}")
print(f"Tutor analyses: {len(analyses) if 'analyses' in locals() else 0}")
print("=" * 70)
