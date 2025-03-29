"""
Test script to verify the restructured application is working correctly.
"""

import requests
import json

def test_server_connection():
    """Test basic connection to the server."""
    try:
        response = requests.get("http://localhost:8000/")
        print(f"Server connection: {'Success' if response.status_code == 200 else 'Failed'}")
        print(f"Status code: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error connecting to server: {str(e)}")
        return False

def test_todos_endpoint():
    """Test the todos endpoint."""
    try:
        response = requests.get("http://localhost:8000/todos/")
        print(f"Todos endpoint: {'Success' if response.status_code == 200 else 'Failed'}")
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            todos = response.json()
            print(f"Found {len(todos)} todos")
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing todos endpoint: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing restructured application...")
    server_ok = test_server_connection()
    if server_ok:
        test_todos_endpoint()
    print("Testing complete.")
