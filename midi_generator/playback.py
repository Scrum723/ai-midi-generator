"""
Real-time MIDI playback engine using python-rtmidi.

Designed for "send generated clip / song live into DAW via IAC or other virtual port".

- Non-blocking play (threaded)
- Supports constant tempo (sufficient for most generated material)
- Sends program changes, notes, basic control
- Can loop a clip
- Port discovery helpers

Usage (from GUI or CLI):
    from midi_generator.playback import list_output_ports, MIDIPlayer
    ports = list_output_ports()
    player = MIDIPlayer(port_name="IAC Driver Bus 1")
    player.play_midi_file("generated/foo.mid", loop=True)
    ...
    player.stop()
"""

from __future__ import annotations
import time
import threading
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

try:
    import rtmidi
    from rtmidi.midiconstants import NOTE_ON, NOTE_OFF, PROGRAM_CHANGE, CONTROL_CHANGE
    HAS_RTMIDI = True
except Exception:
    HAS_RTMIDI = False
    # stubs for type checkers / no-rtmidi envs
    rtmidi = None  # type: ignore
    NOTE_ON = 0x90
    NOTE_OFF = 0x80
    PROGRAM_CHANGE = 0xC0
    CONTROL_CHANGE = 0xB0

import mido
from mido import MidiFile, Message, MetaMessage


def list_output_ports() -> List[str]:
    """Return available MIDI output port names (human friendly)."""
    if not HAS_RTMIDI:
        return ["(rtmidi not installed)"]
    try:
        midiout = rtmidi.MidiOut()
        ports = midiout.get_ports()
        midiout.delete()
        return ports or ["(no MIDI output ports found)"]
    except Exception as e:
        return [f"(error enumerating ports: {e})"]


def find_iac_port() -> Optional[str]:
    """Best-effort find a likely IAC / virtual bus on macOS."""
    for name in list_output_ports():
        n = name.lower()
        if "iac" in n or "bus" in n or "virtual" in n or "inter" in n:
            return name
    return None


