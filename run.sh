#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
pip install -r requirements.txt
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
