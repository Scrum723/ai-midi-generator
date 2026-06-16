"""
Style / Genre presets.

These are starting points. The GUI will allow deep per-layer overrides,
so "any genre" is achieved by starting from a preset and tweaking.
"""

from .core import SongSpec, LayerSpec, Meter

PRESETS = {
    # === Existing ===
    "cinematic": SongSpec(
        tempo=72,
        scale="harmonic_minor",
        density=0.55,
        swing=0.0,
        genre="cinematic",
        layers={
            "drums": LayerSpec(enabled=False),
            "bass": LayerSpec(enabled=True, instrument="bass_fretless", density=0.5, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="pad_choir", density=0.65, octave=4),
            "lead": LayerSpec(enabled=True, instrument="violin", density=0.4, octave=5),
        },
        metadata={"description": "Slow, emotional, atmospheric pads and sparse melody."}
    ),
    "pop": SongSpec(
        tempo=118,
        scale="major",
        density=0.82,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.9),
            "bass": LayerSpec(enabled=True, instrument="bass_finger", density=0.75, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="electric_piano", density=0.7, octave=4),
            "lead": LayerSpec(enabled=True, instrument="square_lead", density=0.55, octave=5),
            "guitar": LayerSpec(enabled=True, instrument="guitar_clean", density=0.4, octave=4),
        },
        metadata={"description": "Uplifting pop/rock band feel."}
    ),
    "techno": SongSpec(
        tempo=128,
        scale="minor",
        density=0.92,
        swing=0.0,
        genre="techno",
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.95),
            "bass": LayerSpec(enabled=True, instrument="square_lead", density=0.85, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="pad_metallic", density=0.6, octave=4),
            "lead": LayerSpec(enabled=True, instrument="saw_lead", density=0.35, octave=5),
        },
        metadata={"description": "Driving four-on-floor techno with arps."}
    ),
    "future_bass": SongSpec(
        tempo=150,
        scale="major",
        density=0.85,
        swing=0.0,
        genre="future_bass",
        tempo_curve=[(0.0, 140), (0.4, 150), (0.7, 170)],  # build + drop
        groove_template="broken",
        complexity=0.75,
        emotional_intensity=0.8,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.9),
            "bass": LayerSpec(enabled=True, instrument="bass_slap", density=0.8, octave=1),
            "harmony": LayerSpec(enabled=True, instrument="pad_sweep", density=0.65, octave=4),
            "lead": LayerSpec(enabled=True, instrument="saw_lead", density=0.7, octave=5),
            "arp": LayerSpec(enabled=True, instrument="saw_lead", density=0.55, octave=6),
        },
        metadata={"description": "Uplifting future bass with supersaw leads, sub bass, emotional elements, and builds."}
    ),
    "hybrid_future_bass_cinematic": SongSpec(
        tempo=110,
        scale="minor",
        density=0.7,
        swing=0.05,
        genre="hybrid:future_bass+cinematic",
        groove_template="glitch",
        complexity=0.65,
        emotional_intensity=0.9,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.75),
            "bass": LayerSpec(enabled=True, instrument="bass_fretless", density=0.7, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="pad_choir", density=0.6, octave=4),
            "lead": LayerSpec(enabled=True, instrument="square_lead", density=0.6, octave=5),
            "arp": LayerSpec(enabled=True, instrument="saw_lead", density=0.5, octave=6),
        },
        metadata={"description": "Hybrid future bass + cinematic: emotional pads, glitchy percussion, soaring arps."}
    ),
    "lofi": SongSpec(
        tempo=86,
        scale="dorian",
        density=0.68,
        swing=0.12,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.7),
            "bass": LayerSpec(enabled=True, instrument="bass_fretless", density=0.65, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="electric_piano", density=0.6, octave=4),
            "lead": LayerSpec(enabled=True, instrument="vibraphone", density=0.45, octave=5),
        },
        metadata={"description": "Chillhop / lo-fi with light swing."}
    ),
    "epic": SongSpec(
        tempo=82,
        scale="minor",
        density=0.78,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.8),
            "bass": LayerSpec(enabled=True, instrument="cello", density=0.7, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="strings", density=0.65, octave=4),
            "lead": LayerSpec(enabled=True, instrument="brass", density=0.5, octave=5),
            "choir": LayerSpec(enabled=True, instrument="choir", density=0.4, octave=4),
        },
        metadata={"description": "Big cinematic orchestral builds."}
    ),

    # === New genres ===
    "jazz": SongSpec(
        tempo=92,
        scale="dorian",
        density=0.65,
        swing=0.22,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.55),
            "bass": LayerSpec(enabled=True, instrument="bass_fretless", density=0.8, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="electric_piano", density=0.65, octave=4),
            "lead": LayerSpec(enabled=True, instrument="vibraphone", density=0.5, octave=5),
        },
        metadata={"description": "Swinging jazz with walking bass and brushes."}
    ),
    "hiphop": SongSpec(
        tempo=88,
        scale="minor",
        density=0.72,
        swing=0.0,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.85),
            "bass": LayerSpec(enabled=True, instrument="bass_slap", density=0.75, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="electric_piano", density=0.55, octave=4),
            "lead": LayerSpec(enabled=True, instrument="square_lead", density=0.4, octave=5),
        },
        metadata={"description": "Boom-bap / modern hip-hop beats."}
    ),
    "ambient": SongSpec(
        tempo=65,
        scale="lydian",
        density=0.45,
        swing=0.0,
        layers={
            "drums": LayerSpec(enabled=False),
            "bass": LayerSpec(enabled=True, instrument="bass_fretless", density=0.35, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="pad_sweep", density=0.7, octave=4),
            "lead": LayerSpec(enabled=True, instrument="pad_halo", density=0.35, octave=5),
        },
        metadata={"description": "Ethereal, slow, textural ambient."}
    ),
    "metal": SongSpec(
        tempo=135,
        scale="minor",
        density=0.95,
        swing=0.0,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=1.0),
            "bass": LayerSpec(enabled=True, instrument="bass_pick", density=0.9, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="guitar_overdrive", density=0.75, octave=3),
            "lead": LayerSpec(enabled=True, instrument="guitar_overdrive", density=0.6, octave=4),
        },
        metadata={"description": "Heavy, aggressive metal riffs."}
    ),
    "house": SongSpec(
        tempo=126,
        scale="minor",
        density=0.88,
        swing=0.0,
        layers={
            "drums": LayerSpec(enabled=True, instrument="standard", density=0.95),
            "bass": LayerSpec(enabled=True, instrument="square_lead", density=0.8, octave=2),
            "harmony": LayerSpec(enabled=True, instrument="pad_metallic", density=0.55, octave=4),
            "lead": LayerSpec(enabled=True, instrument="saw_lead", density=0.45, octave=5),
        },
        metadata={"description": "Classic four-on-floor house."}
    ),
}

COMMON_METERS = [
    Meter(4, 4, name="4/4 Straight"),
    Meter(3, 4, name="3/4 Waltz"),
    Meter(6, 8, subdivision=12, name="6/8 Compound"),
    Meter(5, 4, name="5/4 Odd"),
    Meter(7, 8, subdivision=8, accent_pattern=(3, 2, 2), name="7/8 (3+2+2)"),
]