class MIDIPlayer:
    """
    Threaded real-time MIDI player.
    Plays a mido MidiFile (or pre-parsed event list) out a chosen port.
    """

    def __init__(self, port_name: Optional[str] = None, callback: Optional[Callable[[str], None]] = None):
        self.port_name = port_name
        self._midiout: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._loop = False
        self._current_tempo = 120.0
        self.is_playing = False
        self.callback = callback or (lambda msg: None)  # status updates

        if HAS_RTMIDI:
            self._midiout = rtmidi.MidiOut()
            self._open_port(port_name)

    def _open_port(self, name: Optional[str]):
        if not self._midiout:
            return
        try:
            ports = self._midiout.get_ports()
            if not ports:
                self.callback("No MIDI output ports available")
                return
            idx = 0
            if name:
                for i, p in enumerate(ports):
                    if name.lower() in p.lower() or p.lower() in name.lower():
                        idx = i
                        break
            self._midiout.open_port(idx)
            self.port_name = ports[idx]
            self.callback(f"Opened: {self.port_name}")
        except Exception as e:
            self.callback(f"Failed to open MIDI port: {e}")

    def set_port(self, name: str):
        """Switch output port (stops current playback)."""
        self.stop()
        if self._midiout:
            try:
                self._midiout.close_port()
            except Exception:
                pass
        self.port_name = name
        self._open_port(name)

    def _send(self, msg: List[int]):
        if self._midiout and self._midiout.is_port_open():
            try:
                self._midiout.send_message(msg)
            except Exception:
                pass

    def _play_events(self, events: List[Dict[str, Any]], ticks_per_beat: int, loop: bool):
        """
        events: list of {'tick': int, 'msg': mido Message or dict-like}
        We convert delta ticks -> sleep seconds using current tempo.
        """
        self._stop_event.clear()
        self.is_playing = True
        self._loop = loop

        while not self._stop_event.is_set():
            abs_tick = 0
            tempo = self._current_tempo  # BPM
            us_per_beat = 60_000_000 / tempo
            ticks_per_second = (ticks_per_beat * 1_000_000) / us_per_beat

            for ev in events:
                if self._stop_event.is_set():
                    break
                target_tick = ev.get("tick", abs_tick)
                delta_ticks = max(0, target_tick - abs_tick)
                abs_tick = target_tick

                if delta_ticks > 0:
                    sleep_s = delta_ticks / ticks_per_second
                    # sleep in small chunks so we can react to stop quickly
                    slept = 0.0
                    while slept < sleep_s and not self._stop_event.is_set():
                        chunk = min(0.005, sleep_s - slept)
                        time.sleep(chunk)
                        slept += chunk

                raw = ev.get("raw") or ev.get("msg")
                if isinstance(raw, Message):
                    if raw.type == "note_on":
                        self._send([NOTE_ON | (raw.channel & 0xF), raw.note, raw.velocity])
                    elif raw.type == "note_off":
                        self._send([NOTE_OFF | (raw.channel & 0xF), raw.note, raw.velocity or 0])
                    elif raw.type == "program_change":
                        self._send([PROGRAM_CHANGE | (raw.channel & 0xF), raw.program])
                    elif raw.type == "control_change":
                        self._send([CONTROL_CHANGE | (raw.channel & 0xF), raw.control, raw.value])
                    # ignore most meta for live play
                elif isinstance(raw, dict):
                    # minimal dict form from our clip events
                    typ = raw.get("type", "note_on")
                    ch = int(raw.get("channel", 0))
                    if typ == "note_on":
                        self._send([NOTE_ON | (ch & 0xF), int(raw["note"]), int(raw.get("velocity", 80))])
                    elif typ == "note_off":
                        self._send([NOTE_OFF | (ch & 0xF), int(raw["note"]), 0])
                    elif typ == "program":
                        self._send([PROGRAM_CHANGE | (ch & 0xF), int(raw.get("program", 0))])

            if not loop or self._stop_event.is_set():
                break
            # small gap between loops
            time.sleep(0.05)

        self.is_playing = False
        self.callback("Playback stopped")

    def play_midi_file(self, path: str | Path, loop: bool = False, tempo: Optional[float] = None) -> bool:
        """Play a .mid file live. Returns True if playback thread started."""
        if not HAS_RTMIDI or not self._midiout:
            self.callback("rtmidi not available - cannot play live MIDI")
            return False
        try:
            mid = MidiFile(str(path))
        except Exception as e:
            self.callback(f"Failed to load MIDI: {e}")
            return False

        if tempo:
            self._current_tempo = float(tempo)
        else:
            # try to read first tempo meta
            for track in mid.tracks:
                for msg in track:
                    if msg.type == "set_tempo":
                        self._current_tempo = mido.tempo2bpm(msg.tempo)
                        break
                else:
                    continue
                break

        # flatten to absolute tick events (simple, ignore tempo changes mid-file for now)
        events: List[Dict[str, Any]] = []
        for track in mid.tracks:
            abs_t = 0
            for msg in track:
                abs_t += msg.time
                if msg.type in ("note_on", "note_off", "program_change", "control_change"):
                    events.append({"tick": abs_t, "msg": msg})

        # sort by tick (multi-track)
        events.sort(key=lambda e: e["tick"])

        self.stop()
        self._thread = threading.Thread(
            target=self._play_events,
            args=(events, mid.ticks_per_beat, loop),
            daemon=True,
        )
        self._thread.start()
        self.callback(f"Playing {Path(path).name} @ {self._current_tempo:.0f} BPM (loop={loop})")
        return True

    def play_events(self, events: List[Dict[str, Any]], bpm: int = 120, ticks_per_beat: int = 480, loop: bool = False):
        """Play a list of simple dict events (from AI clip or custom)."""
        if not HAS_RTMIDI or not self._midiout:
            self.callback("rtmidi not available")
            return
        self._current_tempo = float(bpm)
        # normalize to have 'tick' and 'raw'
        norm = []
        for e in events:
            tick = int(e.get("tick", e.get("start", 0) * (ticks_per_beat / 4)))  # rough if in beats
            norm.append({"tick": tick, "raw": e})
        norm.sort(key=lambda x: x["tick"])

        self.stop()
        self._thread = threading.Thread(
            target=self._play_events,
            args=(norm, ticks_per_beat, loop),
            daemon=True,
        )
        self._thread.start()
        self.callback(f"Streaming {len(events)} events @ {bpm} BPM")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.is_playing = False
        # send all notes off on all channels (panic)
        for ch in range(16):
            self._send([CONTROL_CHANGE | ch, 123, 0])  # all notes off
        self.callback("Stop requested")

    def set_tempo(self, bpm: float):
        self._current_tempo = float(bpm)

    def close(self):
        self.stop()
        if self._midiout:
            try:
                self._midiout.close_port()
            except Exception:
                pass


# Simple convenience for headless / tests
def play_file_blocking(path: str, port_name: Optional[str] = None, loop: bool = False, seconds: float = 10.0):
    """Fire-and-forget blocking play (mainly for debugging)."""
    p = MIDIPlayer(port_name=port_name)
    p.play_midi_file(path, loop=loop)
    time.sleep(seconds)
    p.stop()
    p.close()


if __name__ == "__main__":
    print("Available output ports:")
    for i, name in enumerate(list_output_ports()):
        print(f"  {i}: {name}")
    iac = find_iac_port()
    print("Best IAC guess:", iac)
    print("playback module ready (needs a real .mid and open port to do anything audible)")
