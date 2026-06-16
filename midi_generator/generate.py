"""
High-level song generation using SongSpec + Meter-aware components.

This is the main entry point for both the future GUI and CLI.
Currently a simplified version that proves the new architecture works.
"""

from __future__ import annotations
import random
from typing import List, Optional, Literal
from .core import SongSpec, Meter
from .theory import get_chord, roman_to_chord
from .rhythm import (
    generate_drum_events,
    generate_bass_events,
    get_pulse_duration_ticks,
    DRUM_NOTES,
)
from .melody import generate_melody_events
from .builder import MIDIBuilder

# AI integration (optional import to keep core light if no AI deps)
try:
    from .ai import generate_with_ai, apply_overrides, AIResult
    HAS_AI = True
except Exception:
    HAS_AI = False
    AIResult = None  # type: ignore

# Project model (PR1)
try:
    from .project import SongProject, TrackData, project_from_spec_and_events
    HAS_PROJECT = True
except Exception:
    HAS_PROJECT = False
    SongProject = None  # type: ignore


# Very small set of progressions for the stub
PROGRESSIONS = {
    "pop": ["I", "V", "vi", "IV"],
    "minor_pop": ["i", "VI", "III", "VII"],
    "epic": ["i", "VI", "III", "VII"],
    "techno": ["i", "i", "VI", "VII"],
}

# GM Program numbers (0-127) for the instruments we expose in the GUI
GM_PROGRAMS = {
    # Leads
    "square_lead": 80,
    "saw_lead": 81,
    "calliope": 82,
    "violin": 40,
    "trumpet": 56,
    "guitar_clean": 27,
    "guitar_overdrive": 29,
    # Harmony / Pads
    "pad_choir": 91,
    "pad_warm": 89,
    "pad_sweep": 90,
    "strings": 48,
    "electric_piano": 4,
    "organ": 16,
    # Bass
    "bass_finger": 33,
    "bass_pick": 34,
    "bass_fretless": 35,
    "bass_slap": 36,
    "square_lead": 80,   # can be used as bass too
    # "Vocals"
    "choir": 52,
    "voice": 53,
    "synth_brass": 62,
}


def _get_chord_for_bar(bar: int, key_root: int, is_major: bool, family: str) -> tuple[int, str]:
    prog = PROGRESSIONS.get(family, PROGRESSIONS["pop"])
    roman = prog[bar % len(prog)]
    return roman_to_chord(roman, key_root, is_major)


