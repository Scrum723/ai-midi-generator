"""
Core data models: Meter (time signature abstraction) and SongSpec (full song configuration).

These are the single source of truth passed through the entire generation pipeline.
Designed to support high-quality generation for common time signatures while
remaining extensible for future exotic meters.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import math


@dataclass(frozen=True)
class Meter:
    """
    Represents a musical meter / time signature in a way that generators can use.

    Examples:
        Meter(4, 4)           # standard 4/4
        Meter(3, 4)           # waltz
        Meter(6, 8)           # compound
        Meter(5, 4, subdivision=4)  # 5/4 in quarter-note pulses
        Meter(7, 8, accent_pattern=(3,2,2))
    """
    numerator: int
    denominator: int
    subdivision: int = 16          # pulses per bar for rhythm generators (8, 12, or 16 typical)
    accent_pattern: Optional[Tuple[int, ...]] = None  # e.g. (2,2,3) for 7/8 groupings
    name: Optional[str] = None

    def __post_init__(self):
        if self.numerator < 1 or self.denominator < 1:
            raise ValueError("Invalid time signature")
        if self.subdivision not in (8, 12, 16, 24):
            # 12 and 24 useful for compound feels (6/8, 9/8 etc.)
            pass  # allow for now

    @property
    def beats_per_bar(self) -> float:
        """Number of beats (in terms of the denominator) per bar."""
        return self.numerator

    @property
    def pulses_per_bar(self) -> int:
        """Number of rhythmic pulses the generators should work with."""
        return self.subdivision

    @property
    def pulse_duration_ratio(self) -> float:
        """
        How long one pulse is relative to a 16th note in 4/4.
        Used for duration calculations when moving between meters.
        """
        # In 4/4 with sub=16, a pulse = 1/16th note
        # In 6/8 with sub=12, a pulse is an 8th note (longer)
        base = 16 / self.denominator
        return base * (4 / self.subdivision)  # rough normalization

    def is_compound(self) -> bool:
        """True for 6/8, 9/8, 12/8 etc."""
        return self.denominator == 8 and self.numerator % 3 == 0

    def get_accent_weights(self) -> List[float]:
        """
        Return a list of length `pulses_per_bar` with accent strength (0.0-1.0).
        Strong beats get higher values. Used by rhythm generators for velocity and placement.
        """
        n = self.pulses_per_bar
        weights = [0.35] * n

        if self.accent_pattern:
            # User-provided grouping, e.g. (3,2,2) for 7/8
            pos = 0
            for group_size in self.accent_pattern:
                if pos < n:
                    weights[pos] = 1.0
                pos += group_size
        else:
            # Default heuristic based on common practice
            if self.numerator == 4 and self.denominator == 4:
                # 1 and 3 strong, 2 and 4 medium
                weights[0] = 1.0
                if n >= 8:
                    weights[4] = 0.9
                if n >= 4:
                    weights[2] = 0.55
            elif self.numerator == 3 and self.denominator == 4:
                weights[0] = 1.0
                if n >= 6:
                    weights[4] = 0.6
            elif self.numerator == 5 and self.denominator == 4:
                weights[0] = 1.0
                if n >= 8:
                    weights[4] = 0.85
            elif self.numerator == 7 and self.denominator == 8:
                # Common 7/8 feels
                weights[0] = 1.0
                if n >= 6:
                    weights[3] = 0.85
                    weights[5] = 0.7
            else:
                # Generic: first pulse of each "beat" group
                step = max(1, n // max(1, self.numerator))
                for i in range(0, n, step):
                    weights[i] = 0.95

        # Slight decay for later pulses in the bar
        for i in range(1, n):
            weights[i] = max(0.2, weights[i] * (1.0 - 0.15 * (i / n)))
        return weights

    def __str__(self) -> str:
        if self.name:
            return self.name
        return f"{self.numerator}/{self.denominator}"


@dataclass
class EnergyPoint:
    """A point on the song's energy/arrangement curve (0.0 to 1.0)."""
    position: float   # 0.0 = start, 1.0 = end
    energy: float     # 0.0 = sparse/quiet, 1.0 = dense/intense


