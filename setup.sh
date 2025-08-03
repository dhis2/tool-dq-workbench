#!/usr/bin/env bash

set -e  # Exit on error

echo "Setting up virtual environment..."

# Create virtual environment in .venv if it doesn't exist
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "Virtual environment created in .venv"
else
  echo "Virtual environment already exists."
fi

# Activate virtual environment
source .venv/bin/activate
echo "Virtual environment activated."

# Upgrade pip
pip install --upgrade pip

# Install main package in editable mode
echo "Installing dq-workbench in editable mode..."
pip install -e .

# Optionally install dev dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
  echo "Installing development dependencies..."
  pip install -r requirements.txt
else
  echo "requirements.txt not found. Skipping dev dependencies."
fi

echo "Setup complete."
echo "To activate the environment later, run: source .venv/bin/activate"

