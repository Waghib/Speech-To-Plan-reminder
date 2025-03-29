"""
Simple script to run the Speech-To-Plan Reminder application.
"""

import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.todo_routes import router as todo_router
from app.routes.transcription_routes import router as transcription_router
from app.models.todo import Base, engine

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

# Include routers
app.include_router(todo_router)
app.include_router(transcription_router)

# Create tables
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
