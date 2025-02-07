document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const transcribeButton = document.getElementById('transcribeButton');
    const status = document.getElementById('status');
    const output = document.getElementById('output');

    let selectedFile = null;

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
        output.textContent = ''; // Clear previous transcription
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Handle transcribe button click
    transcribeButton.addEventListener('click', async () => {
        if (!selectedFile) {
            status.textContent = 'Please select an audio file first.';
            return;
        }

        status.textContent = 'Transcribing...';
        transcribeButton.disabled = true;
        output.textContent = ''; // Clear previous transcription

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

            const data = await response.json();
            
            if (data.success) {
                if (data.transcription && data.transcription.trim()) {
                    output.textContent = data.transcription;
                    status.textContent = 'Transcription complete';
                } else {
                    output.textContent = 'No speech detected in the audio.';
                    status.textContent = 'No speech detected';
                }
            } else {
                output.textContent = 'Error: ' + (data.error || 'Failed to transcribe');
                status.textContent = 'Error occurred';
            }
        } catch (err) {
            console.error('Error:', err);
            output.textContent = 'Error: Failed to transcribe audio';
            status.textContent = 'Error occurred';
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
