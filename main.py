"""
Main entry point for the Speech-To-Plan Reminder application.
"""

import uvicorn
import logging
from sqladmin import Admin, ModelView

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import app and models
from app import app
from app.models.todo import Todo, engine

# Create TodoAdmin view
class TodoAdmin(ModelView, model=Todo):
    column_list = [Todo.id, Todo.todo, Todo.due_date, Todo.created_at, Todo.updated_at, Todo.calendar_event_id]
    column_searchable_list = [Todo.todo]
    column_sortable_list = [Todo.id, Todo.created_at, Todo.due_date]
    column_default_sort = ("created_at", True)
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    name = "Todo"
    icon = "fa-solid fa-list-check"

# Initialize Admin and add views
admin = Admin(app, engine)
admin.add_view(TodoAdmin)

if __name__ == "__main__":
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
