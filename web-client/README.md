# Speech-To-Plan Reminder Web Interface

This web interface allows you to access the Speech-To-Plan Reminder functionality through a browser, in addition to the Chrome extension.

## Features

- Voice recording and transcription
- Text-based chat interface
- Task management
- Google Calendar integration (through the backend)

## How to Use

1. Start both the Python and Node.js servers using the provided script:
   ```
   .\start-servers.ps1
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:3000
   ```

3. Use the interface to:
   - Record voice messages by clicking "Start Recording"
   - Type messages directly in the text area
   - View and manage your tasks
   - Chat with the AI assistant

## Technical Details

The web interface communicates with the Node.js server, which acts as a proxy to the Python backend. This provides the same functionality as the Chrome extension but in a web browser format.

## Troubleshooting

- Make sure both servers are running (Python on port 8000 and Node.js on port 3000)
- Check browser console for any JavaScript errors
- Ensure your microphone permissions are enabled for voice recording
- If you encounter CORS issues, make sure the Node.js server's CORS settings are properly configured