@dataclass
class LayerSpec:
    """Configuration for one musical layer/role (drums, bass, harmony, lead, etc.)."""
    enabled: bool = True
    instrument: Optional[str] = None          # GM name or program number
    density: float = 0.8                      # 0.0-1.0
    octave: int = 3
    velocity_range: Tuple[int, int] = (55, 105)
    humanization: float = 0.15                # timing/vel jitter
    swing: float = 0.0


@dataclass
class SongSpec:
    """
    Complete, serializable description of a song to generate.
    This is the main object passed from GUI/CLI into the generators.
    """
    # Identity / reproducibility
    seed: Optional[int] = None
    title: Optional[str] = None

    # Core musical parameters
    key_root: int = 0                         # 0=C, 1=C#, ..., 11=B
    scale: str = "minor"                      # major, minor, dorian, mixolydian, etc.
    meter: Meter = field(default_factory=lambda: Meter(4, 4))
    tempo: int = 120

    # Genre & style (supports sub-genres and hybrids e.g. "future_bass", "illenium_future_bass", "hybrid:lofi+cinematic")
    genre: str = "cinematic"

    # Dynamic tempo (normalized position 0-1 -> bpm). Empty = constant self.tempo
    tempo_curve: List[Tuple[float, int]] = field(default_factory=list)

    # Advanced musical constraints & feel
    groove_template: str = "straight"         # "straight", "swing", "glitch", "funk", "broken", or custom
    complexity: float = 0.5                   # 0.0-1.0 overall note/rhythm density & ornamentation
    emotional_intensity: float = 0.5          # 0.0-1.0 affects velocity expression, legato, etc.
    randomness: float = 0.3                   # 0.0-1.0 amount of stochastic variation

    # Length
    duration_seconds: Optional[float] = 280.0   # ~4.5-5 min target
    total_bars: Optional[int] = None            # alternative way to specify length

    # Global style & feel
    density: float = 0.75
    swing: float = 0.0
    humanization: float = 0.12
    energy_curve: List[EnergyPoint] = field(default_factory=lambda: [
        EnergyPoint(0.0, 0.35),
        EnergyPoint(0.15, 0.55),
        EnergyPoint(0.35, 0.92),
        EnergyPoint(0.55, 0.65),
        EnergyPoint(0.70, 0.98),
        EnergyPoint(0.82, 0.45),
        EnergyPoint(1.0, 0.25),
    ])

    # Per-layer configuration (highly customizable "any genre")
    layers: Dict[str, LayerSpec] = field(default_factory=lambda: {
        "drums": LayerSpec(enabled=True, instrument="standard", density=0.85),
        "bass": LayerSpec(enabled=True, instrument="bass_finger", density=0.75, octave=2),
        "harmony": LayerSpec(enabled=True, instrument="pad_warm", density=0.6, octave=4),
        "lead": LayerSpec(enabled=True, instrument="square_lead", density=0.55, octave=5),
    })

    # Advanced / motif controls
    motif_length_beats: int = 4
    motif_variation_probability: float = 0.35
    progression_family: str = "auto"          # pop, minor_pop, epic, techno, blues, custom...

    # Extra free-form metadata (for GUI presets, future features)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_energy_at(self, position: float) -> float:
        """Interpolate energy at normalized position [0.0, 1.0]."""
        pts = sorted(self.energy_curve, key=lambda p: p.position)
        if not pts:
            return 0.7
        if position <= pts[0].position:
            return pts[0].energy
        if position >= pts[-1].position:
            return pts[-1].energy
        for i in range(len(pts) - 1):
            if pts[i].position <= position <= pts[i + 1].position:
                t = (position - pts[i].position) / (pts[i + 1].position - pts[i].position)
                return pts[i].energy + t * (pts[i + 1].energy - pts[i].energy)
        return 0.7

    def estimated_bars(self) -> int:
        """Rough bar count for UI display."""
        if self.total_bars:
            return self.total_bars
        if self.duration_seconds and self.tempo:
            beats = (self.duration_seconds / 60.0) * self.tempo
            return max(32, int(beats / self.meter.beats_per_bar))
        return 96

    def to_dict(self) -> Dict[str, Any]:
        """Extended serialization (used by SongProject)."""
        d = {
            "seed": self.seed,
            "title": self.title,
            "key_root": self.key_root,
            "scale": self.scale,
            "meter": {"numerator": self.meter.numerator, "denominator": self.meter.denominator,
                      "subdivision": self.meter.subdivision,
                      "accent_pattern": self.meter.accent_pattern},
            "tempo": self.tempo,
            "genre": self.genre,
            "tempo_curve": self.tempo_curve,
            "groove_template": self.groove_template,
            "complexity": self.complexity,
            "emotional_intensity": self.emotional_intensity,
            "randomness": self.randomness,
            "duration_seconds": self.duration_seconds,
            "total_bars": self.total_bars,
            "density": self.density,
            "swing": self.swing,
            "humanization": self.humanization,
            "energy_curve": [{"position": p.position, "energy": p.energy} for p in self.energy_curve],
            "layers": {k: {
                "enabled": v.enabled,
                "instrument": v.instrument,
                "density": v.density,
                "octave": v.octave,
                "velocity_range": v.velocity_range,
                "humanization": v.humanization,
                "swing": v.swing,
            } for k, v in self.layers.items()},
            "motif_length_beats": self.motif_length_beats,
            "motif_variation_probability": self.motif_variation_probability,
            "progression_family": self.progression_family,
            "metadata": self.metadata,
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SongSpec":
        """Roundtrippable constructor (used by SongProject)."""
        meter_d = d.get("meter", {"numerator": 4, "denominator": 4, "subdivision": 16})
        meter = Meter(
            numerator=meter_d.get("numerator", 4),
            denominator=meter_d.get("denominator", 4),
            subdivision=meter_d.get("subdivision", 16),
            accent_pattern=meter_d.get("accent_pattern"),
        )
        energy = [EnergyPoint(**p) for p in d.get("energy_curve", [])] or cls.__dataclass_fields__["energy_curve"].default_factory()
        layers = {}
        for k, ld in d.get("layers", {}).items():
            layers[k] = LayerSpec(
                enabled=ld.get("enabled", True),
                instrument=ld.get("instrument"),
                density=ld.get("density", 0.8),
                octave=ld.get("octave", 3),
                velocity_range=tuple(ld.get("velocity_range", (55, 105))),
                humanization=ld.get("humanization", 0.15),
                swing=ld.get("swing", 0.0),
            )
        return cls(
            seed=d.get("seed"),
            title=d.get("title"),
            key_root=d.get("key_root", 0),
            scale=d.get("scale", "minor"),
            meter=meter,
            tempo=d.get("tempo", 120),
            genre=d.get("genre", "cinematic"),
            tempo_curve=d.get("tempo_curve", []),
            groove_template=d.get("groove_template", "straight"),
            complexity=d.get("complexity", 0.5),
            emotional_intensity=d.get("emotional_intensity", 0.5),
            randomness=d.get("randomness", 0.3),
            duration_seconds=d.get("duration_seconds"),
            total_bars=d.get("total_bars"),
            density=d.get("density", 0.75),
            swing=d.get("swing", 0.0),
            humanization=d.get("humanization", 0.12),
            energy_curve=energy,
            layers=layers or cls.__dataclass_fields__["layers"].default_factory(),
            motif_length_beats=d.get("motif_length_beats", 4),
            motif_variation_probability=d.get("motif_variation_probability", 0.35),
            progression_family=d.get("progression_family", "auto"),
            metadata=d.get("metadata", {}),
        )
