"""
Simple CLI for the AI MIDI Generator (headless / scripting use).

Examples:
  python cli.py generate "future bass drop" --count 3 --output /tmp/
  python cli.py preview /path/to/song.mid --limit 30
  python cli.py analyze /path/to/seed.mid

Supports the full feature set including batch and project editing via the core.
"""

import argparse
import os
from pathlib import Path

from midi_generator import (
    batch_generate, render_preview, analyze_midi_for_style,
    SongProject, project_from_spec_and_events
)

def main():
    parser = argparse.ArgumentParser(description="AI MIDI Generator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = subparsers.add_parser("generate", help="Generate MIDI from prompt")
    gen.add_argument("prompt", help="Natural language prompt")
    gen.add_argument("--count", type=int, default=1, help="Number of songs (batch)")
    gen.add_argument("--output", default="generated/", help="Output directory")
    gen.add_argument("--seed", type=int, default=None)

    # preview
    prev = subparsers.add_parser("preview", help="Render audio preview of a MIDI")
    prev.add_argument("midi", help="Path to .mid file or project")
    prev.add_argument("--limit", type=float, default=60, help="Max seconds")

    # analyze
    ana = subparsers.add_parser("analyze", help="Analyze MIDI for style reference")
    ana.add_argument("midi", help="Path to seed .mid")

    args = parser.parse_args()

    if args.command == "generate":
        os.makedirs(args.output, exist_ok=True)
        paths = batch_generate(args.prompt, count=args.count, seed=args.seed)
        for p in paths:
            dest = os.path.join(args.output, os.path.basename(p))
            if p != dest:
                import shutil
                shutil.copy(p, dest)
            print(dest)

    elif args.command == "preview":
        wav = render_preview(args.midi, seconds_limit=args.limit)
        if wav:
            print("Preview:", wav)
        else:
            print("Preview failed")

    elif args.command == "analyze":
        stats = analyze_midi_for_style(args.midi)
        print(stats)

if __name__ == "__main__":
    main()
