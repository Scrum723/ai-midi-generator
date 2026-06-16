"""
midi_generator
Core library for generating full-length, structured MIDI songs with flexible meter support.

This package was refactored from the original single-file CLI generator to support:
- Arbitrary (common) time signatures via the Meter class
- Highly configurable SongSpec
- Clean separation for GUI, CLI, and future uses
"""

from .core import Meter, SongSpec, LayerSpec, EnergyPoint
from .theory import (
    NOTE_NAMES, NOTE_TO_SEMITONE, SCALES, CHORD_TYPES,
    note_name_to_midi, get_scale_notes, get_chord, roman_to_chord
)
from .builder import MIDIBuilder
from .ai import (
    generate_with_ai,
    apply_overrides,
    AIResult,
    SongSpecOverrides,
    ClipResponse,
    NoteEvent,
    AIConfig,
    load_config,
    save_config,
)
from .playback import MIDIPlayer, list_output_ports, find_iac_port
from .project import SongProject, TrackData, project_from_spec_and_events
from .preview import render_preview, play_preview
from .generate import ai_generate_song, generate_song, batch_generate, HAS_AI
from .ai import analyze_midi_for_style

__version__ = "0.3.0"  # Project + editable multi-track model (Phase 1)
__all__ = [
    "Meter", "SongSpec", "LayerSpec", "EnergyPoint",
    "note_name_to_midi", "get_scale_notes", "get_chord", "roman_to_chord",
    "MIDIBuilder",
    "generate_with_ai", "apply_overrides",
    "AIResult", "SongSpecOverrides", "ClipResponse", "NoteEvent",
    "AIConfig", "load_config", "save_config",
    "MIDIPlayer", "list_output_ports", "find_iac_port",
    "SongProject", "TrackData", "project_from_spec_and_events",
]