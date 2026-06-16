"""
High-Quality Audio Preview for the AI MIDI Generator.

Provides "Full Song Preview" that renders the MIDI (from project or path) to a WAV file
using fluidsynth (high quality sampled instruments via soundfont) when available,
with a functional numpy/wave fallback for basic sine/saw preview.

Usage:
    from midi_generator.preview import render_preview, play_preview
    wav_path = render_preview(midi_path_or_project, duration_limit=120)
    play_preview(wav_path)

Performance: For batch of 30, render only on demand (user clicks preview for selected).
No degradation: same generator used.

Requires optional: fluidsynth binary (brew install) + soundfont (auto-download small GM if missing).
Fallback always works (uses wave + numpy for simple synth).
"""

from __future__ import annotations
import os
import subprocess
import tempfile
import wave
import struct
import math
from pathlib import Path
from typing import Union, Optional

import numpy as np  # for fallback synth (install if needed: pip install numpy)

from .project import SongProject
from .generate import generate_song

# Default soundfont search / download
# Note: The previous MuseScore direct link can 404. Use a reliable mirror or instruct user.
# Recommended: Download manually from https://github.com/FluidSynth/fluidsynth/wiki/SoundFont or https://musescore.org/en/handbook/soundfonts
# A stable small GM soundfont alternative mirror (if available) or fall back gracefully.
SF2_URL = None  # Set to a working direct .sf2 URL if you have a reliable host; otherwise manual.
SF2_CACHE = Path.home() / ".cache" / "aimidi" / "FluidR3_GM.sf2"


