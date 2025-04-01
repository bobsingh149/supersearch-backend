#!/bin/bash
set -e

echo "Starting deployment process..."

# Pull the latest code
echo "Pulling latest code from repository..."
# Using --force to overwrite local changes with remote content
git fetch origin
git reset --hard origin/main

# Activate virtual environment
echo "Activating virtual environment..."
source supersearch-venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Kill existing worker processes
echo "Stopping existing worker processes..."
pkill -f "python app/temporal/core/run_worker.py" || echo "No worker processes running."

# Kill existing uvicorn processes
echo "Stopping existing uvicorn server..."
pkill -f "uvicorn app.main:app" || echo "No uvicorn processes running."

# Start worker process in background
echo "Starting worker process in background..."
nohup python app/temporal/core/run_worker.py > logs/cognishop_worker.log 2>&1 &

# Start uvicorn server in background
echo "Starting uvicorn server in background..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/cognishop_server.log 2>&1 &

echo "Deployment completed successfully!" 