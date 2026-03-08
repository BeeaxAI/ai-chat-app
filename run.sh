#!/bin/bash
# AI Chat Application Launcher

set -e

echo "🚀 Starting AI Chat Application..."

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env with your API keys before running."
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d venv ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
source venv/bin/activate
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

# Create data directory
mkdir -p data

# Run
echo "✅ Starting server at http://localhost:8000"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