def _ensure_soundfont() -> Optional[Path]:
    """Return path to a usable .sf2 or None."""
    # Check common locations
    candidates = [
        SF2_CACHE,
        Path("/opt/homebrew/share/fluidsynth/sf2/FluidR3_GM.sf2"),
        Path("/usr/local/share/fluidsynth/sf2/FluidR3_GM.sf2"),
        Path.home() / "Library" / "Audio" / "Sounds" / "Banks" / "FluidR3_GM.sf2",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Try to download if URL is set (user can pre-place)
    if SF2_URL:
        try:
            SF2_CACHE.parent.mkdir(parents=True, exist_ok=True)
            import urllib.request
            print("Downloading soundfont for high-quality preview (one-time)...")
            urllib.request.urlretrieve(SF2_URL, SF2_CACHE)
            if SF2_CACHE.exists():
                return SF2_CACHE
        except Exception as e:
            print(f"Soundfont download failed ({e}).")
    else:
        print("No SF2_URL configured. For best preview quality: brew install fluidsynth && place a GM .sf2 at ~/.cache/aimidi/FluidR3_GM.sf2 (or update SF2_CACHE). Falling back to basic synth preview.")
    return None


def _render_with_fluidsynth(midi_path: Path, wav_path: Path, sf2: Path, fs: int = 44100) -> bool:
    """Use fluidsynth binary for high-quality render."""
    try:
        cmd = [
            "fluidsynth",
            "-F", str(wav_path),
            "-r", str(fs),
            "-ni",
            str(sf2),
            str(midi_path),
        ]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        return wav_path.exists() and wav_path.stat().st_size > 1000
    except Exception as e:
        print(f"fluidsynth render failed: {e}")
        return False


def _render_fallback_synth(midi_path: Path, wav_path: Path, fs: int = 44100, seconds_limit: float = 120.0) -> bool:
    """
    Very basic fallback: parse MIDI roughly and synthesize with sine/saw per track.
    Low quality but always works and gives an "instant preview" idea of structure/timing.
    """
    try:
        import mido
        mid = mido.MidiFile(str(midi_path))
        # Very crude: collect note ons with approx timing
        events = []
        tempo = 500000  # us per beat default
        ticks_per_beat = mid.ticks_per_beat
        for track in mid.tracks:
            abs_time = 0.0
            for msg in track:
                abs_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                if msg.type == 'note_on' and msg.velocity > 0:
                    events.append((abs_time, msg.note, msg.velocity, 0))  # simple saw for lead-ish
                if msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # simplistic, we ignore offs for demo length
                    pass
        if not events:
            # generate a simple tone
            events = [(0.0, 60, 80, 0)]

        duration = min(seconds_limit, max(e[0] for e in events) + 4.0)
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        audio = np.zeros_like(t)

        for start, note, vel, _ in events[:200]:  # limit for speed
            freq = 440 * 2 ** ((note - 69) / 12.0)
            # simple saw + sine mix
            phase = 2 * np.pi * freq * (t - start)
            phase = np.where(t < start, 0, phase)
            saw = 2 * (phase / (2*np.pi) - np.floor(0.5 + phase / (2*np.pi)))
            env = np.exp(-np.maximum(0, t - start) * 2.5) * (vel / 127.0)
            audio += 0.3 * saw * env + 0.15 * np.sin(phase) * env

        # normalize + fade
        audio = audio / (np.max(np.abs(audio)) + 1e-9)
        audio *= 0.9
        # simple fade out
        fade = min(int(fs * 1.0), len(audio))
        audio[-fade:] *= np.linspace(1, 0, fade)

        # write WAV
        with wave.open(str(wav_path), 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fs)
            wf.writeframes((audio * 32767).astype(np.int16).tobytes())
        return True
    except Exception as e:
        print(f"Fallback synth preview failed: {e}")
        return False


def render_preview(
    midi_or_project: Union[str, Path, SongProject],
    output_wav: Optional[Path] = None,
    seconds_limit: float = 120.0,
) -> Optional[Path]:
    """
    Render a full song preview to WAV.
    Returns path to WAV (or None on total failure).
    Uses fluidsynth if possible for high quality; falls back to basic synth.
    """
    if isinstance(midi_or_project, (SongProject,)):
        # generate a temp midi from the project if it has no file
        proj: SongProject = midi_or_project
        with tempfile.TemporaryDirectory() as td:
            tmp_mid = Path(td) / "preview.mid"
            # prefer project export if it has events, else fall back to spec render
            if any(td.events for td in proj.tracks.values()):
                proj.export_full_midi(tmp_mid)
            else:
                # trigger generation from spec (uses current generators)
                generate_song(proj.spec, output_path=str(tmp_mid))
            midi_path = tmp_mid
    else:
        midi_path = Path(midi_or_project)

    if not midi_path.exists():
        print("No MIDI to preview.")
        return None

    if output_wav is None:
        output_wav = Path(tempfile.mktemp(suffix=".wav", prefix="aimidi_preview_"))

    sf2 = _ensure_soundfont()
    if sf2 and _render_with_fluidsynth(midi_path, output_wav, sf2):
        print(f"High-quality preview rendered via fluidsynth: {output_wav}")
        return output_wav

    if _render_fallback_synth(midi_path, output_wav, seconds_limit=seconds_limit):
        print(f"Basic synth preview rendered (install fluidsynth for better quality): {output_wav}")
        return output_wav

    print("Preview rendering failed.")
    return None


def play_preview(wav_path: Path):
    """Simple playback of the preview WAV (macOS afplay or pyaudio)."""
    if not wav_path or not Path(wav_path).exists():
        print("No preview file.")
        return
    try:
        subprocess.run(["afplay", str(wav_path)], check=False)
    except Exception:
        # fallback attempt with pyaudio if installed
        try:
            import pyaudio
            import wave
            wf = wave.open(str(wav_path), 'rb')
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pa.get_format_from_width(wf.getsampwidth()),
                             channels=wf.getnchannels(),
                             rate=wf.getframerate(),
                             output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception as e:
            print(f"Could not play preview: {e}. File is at {wav_path}")


if __name__ == "__main__":
    # Demo
    from midi_generator.generate import ai_generate_song
    mid = ai_generate_song("chill future bass drop", duration_seconds=20, seed=7)
    wav = render_preview(mid)
    if wav:
        print("Preview file ready:", wav)
        # play_preview(wav)  # would block
