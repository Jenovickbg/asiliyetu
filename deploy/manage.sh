#!/usr/bin/env bash
set -euo pipefail
cd /opt/asili-yetu
export ASILI_ENV_FILE=/etc/asili-yetu.env
export PYTHONDONTWRITEBYTECODE=1
exec /opt/asili-yetu/.venv/bin/python -m flask --app app "$@"
