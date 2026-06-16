#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
echo "Starting AI MIDI Generator (hybrid LLM + procedural)..."
echo "Tip: Enable IAC Driver in Audio MIDI Setup for live streaming into your DAW."
echo "For packaged .app: python setup.py py2app (after pip install py2app)"
python -m gui.app
