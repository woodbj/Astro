#!/usr/bin/env python3
"""
Quick test script to verify the terminal API works.
Run this after starting the Flask server.
"""
import requests
import json

SERVER_URL = "http://localhost:5000"


def test_terminal():
    """Test the terminal API endpoints."""
    print("Testing Terminal API...")
    print("=" * 50)

    # Test 1: Get namespace
    print("\n1. Testing GET /api/terminal/namespace")
    try:
        response = requests.get(f"{SERVER_URL}/api/terminal/namespace")
        print(f"   Status: {response.status_code}")
        data = response.json()
        if data.get('success'):
            print(f"   ✓ Success! Found {len(data['namespace'])} objects:")
            for name, info in data['namespace'].items():
                print(f"     - {name}: {info['type']}")
        else:
            print(f"   ✗ Failed: {data.get('error')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 2: Execute simple code
    print("\n2. Testing POST /api/terminal/execute (simple print)")
    try:
        code = "print('Hello from terminal!')"
        response = requests.post(
            f"{SERVER_URL}/api/terminal/execute",
            json={"code": code}
        )
        print(f"   Status: {response.status_code}")
        data = response.json()
        if data.get('success'):
            print(f"   ✓ Success!")
            print(f"   Output: {data['output'].strip()}")
        else:
            print(f"   ✗ Failed: {data.get('error')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 3: Interact with camera
    print("\n3. Testing camera interaction")
    try:
        code = "print(type(camera).__name__)"
        response = requests.post(
            f"{SERVER_URL}/api/terminal/execute",
            json={"code": code}
        )
        data = response.json()
        if data.get('success'):
            print(f"   ✓ Success!")
            print(f"   Camera type: {data['output'].strip()}")
        else:
            print(f"   ✗ Failed: {data.get('error')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 4: Create variable
    print("\n4. Testing variable persistence")
    try:
        code = "test_var = 42\nprint(f'Created test_var = {test_var}')"
        response = requests.post(
            f"{SERVER_URL}/api/terminal/execute",
            json={"code": code}
        )
        data = response.json()
        if data.get('success'):
            print(f"   ✓ Variable created!")
            print(f"   Output: {data['output'].strip()}")

            # Verify it persists
            code2 = "print(f'test_var still exists: {test_var}')"
            response2 = requests.post(
                f"{SERVER_URL}/api/terminal/execute",
                json={"code": code2}
            )
            data2 = response2.json()
            if data2.get('success'):
                print(f"   ✓ Variable persisted!")
                print(f"   Output: {data2['output'].strip()}")
        else:
            print(f"   ✗ Failed: {data.get('error')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 5: Error handling
    print("\n5. Testing error handling")
    try:
        code = "1/0"  # This will cause an error
        response = requests.post(
            f"{SERVER_URL}/api/terminal/execute",
            json={"code": code}
        )
        data = response.json()
        if data.get('success') and data.get('error'):
            print(f"   ✓ Error captured correctly!")
            print(f"   Error type: {data['error'][:50]}...")
        else:
            print(f"   ✗ Error not handled properly")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    print("\n" + "=" * 50)
    print("Tests complete!")


if __name__ == "__main__":
    print("Make sure your Flask server is running:")
    print("  python -m Astro.server\n")

    try:
        test_terminal()
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server!")
        print("  Make sure Flask is running on port 5000")
