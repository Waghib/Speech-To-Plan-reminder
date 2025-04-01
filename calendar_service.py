from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import pickle
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = 'token.pickle'
CREDENTIALS_PATH = 'client_secret_7820419231-09jjarcsdkp3vprgfkhu1emerf0haiqt.apps.googleusercontent.com.json'

def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing credentials: {str(e)}")
                creds = None
        
        if not creds:
            try:
                # Use InstalledAppFlow for desktop applications
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH, 
                    SCOPES
                )
                # This will open the default web browser for authentication
                creds = flow.run_local_server(
                    port=0,  # Let the OS pick an available port
                    prompt='consent'  # Force consent screen to appear
                )
                logger.info("Successfully obtained new credentials")
            except Exception as e:
                logger.error(f"Error in OAuth flow: {str(e)}")
                raise Exception(f"Failed to authenticate with Google Calendar: {str(e)}")
        
        # Save the credentials for future use
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
            logger.info("Credentials saved successfully")

    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(title: str, due_date: str):
    try:
        # Check if credentials file exists
        if not os.path.exists(CREDENTIALS_PATH):
            logger.error(f"Credentials file not found at {CREDENTIALS_PATH}")
            return None
            
        service = get_calendar_service()
        
        # Ensure due_date is in the correct format (YYYY-MM-DD)
        if not due_date or not isinstance(due_date, str):
            logger.error(f"Invalid due_date format: {due_date}")
            return None
            
        # Format the date if it contains time information
        if 'T' in due_date:
            due_date = due_date.split('T')[0]
            
        logger.info(f"Creating calendar event: Title='{title}', Date='{due_date}'")
        
        # Create the event
        event = {
            'summary': title,
            'start': {
                'date': due_date,  # Use date for all-day events
                'timeZone': 'Asia/Karachi',
            },
            'end': {
                'date': due_date,
                'timeZone': 'Asia/Karachi',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 24 * 60},  # 1 day before
                    {'method': 'popup', 'minutes': 60},  # 1 hour before
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Successfully created calendar event: {event.get('htmlLink')}")
        return event['id']
    except Exception as e:
        logger.error(f"Error creating calendar event: {str(e)}")
        # Return None instead of raising an exception to prevent task creation failure
        return None
