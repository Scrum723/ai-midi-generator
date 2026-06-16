# VST / Plugin Scaffold (Phase 5 completion item)

This directory contains the starter for a thin VST3/AU/AAX "AI MIDI Generator" plugin that re-uses the Python core (`midi-song-app/midi_generator`).

## Status
- Core Python engine (SongProject, AI hybrid with LLM+ML path, editing, multi-track export, IAC live, batch, audio preview, genre customization) is **complete** and the primary deliverable.
- The VST is a **defined extension path** with build notes and a ready-to-use bridge. Full native binary requires:
  - Full Xcode (not just CLT) + Apple Developer certificate for signing/notarization.
  - JUCE (or alternative such as iPlug2 / protoplug for lighter Lua bridge).

## Recommended Architecture (thin host)
1. C++ VST (JUCE) that presents a small UI:
   - Text box for the natural language prompt.
   - Buttons: Generate, Regen Track X, Export Stems, Stream (IAC), Batch.
2. The plugin calls the Python engine via one of:
   - **Embedded Python**.
   - **Subprocess / IPC** to the packaged .app or the bridge below.
   - **DAWNet-style** or Max-for-Live style bridge.

The Python side already exposes the exact API needed (see ai_midi_bridge.py for a ready JSON protocol).

## ai_midi_bridge.py - Ready-to-use bridge
Run this as a service or call it from your plugin:

```bash
python vst/ai_midi_bridge.py
```

It accepts JSON on stdin, e.g.:
```json
{"action": "generate", "prompt": "melancholic future bass...", "count": 1}
```
Returns paths, stats, preview WAVs, etc.

Supports the full feature set including editing via SongProject.

Integrate by shelling out or using pipes from your VST code.

## Quick Start (when you have a build machine with full Xcode)
See the example in the old README section above (subprocess to ai_generate_song or the bridge).

## protoplug / Lua lighter alternative (works today)
Install protoplug.
Write Lua that calls `os.execute` or pipes to `python vst/ai_midi_bridge.py` and parses the JSON to send MIDI events.

Example Lua snippet (conceptual):
```lua
-- send request
-- read response JSON
-- for each note in response, send MIDI
```

This gives an immediate "AI MIDI generator plugin" experience.

## Packaging notes for the Python side
- See top-level `setup.py`, `build_app.sh`, and `run_app.sh`.
- Build the .app first: `./build_app.sh`
- The bridge or direct Python calls can target the .app or the source.

## Distribution
- Standalone .app (primary).
- VST requires notarization.

## Next concrete steps (when ready)
1. Clone JUCE.
2. Add call to the bridge or direct import in a background thread.
3. Map events to host MIDI.
4. Expose per-track editing from the desktop app or inline.

The Python core is production-ready for the full plan. The VST is the integration layer.

For full details, see the session plan.md.
