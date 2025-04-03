document.addEventListener('DOMContentLoaded', function() {
    const micButton = document.getElementById('micButton');
    const textInput = document.getElementById('textInput');
    const sendButton = document.getElementById('sendButton');
    const status = document.getElementById('status');
    const chatMessages = document.getElementById('chat-messages');
    const todoList = document.getElementById('todoList');

    console.log("DOM loaded, elements:", {
        micButton: !!micButton,
        textInput: !!textInput,
        sendButton: !!sendButton,
        status: !!status,
        chatMessages: !!chatMessages,
        todoList: !!todoList
    });

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
            const response = await fetch('http://localhost:3000/transcribe_gemini', {
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
            
            try {
                console.log('Sending chat message to Node.js server:', text);
                const response = await fetch('http://localhost:3000/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text: text }),
                    mode: 'cors'
                });
                
                console.log('Response status:', response.status);
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    console.error('Error data:', errorData);
                    throw new Error(errorData.detail || errorData.message || `Server error: ${response.status}`);
                }
                
                // Clone the response for debugging
                const responseClone = response.clone();
                const responseText = await responseClone.text();
                console.log('Raw response text:', responseText);
                
                // Parse the response as JSON
                let data;
                try {
                    data = JSON.parse(responseText);
                    console.log('Parsed response data:', data);
                } catch (parseError) {
                    console.error('Error parsing JSON:', parseError);
                    throw new Error('Invalid JSON response from server');
                }
                
                if (!data.response) {
                    console.error('Missing response field in data:', data);
                    throw new Error('Invalid response format from server');
                }
                
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
            console.log("Refreshing todo list...");
            const response = await fetch('http://localhost:3000/todos');
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const todos = await response.json();
            console.log("Todos received:", todos);
            
            // Make sure todoList element exists
            if (!todoList) {
                console.error("Todo list element not found!");
                return;
            }
            
            todoList.innerHTML = ''; // Clear existing todos

            if (!Array.isArray(todos) || todos.length === 0) {
                console.log("No todos found or invalid response format");
                const emptyMessage = document.createElement('div');
                emptyMessage.className = 'empty-todo-message';
                emptyMessage.textContent = 'No tasks found. Add some tasks to get started!';
                todoList.appendChild(emptyMessage);
                return;
            }

            console.log(`Found ${todos.length} todos to display`);
            todos.forEach(todo => {
                console.log("Processing todo:", todo);
                const todoItem = document.createElement('div');
                todoItem.className = 'todo-item';
                
                const todoText = document.createElement('span');
                todoText.className = 'todo-text';
                todoText.textContent = todo.todo;

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-btn';
                deleteBtn.innerHTML = '&times;';
                deleteBtn.addEventListener('click', () => deleteTodo(todo.id));

                // Add due date if available
                if (todo.due_date) {
                    const dueDate = new Date(todo.due_date);
                    const dueDateElem = document.createElement('span');
                    dueDateElem.className = 'due-date';
                    dueDateElem.textContent = `Due: ${dueDate.toLocaleDateString()}`;
                    todoItem.appendChild(dueDateElem);
                }

                todoItem.appendChild(todoText);
                todoItem.appendChild(deleteBtn);
                todoList.appendChild(todoItem);
            });
            console.log("Todo list refreshed successfully");

        } catch (error) {
            console.error('Error loading todos:', error);
        }
    }

    async function deleteTodo(todoId) {
        try {
            const response = await fetch(`http://localhost:3000/todos/${todoId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            
            await refreshTodoList();
            
            // Add a system message
            const systemMsg = document.createElement('div');
            systemMsg.className = 'message bot-message';
            systemMsg.textContent = 'Task deleted successfully!';
            chatMessages.appendChild(systemMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
        } catch (error) {
            console.error('Error deleting todo:', error);
        }
    }

    async function toggleTodo(todoId) {
        try {
            const response = await fetch(`http://localhost:3000/todos/${todoId}/toggle`, {
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
