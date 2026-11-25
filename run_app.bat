@echo off
REM Double-click to start GRC.AI (after first-time setup in the PDF guide)
call venv\Scripts\activate.bat
streamlit run app.py
pause
