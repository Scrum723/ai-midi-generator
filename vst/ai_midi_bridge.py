"""
Simple Python bridge for VST/plugin integration.

This can be run as a headless service:
  python ai_midi_bridge.py

A thin VST (JUCE or protoplug) can communicate via JSON over stdin/stdout or a simple socket.

For protoplug (Lua VST that can shell out or use os.execute with pipes).

Example usage from a plugin:
- Send JSON: {"action": "generate", "prompt": "future bass drop", "params": {...}}
- Receive: {"path": "/path/to/mid", "tracks": [...] } or error.

This reuses the full core (SongProject, editing, batch, preview, etc.).

For full native VST, embed this logic or call the packaged app via subprocess.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add parent to path if run from vst/
sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_generator import (
    SongProject, batch_generate, render_preview, analyze_midi_for_style,
    generate_with_ai
)

def handle_request(req: dict) -> dict:
    action = req.get("action")
    if action == "generate":
        prompt = req.get("prompt", "default composition")
        count = req.get("count", 1)
        params = req.get("params", {})
        try:
            if count > 1:
                paths = batch_generate(prompt, count=count, **params)
                return {"paths": paths, "status": "ok"}
            else:
                path = batch_generate(prompt, count=1, **params)[0]
                return {"path": path, "status": "ok"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    elif action == "analyze_midi":
        midi_path = req.get("midi_path")
        try:
            stats = analyze_midi_for_style(midi_path)
            return {"stats": stats, "status": "ok"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    elif action == "preview":
        midi_path = req.get("midi_path")
        try:
            wav = render_preview(midi_path, seconds_limit=req.get("limit", 30))
            return {"wav_path": str(wav) if wav else None, "status": "ok"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    elif action == "edit_project":
        # Example for full editing control from plugin
        project_json = req.get("project")  # serialized SongProject
        # In real, load, edit, save back
        return {"status": "not_implemented_in_bridge"}

    else:
        return {"error": f"Unknown action: {action}", "status": "error"}

def main():
    print("AI MIDI Bridge started. Reading JSON requests from stdin...", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            print(json.dumps(resp))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"error": str(e), "status": "error"}))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
