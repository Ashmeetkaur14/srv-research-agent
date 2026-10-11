# Usage:  powershell -ExecutionPolicy Bypass -File .\run.ps1 -Mode pipeline -Note "what I changed"
param([string]$Mode = "pipeline", [string]$Note = "")
if (-not $env:GEMINI_API_KEY -and -not $env:ANTHROPIC_API_KEY) { $env:GEMINI_API_KEY = Read-Host "Paste your Gemini API key (it is NOT saved anywhere)" }
if (-not $env:LLM_MODEL -and $env:GEMINI_API_KEY) { $env:LLM_MODEL = "gemini-flash-latest" }
py -m pip install -q -r requirements.txt
py -m research_agent --ticker SRVCABLE --mode $Mode --note $Note
