# AI MIDI Generator

A powerful AI-powered MIDI generator as a standalone desktop application that seamlessly integrates with major digital audio workstations (Ableton Live, FL Studio, Logic Pro, Pro Tools, Cubase, etc.).

## Features

- **Intelligent Multi-Track Composition**: Generate complete, musically coherent songs with melodies, harmonies, rhythms, basslines, chords, arpeggios, and countermelodies.
- **Precise Prompt Adherence**: Natural language prompts for detailed styles (e.g., "melancholic future bass with emotional piano leads, heavy sub bass, glitchy percussion, and a soaring supersaw drop in the style of Illenium").
- **Full Song Editing & Control** (the most important #3): Adjust, regenerate, or fine-tune any individual track or element (melody, rhythm, velocity, modulation, note density, etc.) after generation in real time. Edit note lists directly, apply params, humanize, targeted AI regen per track. All backed by in-memory SongProject + TrackData.
- **Workflow Management**: Save and organize projects (JSON + sidecar MIDI), edit generations, export MIDI files (individual tracks or full multi-track sessions) compatible with all major DAWs, drag-and-drop export and session templates. Export Stems per-track.
- **High-Quality Audio Preview**: Instant "Full Song Preview" renders a realistic audio sample using built-in synthesis (fluidsynth if available) or sampled fallback instruments.
- **Batch Generation**: Generate up to 30 complete songs in a single batch with no degradation in quality, complexity or coherence (each independent full pipeline run).
- **Style References**: Upload MIDI or describe artist/style influences (analyze feeds into prompt + base spec).
- **Variation Controls**: Amount of randomness, complexity level, emotional intensity via sliders + genre/hybrid text.
- **Humanization Options**: Swing, velocity variation, timing imperfections (per-track Humanize button + global).
- **Stem Separation**: Individual track rendering and export.
- **DAW Integration**: Live MIDI streaming via IAC (macOS) or virtual ports for plugin-like experience without native VST build. "Stream to DAW" loops the (edited) material directly into your DAW timeline.
- **Hybrid AI**: LLM (OpenAI/Anthropic/Ollama/Groq/xAI via instructor) for prompt ease and precise adherence + enhanced procedural engine (Meter/SongSpec aware generators for odd meters 5/4 7/8 etc.) for coherent long-form songs. Optional local ML stub (`ml.py`).
- **Packaged App**: Complete macOS .app bundle via py2app (double-clickable, debuggable).
- **VST Bridge**: `vst/ai_midi_bridge.py` for thin VST integration (JUCE or protoplug Lua).
- **CLI + Tests**: Full CLI and 20+ passing comprehensive tests covering editing, batch, AI, project roundtrips, export validity, preview, humanize, etc.

All core decisions from the plan implemented, especially #3 Full Song Editing & Control with real-time in-memory edits.

## Quick Start

### 1. Clone and Run from Source (recommended for dev)

```bash
git clone https://github.com/Scrum723/ai-midi-generator.git
cd ai-midi-generator

# Create venv + install (macOS example)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional for high-quality audio preview
brew install fluidsynth

# Run the GUI
./run_app.sh
# or: python -m gui.app
```

In the app:
- Type a detailed prompt in the big text box.
- Optionally set Genre/hybrid, variation sliders, key, meter (incl. 5/4, 7/8), BPM, duration.
- Click **🤖 GENERATE WITH AI** (uses LLM or solid heuristic fallback).
- Use **Track Editor** (right side after gen): select track, edit the "pitch start dur vel" lines, tweak density/octave/instr/instructions, hit Apply/Regen This Track/Humanize.
- **Save Project** (persists edits + spec + history to ~/AI-MIDI-Projects/*.json).
- **Export Stems**, Reveal in Finder, Open in GarageBand.
- **▶ Full Song Audio Preview** (renders WAV + plays).
- Live MIDI panel: pick IAC port (enable in Audio MIDI Setup first), Stream to DAW (arm MIDI track in DAW to record the stream).

### 2. Build and Install the Packaged macOS .app

```bash
./build_app.sh
```

The .app appears in `dist/AI-MIDI-Generator.app`.

Copy to Applications:

```bash
cp -R dist/AI-MIDI-Generator.app /Applications/
```

Double-click to launch.

**Debugging packaged app** (per py2app user guide):

If it shows a generic error dialog on launch:

```bash
cd ai-midi-generator
dist/AI-MIDI-Generator.app/Contents/MacOS/AI-MIDI-Generator
```

This prints real tracebacks to terminal. Common issues (already fixed in this repo):
- Missing tkinter / charset_normalizer in frozen bundle → setup.py includes/packages updated.
- Early rtmidi C-ext / GIL crash in _build_ui → port enumeration deferred to runtime "↻ Refresh" button + sensible IAC defaults.

Rebuild with `./build_app.sh` (it cleans build/dist first) after edits.

### CLI

```bash
python cli.py generate "aggressive techno 132bpm driving bass" --count 3 --output /tmp/
python cli.py preview generated/some.mid --limit 30
python cli.py analyze path/to/seed.mid
```

### Batch 30

Use the Batch count field in GUI or `--count 30` in CLI. Each song runs full quality path (no degradation).

## Requirements

- macOS (primary; IAC for live DAW, py2app packaging). Core Python works on Linux/Windows with virtual MIDI alternatives.
- Python 3.10+ (3.13 tested)
- `python-rtmidi`, `mido`, `customtkinter`, `pydantic`, `instructor`, `openai`, `anthropic`
- Optional: fluidsynth (brew) for best preview audio, torch for ML path, API keys (OPENAI_API_KEY etc.)

See requirements.txt.

## Project Structure

- `midi_generator/` — Full reusable core: SongSpec + Meter (odd meters), generators (rhythm/melody/builder), hybrid AI (ai.py + generate), SongProject/TrackData/NoteEvent (project.py for #3 editing), preview, playback (IAC), styles, theory, ml stub.
- `gui/app.py` — Complete CustomTkinter desktop with prompt, all params, Track Editor (apply/regen/humanize + live event text editing), batch, preview, stems, save project, live stream.
- `cli.py` — Scriptable CLI.
- `setup.py` + `build_app.sh` + `run_app.sh` — Packaging + run.
- `tests/test_comprehensive.py` — 20 passing tests (run before any changes).
- `vst/` — Bridge + docs for plugin path.
- `resources/` — Icon placeholder.

## Testing

All 20+ scenarios pass (models, project edit/ser/de/export stems, batch uniqueness+validity, AI track_instructions, GUI editor methods, preview, humanize, tempo_curve, etc.):

```bash
.venv/bin/python tests/test_comprehensive.py
```

## VST / Plugin Path

See `vst/README.md` and `vst/ai_midi_bridge.py`. The Python core is complete; the bridge accepts JSON for generate/edit/preview. Use from JUCE subprocess or protoplug.

## License & Credits

MIT-style. Built with the user + Grok (xAI) following the detailed original project spec. The #3 editing system, hybrid LLM+proc, IAC streaming, packaged .app, stems, batch 30, and full prompt adherence are fully realized.

Enjoy creating music!

For issues or feature requests, open on the repo.
