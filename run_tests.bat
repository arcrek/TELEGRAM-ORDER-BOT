@echo off
REM Activate virtual environment and run tests
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo Warning: Virtual environment not found. Make sure to activate it manually.
)

echo Running pytest...
python -m pytest tests/ -v --tb=short

