document.addEventListener('DOMContentLoaded', function() {
    const micButton = document.getElementById('micButton');
    const textInput = document.getElementById('textInput');
    const sendButton = document.getElementById('sendButton');
    const status = document.getElementById('status');
    const chatMessages = document.getElementById('chat-messages');
    const todoList = document.getElementById('todoList');

    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    function updateMicButtonState(recording) {
        isRecording = recording;
        micButton.classList.toggle('recording', recording);
        status.textContent = recording ? 'Recording...' : 'Type or speak';
    }

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    channelCount: 1,
                    sampleRate: 16000
                }
            });
            
            mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus',
                audioBitsPerSecond: 16000
            });
            audioChunks = [];

            mediaRecorder.addEventListener('dataavailable', event => {
                audioChunks.push(event.data);
            });

            mediaRecorder.addEventListener('stop', async () => {
                try {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    stream.getTracks().forEach(track => track.stop());
                    await processAudio(audioBlob);
                } catch (error) {
                    console.error('Error processing audio:', error);
                    status.textContent = 'Error. Try again';
                    updateMicButtonState(false);
                }
            });

            mediaRecorder.start();
            updateMicButtonState(true);

        } catch (error) {
            console.error('Microphone access error:', error);
            status.textContent = 'Mic access denied';
            updateMicButtonState(false);
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            updateMicButtonState(false);
            status.textContent = 'Processing...';
        }
    }

    async function processAudio(audioBlob) {
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            
            status.textContent = 'Processing...';
            const response = await fetch('http://localhost:8000/transcribe_gemini', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }

            // Add the transcribed text as a user message
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user-message';
            messageDiv.textContent = data.transcription || data.text;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            if (data.chat_response) {
                const botDiv = document.createElement('div');
                botDiv.className = 'message bot-message';
                botDiv.textContent = data.chat_response;
                chatMessages.appendChild(botDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
            
            status.textContent = 'Type or speak';
            await refreshTodoList();

        } catch (error) {
            console.error('Error:', error);
            status.textContent = 'Error. Try again';
        }
    }

    async function sendTextMessage(text) {
        if (!text.trim()) return;
        
        try {
            // Add the text as a user message
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user-message';
            messageDiv.textContent = text;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            status.textContent = 'Processing...';
            
            // Send the text to the server
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            
            // Add the bot's response
            const botDiv = document.createElement('div');
            botDiv.className = 'message bot-message';
            botDiv.textContent = data.response;
            chatMessages.appendChild(botDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            status.textContent = 'Type or speak';
            await refreshTodoList();
            
        } catch (error) {
            console.error('Error:', error);
            status.textContent = 'Error. Try again';
            
            // Add error message as bot message
            const errorDiv = document.createElement('div');
            errorDiv.className = 'message bot-message';
            errorDiv.textContent = 'Sorry, there was an error processing your message. Please try again.';
            chatMessages.appendChild(errorDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    async function refreshTodoList() {
        try {
            const response = await fetch('http://localhost:8000/todos');
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const todos = await response.json();
            todoList.innerHTML = ''; // Clear existing todos

            // todos.forEach(todo => {
            //     const todoItem = document.createElement('div');
            //     todoItem.className = `todo-item${todo.completed ? ' completed' : ''}`;
                
            //     const checkbox = document.createElement('input');
            //     checkbox.type = 'checkbox';
            //     checkbox.checked = todo.completed;
            //     checkbox.addEventListener('change', () => toggleTodo(todo.id));

            //     const todoText = document.createElement('span');
            //     todoText.textContent = todo.text;

            //     todoItem.appendChild(checkbox);
            //     todoItem.appendChild(todoText);
            //     todoList.appendChild(todoItem);
            // });

        } catch (error) {
            console.error('Error loading todos:', error);
        }
    }

    async function toggleTodo(todoId) {
        try {
            const response = await fetch(`http://localhost:8000/todos/${todoId}/toggle`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            await refreshTodoList();
        } catch (error) {
            console.error('Error updating todo:', error);
        }
    }

    if (micButton) {
        micButton.addEventListener('click', () => {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });
    } else {
        console.error('Microphone button not found');
    }

    // Handle text input submission
    if (sendButton && textInput) {
        // Send on button click
        sendButton.addEventListener('click', () => {
            const text = textInput.value;
            if (text.trim()) {
                sendTextMessage(text);
                textInput.value = ''; // Clear input after sending
            }
        });
        
        // Send on Enter key press
        textInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                const text = textInput.value;
                if (text.trim()) {
                    sendTextMessage(text);
                    textInput.value = ''; // Clear input after sending
                }
            }
        });
    } else {
        console.error('Text input or send button not found');
    }

    // Load initial todo list
    refreshTodoList();
});
