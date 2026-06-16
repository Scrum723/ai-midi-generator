# AI MIDI Generator

**Complete packaged macOS .app + VST bridge for AI-powered MIDI generation in DAWs.**

## Features
- Hybrid AI (LLM + procedural) multi-track song generation
- Full editing & control per track and note level
- Audio preview (fluidsynth or fallback)
- Batch generation
- Style references from MIDI upload
- Variation, humanization, genre/hybrid support
- Export stems and full MIDI
- Live streaming to DAW via IAC
- Packaged .app
- VST integration bridge

## Install / Run

Clone this repo or download the source.

```bash
cd ai-midi-generator
source .venv/bin/activate
./run_app.sh
```

Or use the pre-built .app from releases (build with ./build_app.sh if needed).

## Build the .app

```bash
./build_app.sh
```

The app will be in dist/AI-MIDI-Generator.app

Copy to /Applications.

## CLI

```bash
python cli.py generate "chill future bass" --count 5
```

## VST / Plugin

See vst/README.md for the bridge and integration.

## Debugging Builds

If the .app doesn't launch:

```bash
dist/AI-MIDI-Generator.app/Contents/MacOS/AI-MIDI-Generator
```

See the py2app debugging guide in the code for common issues like missing tkinter or charset_normalizer (fixed in setup.py by including them) and rtmidi GIL (fixed by deferring port listing).

## Source
The full source is the midi-song-app project. This repo has the main files for public use.

Built with Grok by xAI.