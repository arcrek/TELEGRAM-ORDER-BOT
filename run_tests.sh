#!/bin/bash
# Activate virtual environment and run tests

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Virtual environment activated"
else
    echo "Warning: Virtual environment not found. Make sure to activate it manually."
fi

echo "Running pytest..."
python -m pytest tests/ -v --tb=short

