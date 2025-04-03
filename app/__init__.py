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

# Create API router for Node.js server integration
from fastapi import APIRouter
api_router = APIRouter(prefix="/api", tags=["api"])

# Include todo router in the API router with a different prefix
api_router.include_router(todo_router, prefix="/todo")

# Include the API router in the main app
app.include_router(api_router)

# Serve static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """Root endpoint that returns a welcome message."""
    return {"message": "Welcome to the Speech-To-Plan Reminder API"}
