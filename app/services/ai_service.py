"""
AI service for the Speech-To-Plan Reminder application.
"""

import json
import torch
import whisper
import logging
import google.generativeai as genai
import numpy as np
import re
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from app.config import settings
from app.services.todo_service import get_all_todos, create_todo, delete_todo_by_id, search_todos

# Configure logging
logger = logging.getLogger(__name__)

# Load Whisper model
logger.info(f"Loading Whisper model on {settings.DEVICE}...")
model = whisper.load_model(settings.WHISPER_MODEL)
model.to(settings.DEVICE)

# Configure Gemini
api_key = settings.GOOGLE_API_KEY
logger.info(f"Using Gemini API key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
genai.configure(api_key=api_key)
gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)

# Initialize chat
chat = gemini_model.start_chat(history=[
    {"role": "user", "parts": [settings.SYSTEM_PROMPT]},
])

def transcribe_with_whisper(audio: np.ndarray) -> str:
    """
    Transcribe audio using Whisper.
    
    Args:
        audio: Audio data as numpy array
        
    Returns:
        Transcribed text
    """
    try:
        # Transcribe audio
        result = model.transcribe(
            audio,
            fp16=torch.cuda.is_available()
        )
        
        return result["text"].strip()
    except Exception as e:
        logger.error(f"Error transcribing with Whisper: {str(e)}")
        raise

def transcribe_with_gemini(audio_path: str) -> str:
    """
    Transcribe audio using Gemini.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Transcribed text
    """
    try:
        # Transcribe audio
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        
        response = gemini_model.generate_content(
            ["Transcribe this audio accurately", audio_data]
        )
        
        return response.text
    except Exception as e:
        logger.error(f"Error transcribing with Gemini: {str(e)}")
        raise