def generate_song(spec: SongSpec, output_path: str | None = None) -> str:
    """
    Generate a MIDI file from a SongSpec.
    Returns the path to the saved file.
    """
    rng = random.Random(spec.seed)

    meter = spec.meter
    ticks_per_beat = 480
    pulse_ticks = get_pulse_duration_ticks(meter, ticks_per_beat)

    builder = MIDIBuilder(ticks_per_beat=ticks_per_beat)

    # --- Setup tracks based on layers + generation mode ---
    layers = spec.layers
    mode = spec.metadata.get("generation_mode", "Full Song")

    if mode in ("Full Song", "Drum Loop", "Beat (Drums + Bass)") and layers.get("drums", type("obj", (object,), {"enabled": False})()).enabled:
        builder.add_track("Drums", channel=9, is_drum=True)

    if mode in ("Full Song", "Bass Line", "Beat (Drums + Bass)") and layers.get("bass", type("obj", (object,), {"enabled": False})()).enabled:
        bass_inst = layers["bass"].instrument or "bass_finger"
        prog = GM_PROGRAMS.get(bass_inst, 33)
        builder.add_track("Bass", channel=1, program=prog)

    if mode in ("Full Song", "Hook / Melody") and layers.get("harmony", type("obj", (object,), {"enabled": False})()).enabled:
        harm_inst = layers.get("harmony", type("obj", (object,), {"instrument": "pad_warm"})()).instrument
        prog = GM_PROGRAMS.get(harm_inst, 89)
        builder.add_track("Harmony", channel=2, program=prog)

    if mode in ("Full Song", "Hook / Melody") and layers.get("lead", type("obj", (object,), {"enabled": False})()).enabled:
        lead_inst = layers.get("lead", type("obj", (object,), {"instrument": "square_lead"})()).instrument
        prog = GM_PROGRAMS.get(lead_inst, 80)
        builder.add_track("Lead", channel=3, program=prog)

    builder.set_tempo(spec.tempo)
    builder.set_time_signature(meter.numerator, meter.denominator)

    is_major = "minor" not in spec.scale.lower()
    builder.set_key_signature(spec.key_root, is_major)

    # Dynamic tempo curve support (new key param)
    if getattr(spec, 'tempo_curve', None):
        # Approximate total ticks for positioning (rough for long songs)
        est_bars = spec.estimated_bars() if hasattr(spec, 'estimated_bars') else 64
        total_ticks_est = est_bars * meter.pulses_per_bar * get_pulse_duration_ticks(meter, 480)
        for pos, bpm in sorted(getattr(spec, 'tempo_curve', [])):
            at_tick = int(pos * total_ticks_est)
            builder.add_tempo_change(bpm, at_tick)

    # --- Very simplified section generation (one long section for the stub) ---
    mode = spec.metadata.get("generation_mode", "Full Song")

    # Adapt length and density based on generation mode
    if mode == "Full Song":
        total_bars = spec.estimated_bars()
    elif mode in ("Drum Loop", "Beat (Drums + Bass)"):
        total_bars = 16          # nice tight loop length
    elif mode == "Bass Line":
        total_bars = 12
    elif mode == "Hook / Melody":
        total_bars = 16
    else:
        total_bars = max(8, spec.estimated_bars() // 4)

    current_tick = 0
    style_hint = spec.metadata.get("style_hint", "pop")

    for bar in range(total_bars):
        pos = bar / max(1, total_bars - 1)
        energy = spec.get_energy_at(pos) * spec.density

        chord_root, chord_type = _get_chord_for_bar(
            bar, spec.key_root, is_major, spec.progression_family or "pop"
        )

        # Drums
        if "Drums" in builder.tracks:
            is_build = energy > 0.85
            drum_ev = generate_drum_events(
                meter, bar, energy, is_build, style=style_hint, swing=spec.swing, rng=rng
            )
            for p, note, vel in drum_ev:
                t = current_tick + p * pulse_ticks
                builder.schedule_note("Drums", note, vel, t, pulse_ticks * 2, channel=9)

        # Bass
        if "Bass" in builder.tracks:
            bass_ev = generate_bass_events(meter, chord_root, chord_type, energy, style=style_hint, rng=rng)
            for p, pitch, vel in bass_ev:
                t = current_tick + p * pulse_ticks
                dur = pulse_ticks * 3
                builder.schedule_note("Bass", pitch, vel, t, dur, channel=1)

        # Harmony
        if "Harmony" in builder.tracks:
            chord = get_chord(chord_root, chord_type, octave=4)
            if mode == "Hook / Melody":
                # Much more active harmony for hooks
                for p in range(0, meter.pulses_per_bar, max(1, meter.pulses_per_bar // 4)):
                    t = current_tick + p * pulse_ticks
                    for i, note in enumerate(chord[:3]):
                        builder.schedule_note("Harmony", note + (i * 12), int(50 + 20 * energy), t, pulse_ticks * 2, channel=2)
            else:
                for i, p in enumerate([0]):
                    t = current_tick + p * pulse_ticks
                    for note in chord[:3]:
                        builder.schedule_note("Harmony", note, int(55 + 25 * energy), t, pulse_ticks * meter.pulses_per_bar * 2, channel=2)

        # Lead / Hook - now using proper melodic generator
        if "Lead" in builder.tracks:
            lead_events = generate_melody_events(
                meter, bar, chord_root, chord_type,
                key_root=spec.key_root,
                scale_name=spec.scale,
                energy=energy,
                mode=mode,
                rng=rng
            )

            # Make Hook mode much more active and "vocal"
            if mode == "Hook / Melody":
                for p, pitch, vel in lead_events:
                    t = current_tick + p * pulse_ticks
                    dur = max(pulse_ticks, int(pulse_ticks * rng.uniform(1.5, 4)))
                    builder.schedule_note("Lead", pitch, vel, t, dur, channel=3)
                # Add extra passing / ornamental notes in hook mode for more life
                if rng.random() < 0.7:
                    extra_p = rng.randint(2, meter.pulses_per_bar - 2)
                    t = current_tick + extra_p * pulse_ticks
                    chord = get_chord(chord_root, chord_type, octave=5)
                    pitch = rng.choice(chord) + 12
                    builder.schedule_note("Lead", pitch, int(65 + 20 * energy), t, pulse_ticks * 2, channel=3)
            else:
                for p, pitch, vel in lead_events:
                    t = current_tick + p * pulse_ticks
                    dur = max(pulse_ticks * 2, int(pulse_ticks * rng.uniform(2.5, 5.5)))
                    builder.schedule_note("Lead", pitch, vel, t, dur, channel=3)

        current_tick += meter.pulses_per_bar * pulse_ticks

    # Add obvious expression / effects so the music isn't completely static
    if "Lead" in builder.tracks:
        # Volume automation (makes it breathe)
        for t in range(0, int(current_tick * 0.95), pulse_ticks * 4):
            val = 65 + int(30 * (0.5 + 0.5 * ((t / (current_tick or 1)) % 1)))
            builder.add_control("Lead", 7, min(127, val), t, channel=3)

        # Light panning movement
        for t in range(pulse_ticks * 2, int(current_tick * 0.8), pulse_ticks * 16):
            pan = 40 + int(40 * (0.5 + 0.5 * ((t / (current_tick or 1)) % 1)))
            builder.add_control("Lead", 10, pan, t, channel=3)  # pan

    if "Harmony" in builder.tracks:
        builder.add_control("Harmony", 91, 60, 0, channel=2)  # reverb send

    # If user chose a vocal-style instrument for lead, boost expression
    lead_inst = layers.get("lead", type("obj", (object,), {"instrument": ""})()).instrument
    if lead_inst in ("choir", "voice") and "Lead" in builder.tracks:
        # Extra volume swells for "vocal" feel
        for t in range(0, int(current_tick * 0.9), pulse_ticks * 12):
            val = 60 + int(35 * (0.5 + 0.5 * ((t / (current_tick or 1)) % 1)))
            builder.add_control("Lead", 7, min(127, val), t, channel=3)

    # Save
    if output_path is None:
        import os, time, re
        os.makedirs("generated", exist_ok=True)
        meter_str = str(meter).replace("/", "_")
        safe_name = f"song_{spec.scale}_{meter_str}_{spec.tempo}bpm_{int(time.time()*1000)}.mid"
        output_path = f"generated/{safe_name}"

    builder.save(output_path)
    return output_path


def ai_generate_song(
    prompt: str,
    base_spec: Optional[SongSpec] = None,
    mode: Literal["full", "clip", "variation"] = "full",
    bars: int = 8,
    duration_seconds: float = 32.0,
    output_path: Optional[str] = None,
    seed: Optional[int] = None,
) -> str:
    """
    High-level hybrid AI + procedural entry point.
    1. Calls LLM (or heuristic) to get creative direction + track_instructions (for precise multi-track).
    2. Applies overrides to a base SongSpec (or sensible default).
    3. Runs the full meter-aware procedural generator (events will be wrapped in SongProject in future PRs).
    Returns the path to the written .mid file.
    (PR1/2: also returns a project via side effect in metadata when HAS_PROJECT.)
    """
    if not HAS_AI:
        from .styles import PRESETS
        spec = base_spec or PRESETS.get("cinematic", SongSpec())
        if seed is not None:
            spec.seed = seed
        return generate_song(spec, output_path=output_path)

    ai_res: AIResult = generate_with_ai(
        prompt=prompt,
        base_spec=base_spec,
        mode=mode,
        bars=bars,
        duration_seconds=duration_seconds,
    )

    if base_spec is None:
        from .styles import PRESETS
        base_spec = PRESETS.get("cinematic", SongSpec())

    if ai_res.spec_overrides:
        spec = apply_overrides(base_spec, ai_res.spec_overrides)
    else:
        spec = base_spec

    if seed is not None:
        spec.seed = seed
    elif spec.seed is None:
        import time
        spec.seed = int(time.time()) % 1_000_000

    # store some AI metadata for later inspection (incl. track instructions from analysis)
    spec.metadata = spec.metadata or {}
    spec.metadata["ai_prompt"] = prompt
    spec.metadata["ai_provider"] = ai_res.provider
    spec.metadata["ai_model"] = ai_res.model
    spec.metadata["ai_used_fallback"] = ai_res.used_fallback
    if ai_res.analysis:
        spec.metadata["ai_track_instructions"] = ai_res.analysis.track_instructions
        spec.metadata["ai_overall_vibe"] = ai_res.analysis.overall_vibe

    # PR1/2: create a project wrapper (events populated by later generator improvements)
    if HAS_PROJECT:
        # For now events are empty; procedural still owns rendering. Future: generators return events -> project.
        dummy_events = {}
        proj = project_from_spec_and_events(prompt[:40] or "ai-gen", spec, dummy_events, prompt=prompt)
        spec.metadata["project_name"] = proj.name   # consumer can load via project system
        # In a full PR2 the return would be the .mid path + side project; here we keep backward compat on return type.

    path = generate_song(spec, output_path=output_path)
    return path


def batch_generate(
    prompt: str,
    count: int = 5,
    base_spec: Optional[SongSpec] = None,
    **ai_kwargs
) -> List[str]:
    """
    Generate N complete songs from the same prompt (with variation via seed/randomness).
    Performance note: for count=30, LLM is called per item (can be slow/expensive).
    Use lower temperature or force heuristic for large batches if needed.
    Returns list of .mid paths. No quality degradation because each uses full pipeline.
    """
    paths = []
    for i in range(count):
        seed = (ai_kwargs.get("seed") or 0) + i * 9973  # good spread
        p = ai_generate_song(
            prompt,
            base_spec=base_spec,
            seed=seed,
            **{k: v for k, v in ai_kwargs.items() if k != "seed"}
        )
        paths.append(p)
        print(f"Batch {i+1}/{count} -> {p}")
    return paths


if __name__ == "__main__":
    # Quick smoke test
    from .styles import PRESETS, COMMON_METERS

    spec = PRESETS["pop"]
    spec.meter = COMMON_METERS[0]  # 4/4
    spec.seed = 42
    path = generate_song(spec)
    print(f"Generated: {path}")
    print("Try changing spec.meter to other COMMON_METERS and re-run!")

    # AI smoke (will be heuristic unless key configured)
    if HAS_AI:
        p = ai_generate_song("uplifting future bass 128bpm with bright supersaw lead", mode="full", duration_seconds=45)
        print("AI hybrid generated:", p)
    else:
        print("AI not available in this env")

    # PR1 smoke: wrap a spec in a project (events empty until PR2 generators return them)
    if HAS_PROJECT:
        spec = PRESETS.get("pop", SongSpec())
        proj = project_from_spec_and_events("demo", spec, {})
        print("PR1 project wrapper OK, name=", proj.name)
    else:
        print("Project model not available yet")
