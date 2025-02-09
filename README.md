# Speech-To-Plan Reminder 

Transform your spoken words into organized plans and reminders effortlessly! Speech-To-Plan Reminder is an innovative application that leverages cutting-edge speech recognition technology to convert voice inputs into structured task reminders and plans.

## Key Features

- **Voice-to-Text Conversion**: Advanced speech recognition using OpenAI Whisper
- **Intelligent Task Processing**: Automatically extracts tasks and reminders from spoken content
- **Persistent Storage**: Secure PostgreSQL database for reliable data management
- **Modern Web Interface**: Intuitive UI for easy interaction
- **Browser Extension Support**: Seamless integration with your browsing experience

## Technologies Used

- **Backend**:
  - FastAPI - High-performance web framework
  - SQLAlchemy - SQL toolkit and ORM
  - OpenAI Whisper - State-of-the-art speech recognition
  - Python 3.8+

- **Database**:
  - PostgreSQL - Robust, reliable database system

- **Frontend**:
  - HTML/CSS/JavaScript
  - Browser Extension APIs

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- FFmpeg for audio processing
- Modern web browser (for extension)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Speech-To-Plan-reminder.git
   cd Speech-To-Plan-reminder
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Configure your database and other settings

5. Initialize the database:
   ```bash
   python init_db.py
   ```

## Running the Application

1. Start the server:
   ```bash
   uvicorn server:app --reload
   ```

2. Access the application through your web browser or the browser extension

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Impact Statement

Speech-To-Plan Reminder revolutionizes the way we capture and organize our thoughts and tasks. By bridging the gap between natural speech and digital organization, it makes task management more accessible and efficient than ever before. Whether you're a busy professional, a student, or anyone who prefers speaking over typing, this tool transforms the way you plan and remember important tasks.

---
Made with  for productivity enthusiasts everywhere
