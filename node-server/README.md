# Speech-To-Plan Reminder Node.js Server

This Node.js server is part of the hybrid architecture for the Speech-To-Plan Reminder application. It handles chat functionality and forwards other requests to the Python backend.

## Architecture Overview

The application now uses a hybrid architecture:

1. **Node.js Server (This Server)**
   - Handles chat functionality using the Gemini API
   - Acts as a proxy for requests to the Python backend
   - Runs on port 3000 by default

2. **Python Server**
   - Handles database operations
   - Manages todo items
   - Processes transcriptions
   - Runs on port 8000 by default

## Setup Instructions

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Configure Environment Variables**
   - Copy `.env.example` to `.env`
   - Update the values in `.env` with your configuration

3. **Start the Server**
   ```bash
   npm start
   ```

   For development with auto-restart:
   ```bash
   npm run dev
   ```

## API Endpoints

### Chat Functionality
- `POST /chat` - Send a message to the chat assistant

### Todo Management (Proxied to Python Server)
- `GET /todos` - Get all todos
- `DELETE /todos/:id` - Delete a todo by ID
- `POST /todos/:id/toggle` - Toggle a todo's completion status

### Transcription (Proxied to Python Server)
- `POST /transcribe_gemini` - Transcribe audio using Gemini API

### Health Check
- `GET /health` - Check server status

## Environment Variables

- `NODE_PORT` - Port for the Node.js server (default: 3000)
- `PYTHON_SERVER_URL` - URL of the Python backend (default: http://localhost:8000)
- `GOOGLE_API_KEY` - Google API key for Gemini
- `GEMINI_MODEL` - Gemini model to use (default: gemini-1.5-flash)

## Notes

- Make sure both the Node.js and Python servers are running for the application to work properly.
- The frontend should be configured to connect to the Node.js server (port 3000) instead of directly to the Python server.
