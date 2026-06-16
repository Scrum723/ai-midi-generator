"""
Much better melody generation.

Goals:
- Actually melodic (good contour, tension/release)
- Respects the scale + current chord
- Has motif memory and variation
- Rhythmic interest (not just random notes)
- Different character for "Hook" vs background lead
"""

from __future__ import annotations
from typing import List, Tuple
import random
from .core import Meter
from .theory import SCALES, get_chord


def get_full_scale(root: int, scale_name: str, lowest_midi: int = 48, highest_midi: int = 84) -> List[int]:
    """Return all MIDI notes in the scale within a playable range."""
    intervals = SCALES.get(scale_name.lower(), SCALES['major'])
    notes = []
    midi = lowest_midi + (root - (lowest_midi % 12)) % 12
    if midi < lowest_midi:
        midi += 12

    while midi <= highest_midi:
        if (midi % 12) in [(root + i) % 12 for i in intervals]:
            notes.append(midi)
        midi += 1
    return notes


def generate_melody_events(
    meter: Meter,
    bar: int,
    chord_root: int,
    chord_type: str,
    key_root: int,
    scale_name: str,
    energy: float,
    mode: str,
    rng: random.Random
) -> List[Tuple[int, int, int]]:
    """
    Return list of (pulse, pitch, velocity) for the melody/lead in one bar.
    Much more musical than the previous stub.
    """
    pulses = meter.pulses_per_bar
    accents = meter.get_accent_weights()
    scale = get_full_scale(key_root, scale_name, 52, 84)
    chord_tones = set(get_chord(chord_root, chord_type, octave=5))

    events = []
    is_hook = mode == "Hook / Melody"

    # Simple motif memory (very basic version for now)
    # In a real version this would be stored on the generator object
    if not hasattr(generate_melody_events, "motif"):
        generate_melody_events.motif = []
        generate_melody_events.motif_rhythm = []

    # Occasionally create or vary a short motif (2-4 notes)
    if bar % 4 == 0 or not generate_melody_events.motif or rng.random() < 0.3:
        motif_len = rng.randint(3, 5) if is_hook else rng.randint(2, 4)
        generate_melody_events.motif = []
        generate_melody_events.motif_rhythm = []

        current = rng.choice([n for n in scale if n in chord_tones or rng.random() < 0.3])
        for _ in range(motif_len):
            generate_melody_events.motif.append(current)
            # Rhythmic values in pulses
            r = rng.choices([2, 3, 4, 6, 8], weights=[3, 2, 3, 1, 1])[0]
            generate_melody_events.motif_rhythm.append(r)

            # Move to a nearby scale tone (step or small leap)
            idx = scale.index(current) if current in scale else len(scale) // 2
            step = rng.choice([-2, -1, -1, 0, 1, 1, 2, 3])
            current = scale[max(0, min(len(scale)-1, idx + step))]

    # Play the motif (with variation) across the bar
    pos = 0
    motif_idx = 0
    variation_chance = 0.35 if is_hook else 0.2

    while pos < pulses:
        if motif_idx >= len(generate_melody_events.motif):
            motif_idx = 0

        pitch = generate_melody_events.motif[motif_idx]

        # Apply small variation on weak beats
        if rng.random() < variation_chance and accents[pos % len(accents)] < 0.6:
            idx = scale.index(pitch) if pitch in scale else len(scale)//2
            pitch = scale[max(0, min(len(scale)-1, idx + rng.choice([-1, 0, 1])))]

        # Make it more "vocal" / lyrical in hook mode
        if is_hook and rng.random() < 0.25:
            pitch += 12  # occasional octave jump for expression

        # Velocity based on accent + energy
        accent = accents[pos % len(accents)]
        vel = int(60 + 35 * energy * accent)
        vel = max(45, min(115, vel + rng.randint(-8, 8)))

        dur = generate_melody_events.motif_rhythm[motif_idx]
        # Clamp duration so we don't overflow the bar too badly
        dur = min(dur, pulses - pos)

        if dur > 0:
            events.append((pos, pitch, vel))

        pos += dur
        motif_idx += 1

    # Add some connecting notes or passing tones in hook mode for more flow
    if is_hook and len(events) >= 2 and rng.random() < 0.6:
        new_events = []
        for i, (p, pitch, vel) in enumerate(events):
            new_events.append((p, pitch, vel))
            if i < len(events) - 1:
                next_p = events[i+1][0]
                gap = next_p - (p + 2)
                if gap >= 3 and rng.random() < 0.5:
                    # insert a passing tone
                    mid = p + gap // 2
                    idx = scale.index(pitch) if pitch in scale else 0
                    passing = scale[max(0, min(len(scale)-1, idx + rng.choice([-1, 1])))]
                    new_events.append((mid, passing, vel - 15))
        events = new_events

    return sorted(events)  # just in case
