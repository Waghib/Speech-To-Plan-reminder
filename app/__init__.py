"""
Speech-To-Plan Reminder Application Package.
This package contains the main application components.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Speech-To-Plan Reminder API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app.routes.todo_routes import router as todo_router
from app.routes.transcription_routes import router as transcription_router

# Include routers
app.include_router(todo_router)
app.include_router(transcription_router)

# Mount static files from extension directory
extension_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extension")
if os.path.exists(extension_dir):
    app.mount("/static", StaticFiles(directory=extension_dir), name="static")
    logger.info(f"Mounted static files from {extension_dir}")
else:
    logger.warning(f"Extension directory {extension_dir} does not exist")
