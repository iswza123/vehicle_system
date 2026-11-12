#!/usr/bin/env bash
# Build script used by Render (see render.yaml)
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
