#!/usr/bin/env python3
"""
Manual test script for full dialogue flow.
Tests: User → Chatbot → Tutor interaction.

Usage:
    python manual_dialogue_test.py
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"


async def test_full_dialogue_flow():
    """Test complete dialogue flow with real server."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        print("=" * 60)
        print("Testing Full Dialogue Flow: User-Chatbot-Tutor")
        print("=" * 60)

        # Step 1: Login
        print("\n[1] Logging in...")
        login_response = await client.post(
            "/login",
            data={"username": "test_manual", "password": "test1234"},
            follow_redirects=False,
        )
        print(f"    Status: {login_response.status_code}")

        # Extract cookies for subsequent requests
        cookies = login_response.cookies

        # Step 2: Get available scenarios
        print("\n[2] Getting scenarios...")
        scenarios_response = await client.get(
            "/scenarios", cookies=cookies, follow_redirects=True
        )
        # Extract scenario ID from HTML or use known ID
        scenario_id = 1  # Using known scenario ID
        print(f"    Using scenario ID: {scenario_id}")

        # Step 3: Create session
        print("\n[3] Creating new session...")
        session_response = await client.post(
            "/sessions",
            json={"scenario_id": scenario_id},
            cookies=cookies,
        )
        if session_response.status_code not in [200, 201]:
            print(f"    ❌ Failed: {session_response.status_code}")
            print(f"    Response: {session_response.text[:200]}")
            return

        session_data = session_response.json()
        session_id = session_data["id"]
        print(f"    ✓ Session created: {session_id}")

        # Step 4: Send first message
        print("\n[4] User sends message...")
        user_message = "How do I add 1/2 and 1/3?"
        print(f"    Sending: {user_message}")
        try:
            msg_response = await client.post(
                f"/sessions/{session_id}/messages",
                json={"content": user_message},
                cookies=cookies,
            )
            print(f"    Response status: {msg_response.status_code}")
            if msg_response.status_code != 200:
                print(f"    ❌ Failed: {msg_response.status_code}")
                print(f"    Response body: {msg_response.text}")
                print(f"    Headers: {msg_response.headers}")
                return

            # Check response content
            print(f"    Response content-type: {msg_response.headers.get('content-type')}")
            print(f"    Response length: {len(msg_response.text)}")
            if msg_response.headers.get('content-type', '').startswith('application/json'):
                msg_data = msg_response.json()
                chatbot_response = msg_data.get("chatbot_response", "")
            else:
                print(f"    ❌ Non-JSON response: {msg_response.text[:200]}")
                return
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return
        print(f"    User: {user_message}")
        print(f"    Chatbot: {chatbot_response[:150]}...")

        # Step 5: Get tutor analysis
        print("\n[5] Getting tutor analysis...")
        analysis_response = await client.post(
            f"/sessions/{session_id}/analyze", cookies=cookies
        )
        if analysis_response.status_code != 200:
            print(f"    ❌ Failed: {analysis_response.status_code}")
            print(f"    Response: {analysis_response.text[:200]}")
            return

        analysis_data = analysis_response.json()
        tutor_feedback = analysis_data.get("analysis", "")
        print(f"    Tutor: {tutor_feedback[:150]}...")

        # Step 6: Continue conversation
        print("\n[6] Continuing conversation...")
        followup = "So I just add the tops and bottoms together?"
        followup_response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"content": followup},
            cookies=cookies,
        )
        if followup_response.status_code != 200:
            print(f"    ❌ Failed: {followup_response.status_code}")
            return

        followup_data = followup_response.json()
        followup_chatbot = followup_data.get("chatbot_response", "")
        print(f"    User: {followup}")
        print(f"    Chatbot: {followup_chatbot[:150]}...")

        # Step 7: Second tutor analysis
        print("\n[7] Getting second tutor analysis...")
        second_analysis = await client.post(
            f"/sessions/{session_id}/analyze", cookies=cookies
        )
        if second_analysis.status_code != 200:
            print(f"    ❌ Failed: {second_analysis.status_code}")
            return

        second_data = second_analysis.json()
        second_tutor = second_data.get("analysis", "")
        print(f"    Tutor: {second_tutor[:150]}...")

        print("\n" + "=" * 60)
        print("✅ Full dialogue flow test PASSED!")
        print(f"   Session ID: {session_id}")
        print(f"   Conversation turns: 2")
        print(f"   Tutor analyses: 2")
        print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_full_dialogue_flow())
    except httpx.ConnectError:
        print("\n❌ Server not running!")
        print("   Start server with: uvicorn src.main:app --reload --port 8000")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
