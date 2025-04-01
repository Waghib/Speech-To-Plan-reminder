"""
Todo service for the Speech-To-Plan Reminder application.
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
import logging
from typing import List, Optional, Union, Tuple

from app.models.todo import Todo
from calendar_service import create_calendar_event

# Configure logging
logger = logging.getLogger(__name__)

def get_all_todos(db: Session) -> List[Todo]:
    """
    Get all todos from the database.
    
    Args:
        db: Database session
        
    Returns:
        List of Todo objects
    """
    return db.query(Todo).order_by(Todo.created_at.desc()).all()

def create_todo(db: Session, title: str, due_date: Optional[str] = None) -> Todo:
    """
    Create a new todo.
    
    Args:
        db: Database session
        title: Todo title
        due_date: Optional due date in ISO format
        
    Returns:
        Created Todo object
    """
    calendar_event_id = None
    parsed_due_date = None
    
    if due_date:
        try:
            # Parse due date
            logger.info(f"Processing due date: {due_date}")
            
            # Handle different date formats
            if 'T' in due_date:
                # ISO format with time
                parsed_due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            else:
                # Just date (YYYY-MM-DD)
                parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d")
            
            logger.info(f"Parsed due date: {parsed_due_date}")
            
            # Format date for calendar event (YYYY-MM-DD)
            calendar_date = parsed_due_date.strftime("%Y-%m-%d")
            
            # Create calendar event
            calendar_event_id = create_calendar_event(title, calendar_date)
            
            if calendar_event_id:
                logger.info(f"Created calendar event with ID: {calendar_event_id}")
            else:
                logger.warning("Failed to create calendar event, but will continue with task creation")
        except Exception as e:
            logger.error(f"Error processing due date: {str(e)}")
            # Continue with task creation even if calendar event creation fails
    
    # Create todo
    todo = Todo(
        todo=title,
        due_date=parsed_due_date,
        calendar_event_id=calendar_event_id
    )
    
    db.add(todo)
    db.commit()
    db.refresh(todo)
    
    return todo

def delete_todo_by_id(db: Session, todo_id: Union[int, List[int]]) -> bool:
    """
    Delete a todo by ID.
    
    Args:
        db: Database session
        todo_id: Todo ID or list of Todo IDs
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if isinstance(todo_id, list):
            # Delete multiple todos
            todos = db.query(Todo).filter(Todo.id.in_(todo_id)).all()
            if not todos:
                return False
            
            for todo in todos:
                db.delete(todo)
        else:
            # Delete single todo
            todo = db.query(Todo).filter(Todo.id == todo_id).first()
            if not todo:
                return False
            
            db.delete(todo)
        
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting todo: {str(e)}")
        db.rollback()
        return False

def search_todos(db: Session, query: str) -> List[Todo]:
    """
    Search todos by title.
    
    Args:
        db: Database session
        query: Search query
        
    Returns:
        List of matching Todo objects
    """
    search_term = f"%{query}%"
    return db.query(Todo).filter(
        or_(
            Todo.todo.ilike(search_term)
        )
    ).all()

def check_duplicate_task(db: Session, title: str, due_date: Optional[str] = None) -> bool:
    """
    Check if a task with the same title and due date already exists.
    
    Args:
        db: Database session
        title: Task title
        due_date: Optional due date in ISO format
        
    Returns:
        True if a duplicate exists, False otherwise
    """
    # Normalize the title for comparison (case insensitive)
    normalized_title = title.lower().strip()
    
    # Extract the core task name without date indicators and common phrases
    core_title = normalized_title
    date_indicators = ["tomorrow", "today", "next week", "next month", "on monday", "on tuesday", 
                      "on wednesday", "on thursday", "on friday", "on saturday", "on sunday"]
    common_phrases = ["i have", "i need to", "remind me to", "i want to", "i should", "i must"]
    
    # Remove date indicators
    for date_indicator in date_indicators:
        core_title = core_title.replace(date_indicator, "").strip()
    
    # Remove common phrases
    for phrase in common_phrases:
        if core_title.startswith(phrase):
            core_title = core_title[len(phrase):].strip()
    
    # Further normalize by removing articles and prepositions at the beginning
    for word in ["a ", "an ", "the ", "to ", "for ", "at ", "in ", "on "]:
        if core_title.startswith(word):
            core_title = core_title[len(word):].strip()
    
    logger.info(f"Checking for duplicate task. Original: '{title}', Normalized: '{core_title}'")
    
    # Get all todos
    todos = db.query(Todo).all()
    
    # If due_date is provided, parse it
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00')).date()
        except Exception as e:
            logger.error(f"Error parsing due date: {str(e)}")
    
    # Check each todo for similarity
    for todo in todos:
        # Normalize todo title
        todo_title = todo.todo.lower().strip()
        
        # Extract core todo title without date indicators and common phrases
        core_todo_title = todo_title
        
        # Remove date indicators
        for date_indicator in date_indicators:
            core_todo_title = core_todo_title.replace(date_indicator, "").strip()
        
        # Remove common phrases
        for phrase in common_phrases:
            if core_todo_title.startswith(phrase):
                core_todo_title = core_todo_title[len(phrase):].strip()
        
        # Further normalize by removing articles and prepositions at the beginning
        for word in ["a ", "an ", "the ", "to ", "for ", "at ", "in ", "on "]:
            if core_todo_title.startswith(word):
                core_todo_title = core_todo_title[len(word):].strip()
        
        logger.info(f"Comparing with existing task. Original: '{todo.todo}', Normalized: '{core_todo_title}'")
        
        # Compare normalized titles
        # Use a more flexible matching approach - check if one is contained in the other
        # or if they're very similar (e.g., "meeting" and "meeting with team")
        if (core_todo_title in core_title or core_title in core_todo_title or
            core_todo_title.split()[0] == core_title.split()[0]):  # Compare first words
            
            logger.info(f"Potential duplicate found: '{todo.todo}' vs '{title}'")
            
            # If no due date is specified for either task, consider it a duplicate
            if not due_date or not todo.due_date:
                logger.info(f"Duplicate confirmed (no due date): '{todo.todo}' vs '{title}'")
                return True
                
            # If due dates match, it's a duplicate
            elif todo.due_date and parsed_due_date and todo.due_date.date() == parsed_due_date:
                logger.info(f"Duplicate confirmed (matching due dates): '{todo.todo}' vs '{title}'")
                return True
                
            # If the existing task has no due date but we're adding one, consider it a duplicate
            # and update the existing task with the due date
            elif not todo.due_date and parsed_due_date:
                # Update the existing task with the due date
                todo.due_date = parsed_due_date
                db.commit()
                logger.info(f"Updated existing task with due date: '{todo.todo}' -> {parsed_due_date}")
                return True
    
    return False

def delete_todo_by_name(db: Session, task_name: str) -> Tuple[bool, int]:
    """
    Delete a todo by name.
    
    Args:
        db: Database session
        task_name: Name of the task to delete
        
    Returns:
        Tuple of (success, count) where success is True if any tasks were deleted,
        and count is the number of tasks deleted
    """
    try:
        # Find todos matching the name
        search_term = f"%{task_name}%"
        todos = db.query(Todo).filter(Todo.todo.ilike(search_term)).all()
        
        if not todos:
            return False, 0
        
        # Delete all matching todos
        count = 0
        for todo in todos:
            db.delete(todo)
            count += 1
        
        db.commit()
        return True, count
    except Exception as e:
        logger.error(f"Error deleting todo by name: {str(e)}")
        db.rollback()
        return False, 0
