document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const transcribeButton = document.getElementById('transcribeButton');
    const status = document.getElementById('status');
    const output = document.getElementById('output');
    const progressContainer = document.getElementById('progressContainer');

    let selectedFile = null;
    let isTranscribing = false;
    let progressInterval = null;

    // Handle drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        });
    });

    // Handle file selection via drag and drop
    dropZone.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('audio/')) {
            handleFileSelect(file);
        } else {
            status.textContent = 'Please select an audio file.';
            status.className = 'error';
        }
    });

    // Handle file selection via click
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });

    function handleFileSelect(file) {
        selectedFile = file;
        fileInfo.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
        transcribeButton.disabled = false;
        status.textContent = 'Ready to transcribe';
        status.className = '';
        output.textContent = ''; // Clear previous transcription
        progressContainer.style.display = 'none';
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function startProgress() {
        let dots = '.';
        let counter = 0;
        progressContainer.style.display = 'block';
        return setInterval(() => {
            counter++;
            dots = '.'.repeat(counter % 4);
            const timeElapsed = Math.floor(counter / 2); // 500ms intervals
            status.textContent = `Transcribing${dots} (${timeElapsed}s elapsed)`;
        }, 500);
    }

    async function pollTranscriptionStatus(retryCount = 0, maxRetries = 120) { // 2 minutes max
        if (retryCount >= maxRetries || !isTranscribing) {
            return;
        }

        try {
            const response = await fetch('http://127.0.0.1:5000/transcribe', {
                method: 'GET'
            });

            const data = await response.json();
            
            if (data.status === 'completed') {
                isTranscribing = false;
                clearInterval(progressInterval);
                progressContainer.style.display = 'none';
                output.textContent = data.transcription;
                status.textContent = 'Transcription complete';
                status.className = 'success';
                transcribeButton.disabled = false;
            } else if (data.status === 'error') {
                throw new Error(data.error || 'Transcription failed');
            } else {
                // Still processing, poll again after 1 second
                setTimeout(() => pollTranscriptionStatus(retryCount + 1), 1000);
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }

    // Handle transcribe button click
    transcribeButton.addEventListener('click', async () => {
        if (!selectedFile) {
            status.textContent = 'Please select an audio file first.';
            status.className = 'error';
            return;
        }

        isTranscribing = true;
        status.textContent = 'Starting transcription...';
        status.className = '';
        transcribeButton.disabled = true;
        output.textContent = ''; // Clear previous transcription
        progressInterval = startProgress();

        try {
            // Convert file to base64
            const base64Audio = await fileToBase64(selectedFile);
            
            // Send to server
            const response = await fetch('http://127.0.0.1:5000/transcribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ audio: base64Audio })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success) {
                isTranscribing = false;
                clearInterval(progressInterval);
                progressContainer.style.display = 'none';
                
                if (data.transcription && data.transcription.trim()) {
                    output.textContent = data.transcription;
                    status.textContent = 'Transcription complete';
                    status.className = 'success';
                } else {
                    output.textContent = 'No speech detected in the audio.';
                    status.textContent = 'No speech detected';
                    status.className = 'error';
                }
            } else {
                throw new Error(data.error || 'Failed to transcribe');
            }
        } catch (err) {
            console.error('Error:', err);
            isTranscribing = false;
            clearInterval(progressInterval);
            progressContainer.style.display = 'none';
            output.textContent = `Error: ${err.message}`;
            status.textContent = 'Error occurred';
            status.className = 'error';
        } finally {
            transcribeButton.disabled = false;
        }
    });

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
    }
});
