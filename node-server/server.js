require('dotenv').config();
const express = require('express');
const cors = require('cors');
const axios = require('axios');
const { GoogleAuth } = require('google-auth-library');

const app = express();
const PORT = process.env.NODE_PORT || 3000;
const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL || 'http://localhost:8000';

// Middleware
app.use(cors({
  origin: '*', // Allow all origins
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true
}));
app.use(express.json());

// Initialize Google Auth for Gemini API
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-1.5-flash';

// System prompt for Gemini
const SYSTEM_PROMPT = `You are an AI To-Do List Assistant. Your role is to help users manage their tasks by adding, viewing, updating, and deleting them.
You MUST ALWAYS respond in JSON format with the following structure:

For actions:
{
  "type": "action",
  "function": "createTodo" | "getAllTodos" | "searchTodo" | "deleteTodoById",
  "input": {  // The input for the function
    "title": string,  // Required for createTodo and searchTodo
    "due_date": string  // Optional ISO date for createTodo
  } | number | number[]  // ID or array of IDs for deleteTodoById
}

For responses to the user:
{
  "type": "output",
  "output": string  // Your message to the user
}

Available Functions:
- getAllTodos: Get all todos from the database
- createTodo: Create a todo with title and optional due_date
- searchTodo: Search todos by title (also used for deletion by name)
- deleteTodoById: Delete todo(s) by ID (supports single ID or array of IDs)

IMPORTANT: Always use the current year (2025) when converting date references like "tomorrow", "today", "next week", etc. to proper ISO format dates (YYYY-MM-DD).`;

// Store chat history
let chatHistory = [];

// Helper function to clean JSON response
function cleanJsonResponse(responseText) {
  try {
    // Extract JSON from response if needed
    if (responseText.includes("```json")) {
      const jsonStart = responseText.indexOf("```json") + 7;
      const jsonEnd = responseText.indexOf("```", jsonStart);
      responseText = responseText.substring(jsonStart, jsonEnd).trim();
    } else if (responseText.includes("```")) {
      const jsonStart = responseText.indexOf("```") + 3;
      const jsonEnd = responseText.indexOf("```", jsonStart);
      responseText = responseText.substring(jsonStart, jsonEnd).trim();
    }
    
    // Clean up any remaining non-JSON content
    const lines = responseText.split('\n');
    const jsonLines = [];
    for (const line of lines) {
      if (line.trim() && !line.startsWith('//') && !line.startsWith('#')) {
        jsonLines.push(line);
      }
    }
    
    const cleanedText = jsonLines.join('\n');
    return JSON.parse(cleanedText);
  } catch (error) {
    console.error(`Error parsing JSON: ${error.message}, Response: ${responseText}`);
    return { type: "output", output: "Sorry, I encountered an error processing your request." };
  }
}

// Format date with current year
function formatDateWithCurrentYear(dateStr) {
  try {
    // Get current year
    const currentYear = new Date().getFullYear();
    
    // Parse the date string
    let parsedDate = null;
    
    // Try different date formats
    const formats = [
      { regex: /^\d{4}-\d{2}-\d{2}$/, format: 'YYYY-MM-DD' }, // YYYY-MM-DD
      { regex: /^\d{2}-\d{2}$/, format: 'MM-DD' },           // MM-DD
      { regex: /^\d{2} [A-Za-z]+$/, format: 'DD Month' },    // DD Month
      { regex: /^[A-Za-z]+ \d{2}$/, format: 'Month DD' }     // Month DD
    ];
    
    // Check if it's a full ISO date
    if (formats[0].regex.test(dateStr)) {
      return dateStr; // Already in YYYY-MM-DD format
    }
    
    // Handle special cases
    const today = new Date();
    if (dateStr.toLowerCase() === 'tomorrow') {
      const tomorrow = new Date();
      tomorrow.setDate(today.getDate() + 1);
      return tomorrow.toISOString().split('T')[0];
    } else if (dateStr.toLowerCase() === 'today') {
      return today.toISOString().split('T')[0];
    } else if (dateStr.toLowerCase().includes('next week')) {
      const nextWeek = new Date();
      nextWeek.setDate(today.getDate() + 7);
      return nextWeek.toISOString().split('T')[0];
    }
    
    // Try to parse with Date object
    const date = new Date(dateStr);
    if (!isNaN(date.getTime())) {
      // Set current year if the year is not the current year
      if (date.getFullYear() !== currentYear) {
        date.setFullYear(currentYear);
      }
      return date.toISOString().split('T')[0];
    }
    
    // If all parsing attempts failed, return original string
    console.error(`Could not parse date: ${dateStr}`);
    return dateStr;
  } catch (error) {
    console.error(`Error formatting date: ${error.message}`);
    return dateStr; // Return original string if parsing fails
  }
}

