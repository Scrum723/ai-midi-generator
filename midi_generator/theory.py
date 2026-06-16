"""
Music theory helpers: notes, scales, chords, roman numeral progressions.

These functions are meter-agnostic and were the cleanest part of the original generator.
"""

from typing import List, Tuple

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_TO_SEMITONE = {n: i for i, n in enumerate(NOTE_NAMES)}

# Scale intervals (semitones from root)
SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'minor_pentatonic': [0, 3, 5, 7, 10],
    'major_pentatonic': [0, 2, 4, 7, 9],
    'blues': [0, 3, 5, 6, 7, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
}

# Chord types as semitone intervals from root
CHORD_TYPES = {
    'maj': [0, 4, 7],
    'min': [0, 3, 7],
    'dim': [0, 3, 6],
    'aug': [0, 4, 8],
    'maj7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10],
    'dom7': [0, 4, 7, 10],
    'dim7': [0, 3, 6, 9],
    'sus2': [0, 2, 7],
    'sus4': [0, 5, 7],
    '6': [0, 4, 7, 9],
    'min6': [0, 3, 7, 9],
    'add9': [0, 2, 4, 7],
    'min9': [0, 2, 3, 7, 10],
    'maj9': [0, 2, 4, 7, 11],
}

DEGREE_SEMITONES = {
    'I': 0, 'II': 2, 'III': 4, 'IV': 5, 'V': 7, 'VI': 9, 'VII': 11,
    'i': 0, 'ii': 2, 'iii': 3, 'iv': 5, 'v': 7, 'vi': 8, 'vii': 10,
    'bVII': 10, 'bVI': 8,
}


def note_name_to_midi(name: str, octave: int = 4) -> int:
    """Convert 'C#4' or ('C#', 4) style to MIDI note number (C4 = 60)."""
    if isinstance(name, str) and name and name[-1].isdigit():
        octave = int(name[-1])
        name = name[:-1]
    semitone = NOTE_TO_SEMITONE.get(name.upper().replace('b', '#').replace('♯', '#'), 0)
    return 12 * (octave + 1) + semitone


def midi_to_note_name(midi_note: int) -> str:
    octave = (midi_note // 12) - 1
    name = NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"


def get_scale_notes(root: int, scale_name: str) -> List[int]:
    """Return list of semitone offsets for one octave of the scale."""
    intervals = SCALES.get(scale_name.lower(), SCALES['major'])
    return [(root + i) % 12 for i in intervals]


def get_chord(root_semi: int, chord_type: str, octave: int = 4) -> List[int]:
    """Return MIDI note numbers for a chord."""
    intervals = CHORD_TYPES.get(chord_type, CHORD_TYPES['maj'])
    base = 12 * (octave + 1) + (root_semi % 12)
    return [base + iv for iv in intervals]


def roman_to_chord(roman: str, root_semi: int, is_major_key: bool) -> Tuple[int, str]:
    """
    Convert roman numeral (I, iv, V7, etc.) to (root_semitone, chord_type).
    """
    base = roman.upper().replace('7', '').replace('9', '')
    chord_type = 'maj'
    if roman[0].islower() or roman in ('iv', 'ii', 'iii', 'vi', 'vii'):
        chord_type = 'min'
    if '7' in roman:
        chord_type = 'dom7' if roman[0].isupper() else 'min7'
    if 'dim' in roman.lower():
        chord_type = 'dim'

    offset = DEGREE_SEMITONES.get(roman, DEGREE_SEMITONES.get(base, 0))
    if not is_major_key:
        if roman in ('III', 'VI', 'VII'):
            offset = DEGREE_SEMITONES.get(roman.lower(), offset)

    chord_root = (root_semi + offset) % 12
    return chord_root, chord_type
