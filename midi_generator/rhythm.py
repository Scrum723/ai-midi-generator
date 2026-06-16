"""
Meter-aware rhythm generation for drums, bass, and harmony.

This is the heart of supporting "any time signature" with good musical feel.
We use the Meter's pulses, accent weights, and compound/straight nature
to generate appropriate patterns instead of hard-coded 4/4 16th grids.
"""

from __future__ import annotations
from typing import List, Tuple, Dict
import random
from .core import Meter, SongSpec, LayerSpec

# Drum map (central place for now)
DRUM_NOTES = {
    'kick': 36, 'kick2': 35, 'snare': 38, 'snare2': 40,
    'closed_hat': 42, 'open_hat': 46, 'pedal_hat': 44,
    'crash': 49, 'ride': 51, 'ride_bell': 53,
    'tom1': 48, 'tom2': 45, 'tom3': 43, 'tom4': 41,
    'clap': 39, 'tamb': 54, 'cowbell': 56, 'shaker': 70,
}


def get_pulse_duration_ticks(meter: Meter, ticks_per_beat: int) -> int:
    """
    How many MIDI ticks one 'pulse' (our internal rhythmic unit) represents.
    We normalize so that in 4/4 sub=16, pulse = 16th note.
    """
    # Base: in 4/4, 4 beats per bar, 16 pulses → each pulse = 1/4 of a beat
    base_pulses_per_beat = meter.subdivision / meter.beats_per_bar
    ticks_per_pulse = ticks_per_beat / base_pulses_per_beat
    return int(ticks_per_pulse)


