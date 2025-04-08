# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptPath

# Function to start a process in a new window
function Start-ProcessInNewWindow {
    param([string]$FilePath, [string]$Arguments, [string]$WindowTitle)
    
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "& { Write-Host 'Starting $WindowTitle...' -ForegroundColor Green; Set-Location '$scriptPath'; $FilePath $Arguments }"
    ) -WindowStyle Minimized
}

Write-Host "Starting Job Description Parser..." -ForegroundColor Cyan
Write-Host "Backend will be available at: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend will be available at: http://localhost:8080" -ForegroundColor Yellow
Write-Host "Press Ctrl+C in respective windows to stop the servers" -ForegroundColor Yellow

# Start Backend Server
try {
    Start-ProcessInNewWindow -FilePath "uvicorn" -Arguments "backend.main:app --reload --host 0.0.0.0 --port 8000" -WindowTitle "Backend Server"
    Start-Sleep -Seconds 2
} catch {
    Write-Host "Error starting backend server: $_" -ForegroundColor Red
    exit 1
}

# Start Frontend Server
try {
    Start-ProcessInNewWindow -FilePath "python" -Arguments "-m http.server 8080 --directory frontend" -WindowTitle "Frontend Server"
    Start-Sleep -Seconds 2
} catch {
    Write-Host "Error starting frontend server: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`nServers are starting..." -ForegroundColor Green
Write-Host "1. Backend server window will appear minimized" -ForegroundColor Green
Write-Host "2. Frontend server window will appear minimized" -ForegroundColor Green
Write-Host "3. You can maximize the windows to see the server logs" -ForegroundColor Green
Write-Host "4. Access the application at http://localhost:8080" -ForegroundColor Cyan
Write-Host "5. Close the server windows when you're done" -ForegroundColor Yellow 