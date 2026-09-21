@echo off
echo ========================================
echo MA216 Quantitative Trading Dashboard
echo ========================================
echo.
echo Starting Streamlit Dashboard...
echo.
echo Dashboard will open in your browser at:
echo http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

.\.venv\Scripts\streamlit.exe run app\dashboard.py
