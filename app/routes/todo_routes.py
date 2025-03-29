"""
Todo routes for the Speech-To-Plan Reminder application.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
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
