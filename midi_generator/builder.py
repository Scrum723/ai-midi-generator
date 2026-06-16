"""
MIDIBuilder - low-level helper for constructing multi-track MIDI files.

This version is meter-aware at the metadata level (time signature, tempo)
but does not impose rhythm logic — that lives in the rhythm/melody modules.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo


@dataclass
class MIDIBuilder:
    ticks_per_beat: int = 480

    def __post_init__(self):
        self.mid = MidiFile(ticks_per_beat=self.ticks_per_beat)
        self.tracks: Dict[str, MidiTrack] = {}
        self.track_names: List[str] = []
        self._global_events: List[Tuple[int, Message]] = []  # (abs_tick, meta)
        self.tempo = 120
        self._last_tick_per_track: Dict[str, int] = {}

    def add_track(self, name: str, channel: int, program: Optional[int] = None,
                  is_drum: bool = False) -> MidiTrack:
        track = MidiTrack()
        self.mid.tracks.append(track)
        self.tracks[name] = track
        self.track_names.append(name)
        self._last_tick_per_track[name] = 0

        track.append(MetaMessage('track_name', name=name, time=0))
        ch = 9 if is_drum else channel
        if program is not None and not is_drum:
            track.append(Message('program_change', channel=ch, program=program, time=0))
        if is_drum:
            track.append(Message('program_change', channel=9, program=0, time=0))
        return track

    def set_tempo(self, bpm: int, at_tick: int = 0):
        self.tempo = bpm
        self._global_events.append((at_tick, MetaMessage('set_tempo', tempo=bpm2tempo(bpm))))

    def add_tempo_change(self, bpm: int, at_tick: int = 0):
        """Schedule a tempo change at a specific tick (supports dynamic tempo_curve)."""
        self._global_events.append((at_tick, MetaMessage('set_tempo', tempo=bpm2tempo(bpm))))

    def set_time_signature(self, num: int, den: int, at_tick: int = 0):
        self._global_events.append((at_tick, MetaMessage('time_signature', numerator=num, denominator=den)))

    def set_key_signature(self, root_semi: int, is_major: bool, at_tick: int = 0):
        key_str = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'][root_semi]
        if not is_major:
            key_str += 'm'
        if key_str == 'Dbm':
            key_str = 'C#m'
        self._global_events.append((at_tick, MetaMessage('key_signature', key=key_str)))

    def schedule_note(self, track_name: str, pitch: int, velocity: int,
                      start_tick: int, duration_ticks: int, channel: int = 0):
        if track_name not in self.tracks:
            raise ValueError(f"Unknown track: {track_name}")
        track = self.tracks[track_name]
        ch = 9 if channel == 9 else channel
        pitch = max(21, min(108, int(pitch)))
        velocity = max(1, min(127, int(velocity)))

        # Store with absolute time in .time temporarily (finalized later)
        track.append(Message('note_on', channel=ch, note=pitch, velocity=velocity, time=start_tick))
        track.append(Message('note_off', channel=ch, note=pitch, velocity=0, time=start_tick + duration_ticks))

    def add_control(self, track_name: str, control: int, value: int, at_tick: int, channel: int = 0):
        track = self.tracks[track_name]
        ch = 9 if channel == 9 else channel
        track.append(Message('control_change', channel=ch, control=control, value=value, time=at_tick))

    def _finalize_track(self, track: MidiTrack, extra_events: List[Tuple[int, Message]] = None) -> MidiTrack:
        events = []
        for msg in track:
            abs_tick = getattr(msg, 'time', 0)
            events.append((abs_tick, msg.copy(time=0)))

        if extra_events:
            events.extend(extra_events)

        events.sort(key=lambda x: x[0])

        new_track = MidiTrack()
        last = 0
        for abs_tick, msg in events:
            delta = max(0, abs_tick - last)
            msg.time = delta
            new_track.append(msg)
            last = abs_tick
        return new_track

    def finalize(self) -> MidiFile:
        all_globals = sorted(self._global_events, key=lambda x: x[0])
        new_tracks = []

        for i, name in enumerate(self.track_names):
            track = self.tracks[name]
            extras = all_globals if i == 0 else None
            new_tracks.append(self._finalize_track(track, extras))

        self.mid.tracks = new_tracks
        return self.mid

    def save(self, path: str) -> str:
        self.finalize()
        self.mid.save(path)
        return path

    def get_duration_seconds(self) -> float:
        """Best-effort duration using current tempo."""
        max_tick = 0
        for t in self.tracks.values():
            for m in t:
                max_tick = max(max_tick, getattr(m, 'time', 0))
        return mido.tick2second(max_tick, self.ticks_per_beat, bpm2tempo(self.tempo))
