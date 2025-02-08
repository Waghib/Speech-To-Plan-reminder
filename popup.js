document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const recordingStatus = document.getElementById('recordingStatus');
    const transcribeButton = document.getElementById('transcribeButton');
    const status = document.getElementById('status');
    const output = document.getElementById('output');
    const progressContainer = document.getElementById('progressContainer');

    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let isTranscribing = false;
    let progressInterval = null;

    // Setup MediaRecorder
    async function setupRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                transcribeButton.disabled = false;
                recordingStatus.textContent = 'Recording complete. Click "Transcribe" to process.';
            };

            return true;
        } catch (error) {
            status.textContent = 'Error accessing microphone: ' + error.message;
            status.className = 'error';
            return false;
        }
    }

    // Handle record button click
    dropZone.addEventListener('click', async () => {
        if (!mediaRecorder) {
            const setup = await setupRecording();
            if (!setup) return;
        }

        if (!isRecording) {
            // Start recording
            audioChunks = [];
            mediaRecorder.start();
            isRecording = true;
            dropZone.classList.add('recording');
            dropZone.querySelector('div:nth-child(2)').textContent = 'Click to Stop Recording';
            recordingStatus.textContent = 'Recording in progress...';
            transcribeButton.disabled = true;
        } else {
            // Stop recording
            mediaRecorder.stop();
            isRecording = false;
            dropZone.classList.remove('recording');
            dropZone.querySelector('div:nth-child(2)').textContent = 'Click to Start Recording';
        }
    });

    function startProgress() {
        progressContainer.style.display = 'block';
        const progressBar = progressContainer.querySelector('.progress-bar-inner');
        let width = 0;
        return setInterval(() => {
            if (width >= 100) {
                width = 0;
            }
            width += 1;
            progressBar.style.width = width + '%';
        }, 100);
    }

    // Handle transcribe button click
    transcribeButton.addEventListener('click', async () => {
        if (audioChunks.length === 0) {
            status.textContent = 'Please record audio first.';
            status.className = 'error';
            return;
        }

        if (isTranscribing) {
            return;
        }

        isTranscribing = true;
        status.textContent = 'Starting transcription...';
        status.className = '';
        transcribeButton.disabled = true;
        output.textContent = ''; // Clear previous transcription
        progressInterval = startProgress();

        try {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const base64Audio = await blobToBase64(audioBlob);
            
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

    // Convert Blob to base64
    function blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64Data = reader.result.split(',')[1];
                resolve(base64Data);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }
});
