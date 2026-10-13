#!/bin/bash
cd "$(dirname "$0")" || exit 1
exec ./core-orders/venv/bin/python main.py
