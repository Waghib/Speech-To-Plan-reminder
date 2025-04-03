document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const recordingProgress = document.getElementById('recordingProgress');
    const recordingStatus = document.getElementById('recordingStatus');
    const textInput = document.getElementById('textInput');
    const sendMessageBtn = document.getElementById('sendMessage');
    const chatHistory = document.getElementById('chatHistory');
    const taskList = document.getElementById('taskList');
    const refreshTasksBtn = document.getElementById('refreshTasks');
    const filterTasksBtn = document.getElementById('filterTasks');
    const tabButtons = document.querySelectorAll('.tab-btn');

    // Variables for recording
    let mediaRecorder;
    let audioChunks = [];
    let recordingInterval;
    let recordingTime = 0;
    const MAX_RECORDING_TIME = 60; // seconds
    let taskFilter = 'all'; // 'all', 'active', 'completed'

    // Server URL
    const SERVER_URL = 'http://localhost:3000';

    // Initialize
    function init() {
        // Event listeners
        startRecordingBtn.addEventListener('click', startRecording);
        stopRecordingBtn.addEventListener('click', stopRecording);
        sendMessageBtn.addEventListener('click', sendMessage);
        textInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Task management event listeners
        refreshTasksBtn.addEventListener('click', loadTasks);
        filterTasksBtn.addEventListener('click', toggleTaskFilter);
        
        // Tab navigation
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');
                activateTab(tabName);
            });
        });
        
        // Handle responsive layout
        handleResponsiveLayout();
        window.addEventListener('resize', handleResponsiveLayout);

        // Load tasks
        loadTasks();
    }
    
    // Toggle task filter
    function toggleTaskFilter() {
        // Cycle through filter options: all -> active -> completed -> all
        if (taskFilter === 'all') {
            taskFilter = 'active';
        } else if (taskFilter === 'active') {
            taskFilter = 'completed';
        } else {
            taskFilter = 'all';
        }
        
        // Update button appearance to indicate current filter
        filterTasksBtn.innerHTML = `<i class="bi bi-funnel"></i> ${taskFilter.charAt(0).toUpperCase() + taskFilter.slice(1)}`;
        
        // Apply the filter
        loadTasks();
    }
    
    // Activate tab
    function activateTab(tabName) {
        // Remove active class from all tab buttons
        tabButtons.forEach(btn => btn.classList.remove('active'));
        
        // Add active class to the clicked tab button
        document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('active');
        
        // Show/hide content based on tab
        const appContent = document.querySelector('.app-content');
        
        if (tabName === 'chat') {
            appContent.style.flexDirection = window.innerWidth < 768 ? 'column' : 'row';
            document.querySelector('.chat-section').style.display = 'flex';
            document.querySelector('.tasks-section').style.display = window.innerWidth < 768 ? 'none' : 'flex';
        } else if (tabName === 'tasks') {
            appContent.style.flexDirection = 'column';
            document.querySelector('.chat-section').style.display = 'none';
            document.querySelector('.tasks-section').style.display = 'flex';
            loadTasks(); // Refresh tasks when switching to tasks tab
        } else if (tabName === 'calendar') {
            // Future implementation for calendar tab
            appContent.style.flexDirection = 'column';
            document.querySelector('.chat-section').style.display = 'none';
            document.querySelector('.tasks-section').style.display = 'none';
            alert('Calendar feature coming soon!');
        } else if (tabName === 'settings') {
            // Future implementation for settings tab
            appContent.style.flexDirection = 'column';
            document.querySelector('.chat-section').style.display = 'none';
            document.querySelector('.tasks-section').style.display = 'none';
            alert('Settings feature coming soon!');
        }
    }
    
    // Handle responsive layout
    function handleResponsiveLayout() {
        if (window.innerWidth < 768) {
            // Mobile view: show tabs
            document.querySelector('.app-footer').style.display = 'block';
            // Default to chat view on mobile
            activateTab('chat');
        } else {
            // Desktop view: hide tabs, show split view
            document.querySelector('.app-footer').style.display = 'none';
            document.querySelector('.chat-section').style.display = 'flex';
            document.querySelector('.tasks-section').style.display = 'flex';
            document.querySelector('.app-content').style.flexDirection = 'row';
        }
    }

    // Start recording
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await processAudio(audioBlob);
                audioChunks = [];
                
                // Stop all tracks to release microphone
                stream.getTracks().forEach(track => track.stop());
            };
            
            // Start recording
            audioChunks = [];
            mediaRecorder.start();
            
            // Update UI
            startRecordingBtn.disabled = true;
            stopRecordingBtn.disabled = false;
            recordingStatus.classList.add('active');
            
            // Start progress bar
            recordingTime = 0;
            recordingProgress.style.width = '0%';
            recordingInterval = setInterval(() => {
                recordingTime++;
                const progress = (recordingTime / MAX_RECORDING_TIME) * 100;
                recordingProgress.style.width = `${progress}%`;
                
                if (recordingTime >= MAX_RECORDING_TIME) {
                    stopRecording();
                }
            }, 1000);
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Error accessing microphone. Please make sure you have granted permission.');
        }
    }

    // Stop recording
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            clearInterval(recordingInterval);
            
            // Update UI
            startRecordingBtn.disabled = false;
            stopRecordingBtn.disabled = true;
            recordingStatus.classList.remove('active');
            recordingProgress.style.width = '0%';
        }
    }

    // Process audio
    async function processAudio(audioBlob) {
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');
            
            // Show loading indicator in chat
            const loadingId = addLoadingMessage();
            
            const response = await fetch(`${SERVER_URL}/transcribe`, {
                method: 'POST',
                body: formData,
            });
            
            // Remove loading indicator
            removeLoadingMessage(loadingId);
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.text) {
                // Add transcribed text to chat
                addMessageToChat('user', data.text);
                
                // Process the transcribed text
                await processMessage(data.text);
            }
        } catch (error) {
            console.error('Error processing audio:', error);
            addMessageToChat('assistant', 'Sorry, there was an error processing your audio. Please try again.');
        }
    }
    
    // Add loading message to chat
    function addLoadingMessage() {
        const id = 'loading-' + Date.now();
        const loadingElement = document.createElement('div');
        loadingElement.id = id;
        loadingElement.classList.add('message', 'assistant', 'loading');
        loadingElement.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Thinking...';
        chatHistory.appendChild(loadingElement);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return id;
    }
    
    // Remove loading message
    function removeLoadingMessage(id) {
        const loadingElement = document.getElementById(id);
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    // Process message
    async function processMessage(message) {
        try {
            // Show loading indicator
            const loadingId = addLoadingMessage();
            
            // Send to server
            const response = await fetch(`${SERVER_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: message }),
            });
            
            // Remove loading indicator
            removeLoadingMessage(loadingId);
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            
            // Add response to chat
            addMessageToChat('assistant', data.response);
            
            // Refresh tasks
            loadTasks();
        } catch (error) {
            console.error('Error processing message:', error);
            addMessageToChat('assistant', 'Sorry, there was an error processing your message. Please try again.');
        }
    }
    
    // Send message
    async function sendMessage() {
        const message = textInput.value.trim();
        if (!message) return;
        
        // Add message to chat
        addMessageToChat('user', message);
        
        // Clear input
        textInput.value = '';
        
        // Process the message
        await processMessage(message);
    }

    // Add message to chat
    function addMessageToChat(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.textContent = text;
        
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // Load tasks
    async function loadTasks() {
        try {
            // Show loading indicator
            taskList.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Loading tasks...</div>';
            
            const response = await fetch(`${SERVER_URL}/todos`);
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const tasks = await response.json();
            
            // Clear task list
            taskList.innerHTML = '';
            
            if (tasks.length === 0) {
                taskList.innerHTML = '<div class="text-center text-muted">No tasks yet. Start a conversation to create tasks!</div>';
                return;
            }
            
            // Filter tasks based on current filter
            let filteredTasks = tasks;
            if (taskFilter === 'active') {
                filteredTasks = tasks.filter(task => !task.completed);
            } else if (taskFilter === 'completed') {
                filteredTasks = tasks.filter(task => task.completed);
            }
            
            // Show filter status
            const filterStatus = document.createElement('div');
            filterStatus.className = 'filter-status';
            filterStatus.innerHTML = `<small class="text-muted">Showing ${filteredTasks.length} ${taskFilter} task${filteredTasks.length !== 1 ? 's' : ''}</small>`;
            taskList.appendChild(filterStatus);
            
            // Add tasks to list
            filteredTasks.forEach(task => {
                const taskDiv = document.createElement('div');
                taskDiv.className = 'task-item';
                taskDiv.dataset.id = task.id;
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'task-checkbox';
                checkbox.checked = task.completed;
                checkbox.addEventListener('change', () => toggleTaskCompletion(task.id, checkbox.checked));
                
                const taskContent = document.createElement('div');
                taskContent.className = 'task-content';
                
                const taskText = document.createElement('div');
                taskText.className = `task-text ${task.completed ? 'task-completed' : ''}`;
                taskText.textContent = task.title;
                
                const taskDetails = document.createElement('div');
                taskDetails.className = 'task-details';
                
                // Add due date if available
                if (task.due_date) {
                    const date = new Date(task.due_date);
                    const today = new Date();
                    const tomorrow = new Date(today);
                    tomorrow.setDate(tomorrow.getDate() + 1);
                    
                    let dateText = '';
                    let dateClass = '';
                    
                    // Format date as Today, Tomorrow, or date
                    if (date.toDateString() === today.toDateString()) {
                        dateText = 'Today';
                        dateClass = 'date-today';
                    } else if (date.toDateString() === tomorrow.toDateString()) {
                        dateText = 'Tomorrow';
                        dateClass = 'date-tomorrow';
                    } else {
                        dateText = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                        
                        // Add year if not current year
                        if (date.getFullYear() !== today.getFullYear()) {
                            dateText += `, ${date.getFullYear()}`;
                        }
                        
                        // Check if date is past
                        if (date < today) {
                            dateClass = 'date-past';
                        }
                    }
                    
                    const dateSpan = document.createElement('span');
                    dateSpan.className = `task-date ${dateClass}`;
                    dateSpan.innerHTML = `<i class="bi bi-calendar"></i> ${dateText}`;
                    taskDetails.appendChild(dateSpan);
                }
                
                // Add delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'task-delete-btn';
                deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteTask(task.id);
                });
                
                taskContent.appendChild(taskText);
                taskContent.appendChild(taskDetails);
                
                taskDiv.appendChild(checkbox);
                taskDiv.appendChild(taskContent);
                taskDiv.appendChild(deleteBtn);
                
                taskList.appendChild(taskDiv);
            });
        } catch (error) {
            console.error('Error loading tasks:', error);
            taskList.innerHTML = '<div class="text-center text-danger">Error loading tasks</div>';
        }
    }

    // Toggle task completion
    async function toggleTaskCompletion(taskId, completed) {
        try {
            const response = await fetch(`${SERVER_URL}/todos/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ completed }),
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            // Refresh tasks
            loadTasks();
        } catch (error) {
            console.error('Error updating task:', error);
            addMessageToChat('assistant', 'Sorry, there was an error updating the task. Please try again.');
        }
    }
    
    // Delete task
    async function deleteTask(taskId) {
        // Confirm deletion
        if (!confirm('Are you sure you want to delete this task?')) {
            return;
        }
        
        try {
            const response = await fetch(`${SERVER_URL}/todos/${taskId}`, {
                method: 'DELETE',
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            // Refresh tasks
            loadTasks();
            
            // Show confirmation
            addMessageToChat('assistant', 'Task deleted successfully.');
        } catch (error) {
            console.error('Error deleting task:', error);
            addMessageToChat('assistant', 'Sorry, there was an error deleting the task. Please try again.');
        }
    }

    // Initialize the app
    init();
});
