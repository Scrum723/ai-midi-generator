# AI MIDI Generator

A powerful AI-powered MIDI generator as a standalone desktop application that seamlessly integrates with major digital audio workstations (Ableton Live, FL Studio, Logic Pro, Pro Tools, Cubase, etc.).

## Features

- **Intelligent Multi-Track Composition**: Generate complete, musically coherent songs with melodies, harmonies, rhythms, basslines, chords, arpeggios, and countermelodies.
- **Precise Prompt Adherence**: Natural language prompts for detailed styles (e.g., "melancholic future bass with emotional piano leads, heavy sub bass, glitchy percussion, and a soaring supersaw drop in the style of Illenium").
- **Full Song Editing & Control**: Adjust, regenerate, or fine-tune any individual track or element (melody, rhythm, velocity, modulation, note density, etc.) after generation in real time.
- **Workflow Management**: Save and organize projects, edit generations, export MIDI files (individual tracks or full multi-track sessions) compatible with all major DAWs, drag-and-drop export and session templates.
- **High-Quality Audio Preview**: Instant "Full Song Preview" renders a realistic audio sample using built-in synthesis or sampled instruments.
- **Batch Generation**: Generate up to 30 complete songs in a single batch with no degradation in quality.
- **Style References**: Upload MIDI or describe artist/style influences.
- **Variation Controls**: Amount of randomness, complexity level, emotional intensity.
- **Humanization Options**: Swing, velocity variation, timing imperfections.
- **Stem Separation**: Individual track rendering and export.
- **DAW Integration**: Live MIDI streaming via IAC (macOS) or virtual ports; packaged for plugin-like use.
- **Hybrid AI**: LLM for prompt ease and precise adherence + enhanced procedural engine (ported from advanced generators) for coherent long-form songs. Optional local ML stub for future complete song gen.
- **Packaged App**: Complete macOS .app bundle.
- **VST Bridge**: ai_midi_bridge.py for thin VST integration (JUCE or protoplug).

## Quick Start

### Run from Source

```bash
git clone https://github.com/Scrum723/ai-midi-generator.git
cd ai-midi-generator
# Set up venv and install deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run_app.sh
```

### Build and Run Packaged .app

```bash
./build_app.sh
```

Then open `dist/AI-MIDI-Generator.app` or copy to /Applications.

Double-click to launch the GUI.

### CLI

```bash
python cli.py generate "chill lofi piano over lo-fi drums" --count 5
```

## VST / Plugin

See `vst/README.md` for the bridge and integration.

## Requirements

- macOS (for IAC and packaging; core works elsewhere with adjustments)
- Python 3.13+
- For full features: fluidsynth for high-quality preview (brew install fluidsynth)
- Optional: API keys for OpenAI/Anthropic/etc for LLM (heuristic fallback works great)

## Project Structure

- `midi_generator/` : Core engine (SongSpec, Meter, generators, AI, Project editing, preview, playback, batch)
- `gui/app.py` : CustomTkinter GUI with full editing, batch, preview, style refs
- `cli.py` : Headless CLI
- `setup.py`, `build_app.sh` : py2app packaging for .app
- `vst/` : Plugin bridge and docs
- `tests/` : Comprehensive test suite

## License

MIT or as per your preference. Enjoy making music!

Built iteratively with Grok (xAI).