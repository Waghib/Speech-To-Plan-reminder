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
            parsed_due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            
            # Create calendar event
            calendar_event_id = create_calendar_event(title, due_date.split('T')[0])
            logger.info(f"Created calendar event with ID: {calendar_event_id}")
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
    
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
