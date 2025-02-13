import requests
import json

def test_add_task():
    url = "http://localhost:8000/chat"
    headers = {"Content-Type": "application/json"}
    
    # First, let's check existing todos
    print("\nChecking existing todos...")
    response = requests.get("http://localhost:8000/todos")
    print("Existing todos:", response.json())
    
    print("\nAdding new task...")
    data = {
        "text": "Add task: Complete project documentation (Due: 2025-02-20)"
    }
    
    response = requests.post(url, headers=headers, json=data)
    print("Response status:", response.status_code)
    print("Response content:", response.json())
    
    print("\nChecking updated todos...")
    response = requests.get("http://localhost:8000/todos")
    print("Updated todos:", response.json())

if __name__ == "__main__":
    test_add_task()
