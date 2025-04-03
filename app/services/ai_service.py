import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

import google.generativeai as genai
from sqlalchemy.orm import Session

from app.services.todo_service import create_todo, get_all_todos, delete_todo_by_id, check_duplicate_task, search_todos
from app.config import GOOGLE_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
if GOOGLE_API_KEY:
    logger.info(f"Using Gemini API key: {GOOGLE_API_KEY[:5]}...{GOOGLE_API_KEY[-5:] if GOOGLE_API_KEY else 'None'}")
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL)
else:
    logger.error("No Gemini API key found")

# Initialize chat
chat = gemini_model.start_chat(history=[
    {"role": "user", "parts": [SYSTEM_PROMPT]},
])

def clean_json_response(response_text: str) -> Dict[str, Any]:
    """Clean and parse JSON response from Gemini."""
    try:
        # If response is already valid JSON, return it
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        if "```json" in response_text and "```" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from code block: {json_text}")
        
        # Try to extract any JSON-like structure
        pattern = r'\{.*\}'
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from pattern match: {match.group(0)}")
        
        logger.error(f"Could not extract valid JSON from response: {response_text}")
        return {"type": "output", "output": "I couldn't process that request. Please try again."}

def format_date_with_current_year(date_str: str) -> str:
    """
    Format a date string to use the current year.
    
    Args:
        date_str: Date string in any format
        
    Returns:
        Date string in YYYY-MM-DD format with current year
    """
    try:
        # Get current year
        current_year = datetime.now().year
        
        # Parse the date string
        parsed_date = None
        
        # Try different date formats
        formats = [
            "%Y-%m-%d",  # YYYY-MM-DD
            "%m-%d",     # MM-DD
            "%d-%m",     # DD-MM
            "%B %d",     # Month Day
            "%d %B",     # Day Month
            "%b %d",     # Abbreviated Month Day
            "%d %b"      # Day Abbreviated Month
        ]
        
        for fmt in formats:
            try:
                if fmt == "%Y-%m-%d":
                    parsed_date = datetime.strptime(date_str, fmt)
                    break
                else:
                    # For formats without year, add a placeholder year
                    temp_date_str = f"2000-{date_str}" if "-" in date_str else f"2000 {date_str}"
                    temp_fmt = f"%Y-{fmt}" if "-" in fmt else f"%Y {fmt}"
                    parsed_date = datetime.strptime(temp_date_str, temp_fmt)
                    # Replace with current year
                    parsed_date = parsed_date.replace(year=current_year)
                    break
            except ValueError:
                continue
        
        if not parsed_date:
            # If all parsing attempts failed, raise an error
            raise ValueError(f"Could not parse date: {date_str}")
        
        # Return formatted date with current year
        return parsed_date.strftime("%Y-%m-%d")
    except Exception as e:
        logger.error(f"Error formatting date: {str(e)}")
        return date_str  # Return original string if parsing fails

async def process_chat_message(message: str, db: Session) -> str:
    """Process a chat message and return a response."""
    try:
        # Send message to Gemini
        logger.info(f"Sending message to Gemini: {message}")
        response = chat.send_message(message)
        response_text = response.text
        logger.info(f"Raw Gemini response: {response_text}")
        
        # Parse the response
        response_json = clean_json_response(response_text)
        
        # Handle direct output responses
        if "type" in response_json and response_json["type"] == "output":
            return response_json["output"]
        
        # Handle action responses
        if "type" in response_json and response_json["type"] == "action":
            function_name = response_json["function"]
            
            if function_name == "createTodo":
                input_data = response_json["input"]
                
                if isinstance(input_data, dict):
                    title = input_data.get("title", "")
                    due_date_str = input_data.get("due_date")
                else:
                    # Handle case where input is just a string
                    title = str(input_data)
                    due_date_str = None
                
                # Process due date if provided
                due_date = None
                if due_date_str:
                    try:
                        # Ensure the date uses the current year
                        formatted_date = format_date_with_current_year(due_date_str)
                        logger.info(f"Formatted date: {formatted_date} (original: {due_date_str})")
                        due_date = datetime.strptime(formatted_date, "%Y-%m-%d").isoformat()
                    except ValueError:
                        logger.error(f"Invalid date format: {due_date_str}")
                
                # Check for duplicate task
                if check_duplicate_task(db, title, due_date):
                    return f"You already have '{title}' in your tasks."
                
                # Create the task
                logger.info(f"Creating task: '{title}', due: {due_date}")
                try:
                    todo = create_todo(db, title, due_date)
                    logger.info(f"Created task: {title}, due: {due_date}, id: {todo.id}")
                    return f"I'll add '{title}' to your tasks."
                except Exception as e:
                    logger.error(f"Error creating task: {str(e)}")
                    return f"Sorry, I encountered an error creating your task: {str(e)}"
            
            elif function_name == "getAllTodos":
                # Get all todos
                todos = get_all_todos(db)
                
                # Format todos for display
                if todos:
                    formatted_todos = "\n".join([
                        f"- {todo.todo}" + (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "")
                        for todo in todos
                    ])
                    return f"Here are all your todos:\n{formatted_todos}"
                else:
                    return "You don't have any tasks yet. Try adding some!"
            
            elif function_name == "searchTodo":
                # This function is used for searching and potentially deleting todos
                search_term = response_json["input"].get("title", "")
                
                # Use the search term to find matching todos
                matching_todos = search_todos(db, search_term)
                
                if matching_todos:
                    # Format todos for display with IDs
                    formatted_todos = "\n".join([
                        f"- {todo.todo} (ID: {todo.id})" + 
                        (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "")
                        for todo in matching_todos
                    ])
                    
                    # Store the found todo IDs in the chat history for potential deletion
                    todo_ids = [todo.id for todo in matching_todos]
                    
                    # If there's only one match, we can return its ID directly for deletion
                    if len(todo_ids) == 1:
                        # Delete the todo by ID
                        success = delete_todo_by_id(db, todo_ids[0])
                        if success:
                            return f"I've removed '{matching_todos[0].todo}' from your list."
                        else:
                            return "I couldn't delete that task. Please try again."
                    
                    return f"I found tasks matching '{search_term}':\n{formatted_todos}"
                else:
                    return f"I couldn't find any tasks matching '{search_term}'."
            
            elif function_name == "deleteTodoById":
                todo_id = response_json["input"]
                
                # Delete the todo by ID
                success = delete_todo_by_id(db, todo_id)
                
                if success:
                    return f"I've removed that task from your list."
                else:
                    return "I couldn't find that task to delete."
        
        # If we get here, we couldn't process the response
        return "I apologize, but I couldn't understand how to process that. Could you please try again with a clearer request?"
    
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return "I encountered an error while processing your request. Could you please try again or rephrase your request?"
