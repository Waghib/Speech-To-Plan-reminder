# Speech-To-Plan Reminder - Browser Extension 🎙️✨

Transform your spoken words into organized plans and reminders effortlessly with this powerful Chrome extension! Speech-To-Plan Reminder is an innovative browser extension that leverages cutting-edge speech recognition and AI technology to convert voice inputs into structured task reminders and plans. With seamless Google Calendar integration, your tasks are not only recorded but automatically synced to your calendar, ensuring you never miss an important deadline or appointment.

## 🔄 Project Flow

![Project Flow Diagram](project-flow.png)

The diagram above illustrates the complete flow of the Speech-To-Plan Reminder system, showing how voice input is processed through various components to create organized tasks and calendar events.

## 🌟 Key Features

- **Voice-to-Text Conversion**: Advanced speech recognition using OpenAI Whisper
- **AI-Powered Task Analysis**: Intelligent task processing using Google's Gemini AI
- **Browser Integration**: Seamlessly works as a Chrome extension for easy access
- **Hybrid Architecture**: Node.js and Python servers working together for optimal performance
- **Persistent Storage**: Secure PostgreSQL database for reliable data management
- **Modern Web Interface**: Intuitive UI for easy interaction
- **Google Calendar Integration**: Automatically sync tasks with due dates to your Google Calendar

## 🚀 Technologies Used

- **AI & Machine Learning**:
  - OpenAI Whisper - State-of-the-art speech recognition
  - Google Gemini AI - Advanced natural language processing
  
- **Backend**:
  - Node.js - Event-driven JavaScript runtime for real-time communication
  - Express.js - Web application framework for Node.js
  - FastAPI - High-performance Python web framework
  - SQLAlchemy - SQL toolkit and ORM
  - Python 3.8+
  - Google Calendar API - Calendar integration and event management

- **Browser Extension**:
  - Chrome Extension APIs
  - HTML/CSS/JavaScript
  
- **Database**:
  - PostgreSQL - Robust, reliable database system

## 🏗️ Architecture

The application uses a hybrid architecture:

- **Node.js Server (Port 3000)**:
  - Acts as an API gateway for the Chrome extension
  - Handles real-time communication
  - Forwards requests to the Python backend
  - Provides better performance for concurrent connections

- **Python Server (Port 8000)**:
  - Manages core business logic
  - Handles database operations
  - Processes AI-related tasks
  - Integrates with Google Calendar

## Prerequisites

- Python 3.8 or higher
- Node.js 14.x or higher
- PostgreSQL database
- FFmpeg for audio processing
- Modern web browser (for extension)
- Google Cloud Platform account (for Calendar integration)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/waghib/Speech-To-Plan-reminder.git
   cd Speech-To-Plan-reminder
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Node.js dependencies:
   ```bash
   npm install
   ```

5. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Configure your database, API keys, and other settings

6. Initialize the database:
   ```bash
   python init_db.py
   ```

7. Set up Google Calendar Integration:
   - Go to Google Cloud Console
   - Create a new project or select an existing one
   - Enable the Google Calendar API
   - Create OAuth 2.0 credentials (Desktop application type)
   - Download the client secrets file and save it as `client_secret_[YOUR_CLIENT_ID].apps.googleusercontent.com.json` in the project root

## Running the Application

1. Start both servers using the provided script:
   ```bash
   # On Windows
   .\start-servers.ps1
   
   # On Linux/Mac
   # Use the equivalent bash script
   ```

   This will start:
   - Python server on port 8000
   - Node.js server on port 3000

2. Access the application through the browser extension:
   - Load the extension from the `extension` directory in Chrome
   - Click on the extension icon to open the popup interface

3. When adding a task with a due date, the application will:
   - Save the task in the local database
   - Create a corresponding event in your Google Calendar
   - Set up reminders (1 day and 1 hour before the event)
   - First-time users will need to authorize the application to access their Google Calendar

## Calendar Integration Features

- **Automatic Event Creation**: Tasks with due dates are automatically added to your Google Calendar
- **Smart Date Parsing**: Understands various date formats in your voice commands
- **Customized Reminders**: Sets up helpful reminders before each task's due date
- **All-Day Events**: Tasks are created as all-day events for better visibility
- **Timezone Aware**: Properly handles your local timezone for accurate scheduling

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Impact Statement

Speech-To-Plan Reminder revolutionizes the way we capture and organize our thoughts and tasks. By bridging the gap between natural speech and digital organization, it makes task management more accessible and efficient than ever before. With Google Calendar integration, it ensures your tasks are not just recorded but properly scheduled and remembered, making it an indispensable tool for anyone who wants to stay organized across multiple platforms.

---
Made with ❤️ by waghib for productivity enthusiasts everywhere
