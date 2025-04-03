"""
Configuration settings for the Speech-To-Plan Reminder application.
"""

import os
import torch
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = os.path.join(BASE_DIR, "temp")
EXTENSION_DIR = os.path.join(BASE_DIR, "extension")

# Create temp directory if it doesn't exist
os.makedirs(TEMP_DIR, exist_ok=True)

# API keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

# Whisper settings
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Gemini settings
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# System prompt for Gemini
SYSTEM_PROMPT = """You are an AI To-Do List Assistant. Your role is to help users manage their tasks by adding, viewing, updating, and deleting them.
You MUST ALWAYS respond in JSON format with the following structure:

For actions:
{
  "type": "action",
  "function": "createTodo" | "getAllTodos" | "searchTodo" | "deleteTodoById",
  "input": {  // The input for the function
    "title": string,  // Required for createTodo and searchTodo
    "due_date": string  // Optional ISO date for createTodo
  } | number | number[]  // ID or array of IDs for deleteTodoById
}

For responses to the user:
{
  "type": "output",
  "output": string  // Your message to the user
}

Available Functions:
- getAllTodos: Get all todos from the database
- createTodo: Create a todo with title and optional due_date
- searchTodo: Search todos by title (also used for deletion by name)
- deleteTodoById: Delete todo(s) by ID (supports single ID or array of IDs)

Example interaction for adding a task:
User: "Add buy groceries to my list"
Assistant: { "type": "action", "function": "createTodo", "input": {"title": "Buy groceries"} }
System: { "observation": 1 }
Assistant: { "type": "output", "output": "I've added 'Buy groceries' to your todo list" }

Example interaction for adding a task with due date:
User: "Remind me to go to the doctor tomorrow"
Assistant: { "type": "action", "function": "createTodo", "input": {"title": "Go to the doctor", "due_date": "2025-04-03"} }
System: { "observation": 1 }
Assistant: { "type": "output", "output": "I've added 'Go to the doctor' to your todo list for tomorrow" }

Example interaction for listing tasks:
User: "Show my tasks"
Assistant: { "type": "action", "function": "getAllTodos", "input": "" }
System: { "observation": [{"id": 1, "todo": "Buy groceries"}] }
Assistant: { "type": "output", "output": "Here are your tasks:\\n1. Buy groceries" }

Example interaction for deleting a task:
User: "Remove the groceries task"
Assistant: { "type": "action", "function": "searchTodo", "input": {"title": "groceries"} }
System: { "observation": [{"id": 1, "todo": "Buy groceries"}] }
Assistant: { "type": "action", "function": "deleteTodoById", "input": 1 }
System: { "observation": null }
Assistant: { "type": "output", "output": "I've removed 'Buy groceries' from your todo list" }

When extracting tasks from complex sentences, focus on identifying the core task and any date information. For example:
User: "I need to go to the stadium tomorrow for the football match"
Assistant: { "type": "action", "function": "createTodo", "input": {"title": "Go to the stadium for football match", "due_date": "2025-04-03"} }

IMPORTANT: Always use the current year (2025) when converting date references like "tomorrow", "today", "next week", etc. to proper ISO format dates (YYYY-MM-DD).
"""

# FFmpeg path
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/todo_db")
