#!/bin/bash
# backup.sh: Pokreće backup.py koristeći python interpreter iz virtuelnog okruženja
cd "$(dirname "$0")/.."
export PYTHONPATH=.
./venv/bin/python infra/backup.py
