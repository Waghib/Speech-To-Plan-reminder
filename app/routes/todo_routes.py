"""
Todo routes for the Speech-To-Plan Reminder application.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
from datetime import datetime

from app.models.todo import get_db, Todo
from app.services.todo_service import (
    get_all_todos, 
    create_todo, 
    delete_todo_by_id,
    search_todos
)

router = APIRouter(prefix="/todos", tags=["todos"])

class TodoResponse(BaseModel):
    """Todo response model."""
    id: int
    todo: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    calendar_event_id: Optional[str] = None

    class Config:
        from_attributes = True

class TodoCreate(BaseModel):
    """Todo creation model."""
    todo: str
    due_date: Optional[str] = None

@router.get("/", response_model=List[TodoResponse])
async def get_todos(db: Session = Depends(get_db)):
    """Get all todos."""
    return get_all_todos(db)

@router.post("/", response_model=TodoResponse)
async def add_todo(todo_data: TodoCreate, db: Session = Depends(get_db)):
    """Create a new todo."""
    return create_todo(db, todo_data.todo, todo_data.due_date)

@router.delete("/{todo_id}")
async def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    """Delete a todo by ID."""
    result = delete_todo_by_id(db, todo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"success": True}

@router.get("/search/")
async def search_todo(query: str, db: Session = Depends(get_db)):
    """Search todos by title."""
    return search_todos(db, query)

# Add a new action endpoint for Node.js server integration
class ActionRequest(BaseModel):
    function: str
    input: Union[Dict[str, Any], int, List[int], str]

@router.post("/action", response_model=Dict[str, Any])
async def handle_action(action: ActionRequest, db: Session = Depends(get_db)):
    """
    Handle actions forwarded from the Node.js server.
    This endpoint allows the Node.js server to perform database operations.
    """
    function_name = action.function
    input_data = action.input
    
    try:
        if function_name == "getAllTodos":
            # Get all todos
            todos = get_all_todos(db)
            
            # Format todos for display
            if todos:
                formatted_todos = "\n".join([
                    f"- {todo.todo}" + (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "")
                    for todo in todos
                ])
                return {"response": f"Here are all your todos:\n{formatted_todos}"}
            else:
                return {"response": "You don't have any tasks yet. Try adding some!"}
        
        elif function_name == "createTodo":
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
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").isoformat()
                except ValueError:
                    return {"response": f"Invalid date format: {due_date_str}"}
            
            # Create the task
            try:
                todo = create_todo(db, title, due_date)
                return {"response": f"I'll add '{title}' to your tasks."}
            except Exception as e:
                return {"response": f"Sorry, I encountered an error creating your task: {str(e)}"}
        
        elif function_name == "searchTodo":
            # This function is used for searching and potentially deleting todos
            if isinstance(input_data, dict):
                search_term = input_data.get("title", "")
            else:
                search_term = str(input_data)
            
            # Use the search term to find matching todos
            matching_todos = search_todos(db, search_term)
            
            if matching_todos:
                # Format todos for display with IDs
                formatted_todos = "\n".join([
                    f"- {todo.todo} (ID: {todo.id})" + 
                    (f" (Due: {todo.due_date.strftime('%Y-%m-%d')})" if todo.due_date else "")
                    for todo in matching_todos
                ])
                
                # If there's only one match, we can return its ID directly for deletion
                if len(matching_todos) == 1:
                    # Delete the todo by ID
                    success = delete_todo_by_id(db, matching_todos[0].id)
                    if success:
                        return {"response": f"I've removed '{matching_todos[0].todo}' from your list."}
                    else:
                        return {"response": "I couldn't delete that task. Please try again."}
                
                return {"response": f"I found tasks matching '{search_term}':\n{formatted_todos}"}
            else:
                return {"response": f"I couldn't find any tasks matching '{search_term}'."}
        
        elif function_name == "deleteTodoById":
            todo_id = input_data
            
            # Delete the todo by ID
            success = delete_todo_by_id(db, todo_id)
            
            if success:
                return {"response": f"I've removed that task from your list."}
            else:
                return {"response": "I couldn't find that task to delete."}
        
        # If we get here, the function name is not recognized
        return {"response": f"Unknown function: {function_name}"}
    
    except Exception as e:
        return {"response": f"Error processing action: {str(e)}"}
