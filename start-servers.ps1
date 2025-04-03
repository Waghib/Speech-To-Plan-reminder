# PowerShell script to start both Python and Node.js servers

Write-Host "Starting Speech-To-Plan Reminder Servers..." -ForegroundColor Green

# Start Python server in a new PowerShell window
Start-Process powershell -ArgumentList "-Command", "cd '$PSScriptRoot'; python main.py; Read-Host 'Press Enter to exit'"

# Wait a moment for Python server to initialize
Start-Sleep -Seconds 3

# Start Node.js server in a new PowerShell window
Start-Process powershell -ArgumentList "-Command", "cd '$PSScriptRoot\node-server'; npm start; Read-Host 'Press Enter to exit'"

Write-Host "Both servers have been started in separate windows." -ForegroundColor Green
Write-Host "Python server is running on http://localhost:8000" -ForegroundColor Cyan
Write-Host "Node.js server is running on http://localhost:3000" -ForegroundColor Cyan
Write-Host "The frontend should connect to the Node.js server at http://localhost:3000" -ForegroundColor Yellow
Write-Host "
ACCESS OPTIONS:" -ForegroundColor Magenta
Write-Host "1. Chrome Extension: Load the extension from the 'extension' directory" -ForegroundColor White
Write-Host "2. Web Interface: Open http://localhost:3000 in your browser" -ForegroundColor White
