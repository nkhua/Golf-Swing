#!/usr/bin/env bash
set -euo pipefail

repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repoRoot"

echo "=== Golf Swing Setup ==="

if [ ! -d "backend/venv" ]; then
  echo "Creating backend Python virtual environment..."
  python3 -m venv backend/venv
else
  echo "Backend virtual environment already exists."
fi

source backend/venv/bin/activate

echo "Installing backend dependencies..."
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

echo "Installing mobile dependencies..."
npm install --prefix mobile

echo "Setup complete. To run the backend:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn main:app --reload --host 0.0.0.0 --port 8000"