def generate_drum_events(
    meter: Meter,
    bar_in_section: int,
    energy: float,
    is_build: bool,
    style: str = "pop",
    swing: float = 0.0,
    rng: random.Random | None = None
) -> List[Tuple[int, int, int]]:
    """
    Return list of (pulse_index, drum_note, velocity) for one bar.
    pulse_index is 0 .. meter.pulses_per_bar-1
    """
    if rng is None:
        rng = random.Random()

    pulses = meter.pulses_per_bar
    accents = meter.get_accent_weights()
    events: List[Tuple[int, int, int]] = []
    e = max(0.35, min(1.0, energy))

    style = style.lower()

    # === 5/4 and 7/8 specific musical patterns (much better feel) ===
    if meter.numerator == 5 and meter.denominator == 4:
        # Classic 5/4 rock/prog feel (e.g. 3+2 or 2+3)
        events.append((0, DRUM_NOTES['kick'], int(110 + 12 * e)))
        events.append((pulses // 2, DRUM_NOTES['kick'], int(85 + 10 * e)))   # beat 3
        events.append((int(pulses * 0.8), DRUM_NOTES['kick'], int(70 + 8 * e)))  # pickup

        events.append((int(pulses * 0.4), DRUM_NOTES['snare'], int(95 + 10 * e)))   # beat 2.5-ish
        events.append((int(pulses * 0.6), DRUM_NOTES['snare'], int(88 + 8 * e)))    # beat 4

        for p in range(0, pulses, max(1, pulses // 10)):
            v = int(48 + 22 * e * rng.uniform(0.8, 1.0))
            events.append((p, DRUM_NOTES['closed_hat'], v))

    elif meter.numerator == 7 and meter.denominator == 8:
        # Nice 7/8 feel (3+2+2 or 2+2+3)
        events.append((0, DRUM_NOTES['kick'], int(108 + 12 * e)))
        events.append((int(pulses * 0.43), DRUM_NOTES['kick'], int(82 + 10 * e)))  # second group
        events.append((int(pulses * 0.71), DRUM_NOTES['kick'], int(78 + 8 * e)))   # third group

        events.append((int(pulses * 0.29), DRUM_NOTES['snare'], int(92 + 10 * e)))
        events.append((int(pulses * 0.57), DRUM_NOTES['snare'], int(85 + 8 * e)))

        step = max(1, pulses // 14)
        for p in range(0, pulses, step):
            v = int(45 + 20 * e)
            if accents[p] > 0.7:
                v += 15
            events.append((p, DRUM_NOTES['closed_hat'], v))

    # === Techno / Electronic (four-on-floor adapted to meter) ===
    elif style in ("techno", "electronic"):
        # Place kick on every "main beat" as much as possible
        beat_step = max(1, pulses // max(1, meter.numerator))
        for i in range(0, pulses, beat_step):
            vel = int(105 + 18 * e)
            events.append((i, DRUM_NOTES['kick'], vel))

        # Closed hats on most pulses, lighter on off-beats
        for p in range(pulses):
            v = int(52 + 25 * e * rng.uniform(0.7, 1.0))
            if accents[p] < 0.5:
                v = int(v * 0.65)
            events.append((p, DRUM_NOTES['closed_hat'], v))

        # Snare/clap on medium-strong beats
        for p in range(pulses):
            if accents[p] > 0.6 and p != 0:
                events.append((p, DRUM_NOTES['snare'], int(70 + 38 * e)))

        if is_build and bar_in_section % 2 == 0:
            events.append((pulses - 1, DRUM_NOTES['open_hat'], int(88 + 10 * e)))

    # === Pop / Rock feel ===
    elif style == "pop":
        # Kick on 1 and usually a bit before 3
        events.append((0, DRUM_NOTES['kick'], int(102 + 12 * e)))
        if pulses > 6:
            events.append((pulses // 2, DRUM_NOTES['kick'], int(88 + 10 * e)))

        # Snare on the "backbeats"
        backbeats = [pulses // 4, (3 * pulses) // 4]
        for bb in backbeats:
            if bb < pulses:
                events.append((bb, DRUM_NOTES['snare'], int(95 + 12 * e)))

        # Hats
        for p in range(0, pulses, max(1, pulses // 8)):
            v = int(65 + 18 * rng.random())
            events.append((p, DRUM_NOTES['closed_hat'], v))

        if is_build and bar_in_section % 4 == 3:
            events.append((pulses - 1, DRUM_NOTES['crash'], 100))

    # === Lo-fi / Chill with swing ===
    elif style == "lofi":
        events.append((0, DRUM_NOTES['kick'], int(82 + 15 * e)))
        if pulses > 5:
            events.append((pulses // 3 + 1, DRUM_NOTES['kick'], 60))

        # Snare on 2 and 4
        for frac in (0.25, 0.75):
            p = int(frac * pulses)
            if p < pulses:
                events.append((p, DRUM_NOTES['snare'], int(75 + 10 * e)))

        # Swingy hats
        step = max(1, pulses // 8)
        for p in range(0, pulses, step):
            v = int(45 + 20 * rng.random())
            if swing > 0 and p % 2 == 1:
                # swing moves the pulse slightly later in time (handled in scheduler)
                pass
            events.append((p, DRUM_NOTES['closed_hat'], v))

        if rng.random() < 0.35:
            events.append((int(0.4 * pulses), DRUM_NOTES['open_hat'], 50))

    # === Epic / Orchestral drums ===
    elif style == "epic":
        events.append((0, DRUM_NOTES['kick'], int(115 + 10 * e)))
        if pulses > 4:
            events.append((pulses // 3, DRUM_NOTES['kick'], 75))
        events.append((pulses // 2, DRUM_NOTES['snare'], 90))
        if pulses > 6:
            events.append((int(0.75 * pulses), DRUM_NOTES['snare'], 95))

        if is_build or bar_in_section % 4 == 0:
            events.append((0, DRUM_NOTES['crash'], 105))

        # Toms and hats for movement
        for p in range(0, pulses, max(2, pulses // 6)):
            if accents[p] > 0.4:
                events.append((p, DRUM_NOTES['closed_hat'], int(55 + 20 * e)))

    # === Cinematic / sparse / default ===
    else:
        if e > 0.55 and rng.random() < 0.6:
            events.append((0, DRUM_NOTES['kick'], int(55 + 15 * e)))
        if "chorus" in str(bar_in_section) or rng.random() < 0.25:  # rough
            p = pulses // 2
            events.append((p, DRUM_NOTES['snare'], 50))
        if rng.random() < 0.4:
            events.append((pulses // 4, DRUM_NOTES['closed_hat'], 38))

    # Deduplicate same pulse (keep loudest)
    by_pulse: Dict[int, Tuple[int, int]] = {}
    for p, note, vel in events:
        if 0 <= p < pulses:
            if p not in by_pulse or vel > by_pulse[p][1]:
                by_pulse[p] = (note, vel)

    return sorted([(p, n, v) for p, (n, v) in by_pulse.items()])


def generate_bass_events(
    meter: Meter,
    chord_root: int,
    chord_type: str,
    energy: float,
    style: str = "pop",
    rng: random.Random | None = None
) -> List[Tuple[int, int, int]]:
    """
    Return list of (pulse_index, pitch, velocity) for bass in one bar.
    """
    if rng is None:
        rng = random.Random()

    pulses = meter.pulses_per_bar
    accents = meter.get_accent_weights()
    events: List[Tuple[int, int, int]] = []
    e = max(0.4, min(1.0, energy))

    style = style.lower()

    # Root + occasional 5th or octave for interest, adapted to meter accents
    if meter.numerator in (5, 7):
        # Sparse but locked to the odd grouping
        events.append((0, 36 + chord_root, int(95 + 20 * e)))
        if pulses > 8:
            events.append((pulses // 3, 36 + chord_root + 7, int(70 + 12 * e)))
    else:
        events.append((0, 36 + chord_root, int(100 + 15 * e)))
        if pulses > 6 and accents[pulses // 2] > 0.6:
            events.append((pulses // 2, 36 + chord_root - 12, int(80 + 10 * e)))

    # Walking or pulse on off-beats for groove
    for i in range(1, pulses, max(2, pulses // 6)):
        if accents[i] > 0.45 or rng.random() < 0.3:
            v = int(60 + 25 * e * rng.uniform(0.6, 1.0))
            events.append((i, 36 + chord_root + (7 if i % 3 == 0 else 0), v))

    # Dedup
    by_p = {}
    for p, note, v in events:
        if p not in by_p or v > by_p[p][1]:
            by_p[p] = (note, v)
    return [(p, n, v) for p, (n, v) in sorted(by_p.items())]


if __name__ == "__main__":
    m = Meter(7, 8, subdivision=8, accent_pattern=(3,2,2))
    print("7/8 drums sample:", generate_drum_events(m, 0, 0.8, False, "techno"))
    print("Bass sample:", generate_bass_events(m, 0, "min", 0.7))