// Chat endpoint
app.post('/chat', async (req, res) => {
  try {
    const { text } = req.body;
    
    if (!text) {
      return res.status(400).json({ error: 'No text provided' });
    }
    
    console.log(`Received chat message: ${text}`);
    
    // Forward to Python server for chat processing
    try {
      console.log("Using Python server for chat processing");
      console.log("Request body:", JSON.stringify(req.body));
      
      const pythonChatResponse = await axios.post(
        `${PYTHON_SERVER_URL}/chat`,
        { text }
      );
      
      console.log("Python server response:", JSON.stringify(pythonChatResponse.data));
      
      // Send the response back to the client
      return res.json(pythonChatResponse.data);
    } catch (fallbackError) {
      console.error(`Python server failed: ${fallbackError.message}`);
      if (fallbackError.response) {
        console.error("Response data:", JSON.stringify(fallbackError.response.data));
        console.error("Response status:", fallbackError.response.status);
      }
      return res.status(500).json({ 
        error: 'Server error', 
        message: 'Python server failed to process the chat message' 
      });
    }
  } catch (error) {
    console.error(`Error processing chat message: ${error.message}`);
    if (error.response) {
      console.error("Response data:", JSON.stringify(error.response.data));
    }
    return res.status(500).json({ 
      error: 'Server error', 
      message: error.message 
    });
  }
});

// Proxy endpoint for transcription
app.post('/transcribe_gemini', async (req, res) => {
  try {
    // Forward the request to the Python server
    const response = await axios.post(
      `${PYTHON_SERVER_URL}/transcribe_gemini`,
      req.body,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...req.headers
        },
        responseType: 'stream'
      }
    );
    
    // Forward the response back to the client
    response.data.pipe(res);
  } catch (error) {
    console.error(`Error forwarding transcription request: ${error.message}`);
    return res.status(500).json({ 
      error: 'Server error', 
      message: error.message 
    });
  }
});

// Proxy endpoint for todos
app.get('/todos', async (req, res) => {
  try {
    // Forward the request to the Python server
    const response = await axios.get(`${PYTHON_SERVER_URL}/todos`);
    
    // Forward the response back to the client
    return res.json(response.data);
  } catch (error) {
    console.error(`Error forwarding todos request: ${error.message}`);
    return res.status(500).json({ 
      error: 'Server error', 
      message: error.message 
    });
  }
});

// Proxy endpoint for deleting a todo
app.delete('/todos/:id', async (req, res) => {
  try {
    // Forward the request to the Python server
    const response = await axios.delete(`${PYTHON_SERVER_URL}/todos/${req.params.id}`);
    
    // Forward the response back to the client
    return res.json(response.data);
  } catch (error) {
    console.error(`Error forwarding delete todo request: ${error.message}`);
    return res.status(500).json({ 
      error: 'Server error', 
      message: error.message 
    });
  }
});

// Proxy endpoint for toggling a todo
app.post('/todos/:id/toggle', async (req, res) => {
  try {
    // Forward the request to the Python server
    const response = await axios.post(`${PYTHON_SERVER_URL}/todos/${req.params.id}/toggle`);
    
    // Forward the response back to the client
    return res.json(response.data);
  } catch (error) {
    console.error(`Error forwarding toggle todo request: ${error.message}`);
    return res.status(500).json({ 
      error: 'Server error', 
      message: error.message 
    });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', server: 'node' });
});

// Start the server
app.listen(PORT, () => {
  console.log(`Node.js server running on port ${PORT}`);
  console.log(`Connecting to Python server at ${PYTHON_SERVER_URL}`);
});