def clean_json_response(response_text: str) -> str:
    """
    Clean the JSON response from Gemini to extract the actual message.
    
    Args:
        response_text: Raw response text from Gemini
        
    Returns:
        Cleaned response text
    """
    # Check if the response is already a clean string without JSON markers
    if not any(marker in response_text for marker in ['{', '}', '```', '`', '"type":', '"function":']):
        return response_text
    
    # First try to parse as JSON directly
    try:
        response_json = json.loads(response_text)
        # Handle different response types
        if isinstance(response_json, dict):
            if "output" in response_json:
                return response_json["output"]
            elif response_json.get("type") == "action":
                # Process the action directly here instead of returning JSON
                function_name = response_json.get("function", "")
                function_input = response_json.get("input", "")
                if function_name == "getAllTodos":
                    return "Let me fetch your tasks for you."
                elif function_name == "createTodo":
                    title = function_input
                    if isinstance(function_input, dict):
                        title = function_input.get("title", "")
                    return f"I'll add '{title}' to your tasks."
                elif function_name == "searchTodo":
                    query = function_input
                    if isinstance(function_input, dict):
                        query = function_input.get("title", "")
                    return f"Searching for tasks with '{query}'."
                elif function_name == "deleteTodoById":
                    return "I'll delete that task for you."
                else:
                    return f"I'll help you with that {function_name} action."
        return response_text
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks or quotes
    json_pattern = r'```(?:json)?\s*({.*?})\s*```|`({.*?})`|"({.*?})"'
    matches = re.findall(json_pattern, response_text, re.DOTALL)
    
    for match_groups in matches:
        for match in match_groups:
            if match:
                try:
                    json_obj = json.loads(match)
                    if isinstance(json_obj, dict):
                        if "output" in json_obj:
                            return json_obj["output"]
                        elif json_obj.get("type") == "action":
                            # Process the action
                            function_name = json_obj.get("function", "")
                            function_input = json_obj.get("input", "")
                            if function_name == "getAllTodos":
                                return "Let me fetch your tasks for you."
                            elif function_name == "createTodo":
                                title = function_input
                                if isinstance(function_input, dict):
                                    title = function_input.get("title", "")
                                return f"I'll add '{title}' to your tasks."
                            elif function_name == "searchTodo":
                                query = function_input
                                if isinstance(function_input, dict):
                                    query = function_input.get("title", "")
                                return f"Searching for tasks with '{query}'."
                            elif function_name == "deleteTodoById":
                                return "I'll delete that task for you."
                            else:
                                return f"I'll help you with that {function_name} action."
                except:
                    continue
    
    # Try to extract action type if present
    action_pattern = r'"type"\s*:\s*"action".*?"function"\s*:\s*"(\w+)"'
    action_match = re.search(action_pattern, response_text)
    if action_match:
        function_name = action_match.group(1)
        if function_name == "getAllTodos":
            return "Let me fetch your tasks for you."
        elif function_name == "createTodo":
            return "I'll add that to your tasks."
        elif function_name == "searchTodo":
            return "Searching for your tasks."
        elif function_name == "deleteTodoById":
            return "I'll delete that task for you."
        else:
            return f"I'll help you with that {function_name} action."
    
    # Try to extract just the output field if present
    output_pattern = r'"output"\s*:\s*"(.*?)"'
    output_match = re.search(output_pattern, response_text)
    if output_match:
        return output_match.group(1)
    
    # If all else fails, remove JSON formatting characters
    cleaned_text = re.sub(r'```json|```|\{|\}|"type":|"output":|"function":|"input":', '', response_text)
    cleaned_text = re.sub(r'[:,"]', '', cleaned_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    return cleaned_text or response_text

def process_chat_message(message: str, db: Session) -> str:
    """
    Process a chat message using Gemini.
    
    Args:
        message: User message
        db: Database session
        
    Returns:
        Response message
    """
    try:
        # Check for direct task creation commands
        if any(phrase in message.lower() for phrase in ["i have a", "i have", "add a", "add", "create a", "create", "schedule a", "schedule", "remind me"]):
            # Extract task details
            task_title = message
            due_date = None
            
            # Look for date indicators
            if "tomorrow" in message.lower():
                tomorrow = datetime.now() + timedelta(days=1)
                due_date = tomorrow.strftime("%Y-%m-%d")
                task_title = message.replace("tomorrow", "").strip()
                
                # Handle different prefixes
                if task_title.lower().startswith("i have a"):
                    task_title = task_title[8:].strip()
                elif task_title.lower().startswith("i have"):
                    task_title = task_title[6:].strip()
                elif task_title.lower().startswith("add a"):
                    task_title = task_title[5:].strip()
                elif task_title.lower().startswith("add"):
                    task_title = task_title[3:].strip()
                elif task_title.lower().startswith("create a"):
                    task_title = task_title[8:].strip()
                elif task_title.lower().startswith("create"):
                    task_title = task_title[6:].strip()
                elif task_title.lower().startswith("schedule a"):
                    task_title = task_title[10:].strip()
                elif task_title.lower().startswith("schedule"):
                    task_title = task_title[8:].strip()
                
                # Capitalize the first letter of the task
                if task_title:
                    task_title = task_title[0].upper() + task_title[1:] if len(task_title) > 1 else task_title.upper()
            
            # Create the task directly
            logger.info(f"Creating task directly: '{task_title}', due: {due_date}")
            todo = create_todo(db, task_title, due_date)
            logger.info(f"Created task directly: {task_title}, due: {due_date}, id: {todo.id}")
            return f"I'll add '{task_title}' to your tasks."
        
        # Send message to Gemini
        response = chat.send_message(message)
        response_text = response.text
        
        # Check if the message is asking for todos
        if any(keyword in message.lower() for keyword in ["show", "list", "get", "view", "display", "my tasks", "my todos", "all tasks", "all todos"]):
            # Get all todos
            todos = get_all_todos(db)
            
            # Format todos for display
            if todos:
                formatted_todos = "\n".join([f"• {todo.todo}" + (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "") for todo in todos])
                return f"Here are your tasks:\n{formatted_todos}"
            else:
                return "You don't have any tasks yet. Try adding some!"
        
        # Clean and parse the response
        cleaned_response = clean_json_response(response_text)
        
        # Try to parse response as JSON
        try:
            response_json = json.loads(response_text)
            
            # Handle action responses
            if response_json.get("type") == "action":
                function_name = response_json.get("function")
                function_input = response_json.get("input")
                
                if function_name == "getAllTodos":
                    # Get all todos
                    todos = get_all_todos(db)
                    
                    # Format todos for response
                    if todos:
                        formatted_todos = "\n".join([f"• {todo.todo}" + (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "") for todo in todos])
                        return f"Here are your tasks:\n{formatted_todos}"
                    else:
                        return "You don't have any tasks yet. Try adding some!"
                
                elif function_name == "createTodo":
                    # Create todo
                    title = function_input
                    due_date = None
                    
                    # Check if input is a dictionary with title and due_date
                    if isinstance(function_input, dict):
                        title = function_input.get("title", "")
                        due_date = function_input.get("due_date")
                    
                    # Create todo
                    logger.info(f"Creating todo from AI response: {title}, due: {due_date}")
                    todo = create_todo(db, title, due_date)
                    
                    return f"Added '{title}' to your tasks!"
                
                elif function_name == "searchTodo":
                    # Search todos
                    query = function_input
                    if isinstance(function_input, dict):
                        query = function_input.get("title", "")
                    
                    todos = search_todos(db, query)
                    
                    # Format todos for response
                    if todos:
                        formatted_todos = "\n".join([f"• {todo.todo}" + (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "") for todo in todos])
                        return f"Found {len(todos)} tasks matching '{query}':\n{formatted_todos}"
                    else:
                        return f"No tasks found matching '{query}'."
                
                elif function_name == "deleteTodoById":
                    # Delete todo by ID
                    todo_id = function_input
                    
                    # Delete todo
                    success = delete_todo_by_id(db, todo_id)
                    
                    return "Task deleted successfully!" if success else "Task not found."
                
                # Default response for unknown function
                return f"Unsupported function: {function_name}"
            
            # Handle output responses
            elif response_json.get("type") == "output":
                return response_json.get("output", "I didn't understand that")
            
            # Default response for unknown response type
            return cleaned_response
        
        except json.JSONDecodeError:
            # If response is not valid JSON, return the cleaned text
            return cleaned_response
    
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return f"Sorry, I encountered an error: {str(e)}"
