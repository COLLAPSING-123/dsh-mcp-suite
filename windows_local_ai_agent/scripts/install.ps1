$ErrorActionPreference = "Stop"
py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Install Python 3.11+ and enable the Python Launcher." }
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path logs, state | Out-Null
Write-Host "Install complete. Copy .env.example to .env and edit it."
