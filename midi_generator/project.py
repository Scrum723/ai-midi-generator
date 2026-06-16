"""
SongProject and TrackData: the canonical editable model for the AI MIDI Generator.

This provides:
- In-memory source of truth for multi-track compositions (events per track).
- Persistence (JSON project files + optional sidecar .mid).
- Editability (per-track events + params).
- Workflow (save/load, versions, templates, export stems/full).
- Seamless integration with existing SongSpec, NoteEvent, MIDIBuilder, and generators.

A SongProject is created on generation (or load), holds the spec + realized TrackData (List[NoteEvent] per logical track), and is the object passed around for editing, re-rendering, and export.

Events use the NoteEvent from .ai (beats-based, with .track for logical name).

This enables "Full Song Editing & Control" + all Workflow Management requirements while reusing the hybrid LLM + procedural engine.
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import SongSpec, LayerSpec, Meter, EnergyPoint
from .ai import NoteEvent  # reuse the Pydantic model (pitch, start, duration, velocity, track)


@dataclass
class TrackData:
    """Editable data for one logical track/layer."""
    name: str                           # e.g. "lead", "drums", "arp", "counter_melody"
    enabled: bool = True
    events: List[NoteEvent] = field(default_factory=list)  # canonical note data (source of truth)
    params: LayerSpec = field(default_factory=LayerSpec)   # per-track overrides (density, instrument, octave, vel_range, humanization, swing)
    instructions: str = ""              # from original prompt or user sub-prompt / AI directives (e.g. "emotional piano leads with leaps")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "events": [e.model_dump() for e in self.events],  # Pydantic v2
            "params": {
                "enabled": self.params.enabled,
                "instrument": self.params.instrument,
                "density": self.params.density,
                "octave": self.params.octave,
                "velocity_range": self.params.velocity_range,
                "humanization": self.params.humanization,
                "swing": self.params.swing,
            },
            "instructions": self.instructions,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrackData":
        params = LayerSpec(
            enabled=d.get("params", {}).get("enabled", True),
            instrument=d.get("params", {}).get("instrument"),
            density=d.get("params", {}).get("density", 0.8),
            octave=d.get("params", {}).get("octave", 3),
            velocity_range=tuple(d.get("params", {}).get("velocity_range", (55, 105))),
            humanization=d.get("params", {}).get("humanization", 0.15),
            swing=d.get("params", {}).get("swing", 0.0),
        )
        events = [NoteEvent(**ev) for ev in d.get("events", [])]
        return cls(
            name=d["name"],
            enabled=d.get("enabled", True),
            events=events,
            params=params,
            instructions=d.get("instructions", ""),
        )


@dataclass
class SongProject:
    """
    Top-level project container.
    - Owns the authoritative SongSpec (config) + per-track editable data.
    - Supports versioning, serialization, export, templates.
    - Created by generate flows (or loaded); UI and generators operate on it.
    """
    name: str = "Untitled"
    spec: SongSpec = field(default_factory=SongSpec)
    tracks: Dict[str, TrackData] = field(default_factory=dict)  # key = logical name (drums, bass, lead, arp, ...)
    prompt_history: List[Dict[str, Any]] = field(default_factory=list)  # [{"prompt": "...", "timestamp": , "ai_meta": {...}, "version": } ...]
    created_at: float = field(default_factory=time.time)
    current_version: int = 0

    # --- Core workflow ---

    def add_version(self, prompt: str = "", ai_meta: Optional[Dict] = None) -> int:
        """Record a generation/edit step."""
        self.current_version += 1
        entry = {
            "version": self.current_version,
            "timestamp": time.time(),
            "prompt": prompt,
            "ai_meta": ai_meta or {},
        }
        self.prompt_history.append(entry)
        return self.current_version

    def get_track(self, name: str) -> Optional[TrackData]:
        return self.tracks.get(name)

    def set_track_events(self, name: str, events: List[NoteEvent], params: Optional[LayerSpec] = None, instructions: str = ""):
        """Update (or create) a track's editable events + optional params."""
        if name not in self.tracks:
            self.tracks[name] = TrackData(name=name)
        td = self.tracks[name]
        td.events = events
        if params:
            td.params = params
        if instructions:
            td.instructions = instructions

    # --- Serialization (project.json) ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "current_version": self.current_version,
            "spec": self._spec_to_dict(),
            "tracks": {k: v.to_dict() for k, v in self.tracks.items()},
            "prompt_history": self.prompt_history,
        }

    def _spec_to_dict(self) -> Dict[str, Any]:
        """Extended version of SongSpec.to_dict (includes energy, full layers, metadata, structure hints if present)."""
        s = self.spec
        d = {
            "seed": s.seed,
            "title": s.title,
            "key_root": s.key_root,
            "scale": s.scale,
            "meter": {
                "numerator": s.meter.numerator,
                "denominator": s.meter.denominator,
                "subdivision": s.meter.subdivision,
                "accent_pattern": s.meter.accent_pattern,
            },
            "tempo": s.tempo,
            "duration_seconds": s.duration_seconds,
            "total_bars": s.total_bars,
            "density": s.density,
            "swing": s.swing,
            "humanization": s.humanization,
            "energy_curve": [{"position": p.position, "energy": p.energy} for p in s.energy_curve],
            "layers": {
                k: {
                    "enabled": v.enabled,
                    "instrument": v.instrument,
                    "density": v.density,
                    "octave": v.octave,
                    "velocity_range": v.velocity_range,
                    "humanization": v.humanization,
                    "swing": v.swing,
                }
                for k, v in s.layers.items()
            },
            "motif_length_beats": s.motif_length_beats,
            "motif_variation_probability": s.motif_variation_probability,
            "progression_family": s.progression_family,
            "metadata": s.metadata,
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SongProject":
        spec_d = d.get("spec", {})
        meter_d = spec_d.get("meter", {"numerator": 4, "denominator": 4, "subdivision": 16})
        meter = Meter(
            numerator=meter_d["numerator"],
            denominator=meter_d["denominator"],
            subdivision=meter_d.get("subdivision", 16),
            accent_pattern=meter_d.get("accent_pattern"),
        )
        energy = [EnergyPoint(**p) for p in spec_d.get("energy_curve", [])] or SongSpec.__dataclass_fields__["energy_curve"].default_factory()
        layers = {}
        for k, ld in spec_d.get("layers", {}).items():
            layers[k] = LayerSpec(
                enabled=ld.get("enabled", True),
                instrument=ld.get("instrument"),
                density=ld.get("density", 0.8),
                octave=ld.get("octave", 3),
                velocity_range=tuple(ld.get("velocity_range", (55, 105))),
                humanization=ld.get("humanization", 0.15),
                swing=ld.get("swing", 0.0),
            )
        spec = SongSpec(
            seed=spec_d.get("seed"),
            title=spec_d.get("title"),
            key_root=spec_d.get("key_root", 0),
            scale=spec_d.get("scale", "minor"),
            meter=meter,
            tempo=spec_d.get("tempo", 120),
            duration_seconds=spec_d.get("duration_seconds"),
            total_bars=spec_d.get("total_bars"),
            density=spec_d.get("density", 0.75),
            swing=spec_d.get("swing", 0.0),
            humanization=spec_d.get("humanization", 0.12),
            energy_curve=energy,
            layers=layers,
            motif_length_beats=spec_d.get("motif_length_beats", 4),
            motif_variation_probability=spec_d.get("motif_variation_probability", 0.35),
            progression_family=spec_d.get("progression_family", "auto"),
            metadata=spec_d.get("metadata", {}),
        )
        tracks = {k: TrackData.from_dict(td) for k, td in d.get("tracks", {}).items()}
        proj = cls(
            name=d.get("name", "Untitled"),
            spec=spec,
            tracks=tracks,
            prompt_history=d.get("prompt_history", []),
            created_at=d.get("created_at", time.time()),
            current_version=d.get("current_version", 0),
        )
        return proj

    def save(self, path: Path | str) -> Path:
        """Save project.json (events + spec + history). Creates parent dirs."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2))
        return p

    @classmethod
    def load(cls, path: Path | str) -> "SongProject":
        """Load from project.json."""
        data = json.loads(Path(path).read_text())
        return cls.from_dict(data)

    # --- Export (reuses builder) ---

    def export_full_midi(self, output_path: Path | str, builder=None) -> str:
        """Render current tracks/events to a single multi-track .mid (uses existing MIDIBuilder patterns)."""
        from .builder import MIDIBuilder
        from .generate import GM_PROGRAMS  # if available; fallback
        b = builder or MIDIBuilder()
        # Simple render: add tracks + schedule from events (convert beats->ticks using spec tempo)
        ticks_per_beat = 480
        tempo = self.spec.tempo or 120
        # For simplicity, assume events .start/.duration are in beats; convert using current tempo
        # (real impl would use the same pulse logic as generate_song)
        for tname, td in self.tracks.items():
            if not td.enabled or not td.events:
                continue
            is_drum = "drum" in tname.lower()
            prog = None
            if not is_drum and td.params.instrument:
                prog = GM_PROGRAMS.get(td.params.instrument) if 'GM_PROGRAMS' in globals() else None
            b.add_track(tname, channel=9 if is_drum else 1, program=prog, is_drum=is_drum)
            for ev in td.events:
                # very rough beat -> tick (assumes 4/4 for demo; real uses meter/pulses)
                start_tick = int(ev.start * ticks_per_beat)
                dur_ticks = int(ev.duration * ticks_per_beat)
                b.schedule_note(tname, ev.pitch, ev.velocity, start_tick, dur_ticks)
        b.set_tempo(tempo)
        b.set_time_signature(self.spec.meter.numerator, self.spec.meter.denominator)
        return b.save(str(output_path))

    def export_stems(self, out_dir: Path | str) -> List[str]:
        """Export one .mid per enabled track (stems)."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for tname, td in self.tracks.items():
            if not td.enabled:
                continue
            p = out_dir / f"{self.name}_{tname}.mid"
            # minimal: build a single-track project copy and export
            stem_proj = SongProject(name=f"{self.name}_{tname}", spec=self.spec)
            stem_proj.tracks[tname] = td
            stem_proj.export_full_midi(p)
            paths.append(str(p))
        return paths

    def render_audio_preview(self, wav_path: Optional[Path] = None, limit_seconds: float = 120.0) -> Optional[Path]:
        """High-quality (or fallback) full song audio preview. Returns WAV path."""
        from .preview import render_preview
        return render_preview(self, wav_path, seconds_limit=limit_seconds)

    def to_template(self) -> Dict[str, Any]:
        """Return a reusable template (spec + instructions, no concrete events)."""
        return {
            "name": self.name,
            "spec": self._spec_to_dict(),
            "default_instructions": {k: v.instructions for k, v in self.tracks.items()},
            "prompt_examples": [h.get("prompt", "") for h in self.prompt_history[-5:]],
        }


# Convenience: wrap a plain generate result into a project (used during transition)
def project_from_spec_and_events(name: str, spec: SongSpec, events_by_track: Dict[str, List[NoteEvent]], prompt: str = "") -> SongProject:
    proj = SongProject(name=name, spec=spec)
    for tname, evs in events_by_track.items():
        proj.set_track_events(tname, evs)
    proj.add_version(prompt=prompt)
    return proj


if __name__ == "__main__":
    # Smoke
    from .ai import NoteEvent
    p = SongProject(name="test")
    p.set_track_events("lead", [NoteEvent(pitch=60, start=0.0, duration=1.0, velocity=80, track="lead")])
    print("Project created with", len(p.tracks), "track(s)")
    d = p.to_dict()
    p2 = SongProject.from_dict(d)
    print("Roundtrip OK, tracks:", list(p2.tracks.keys()))
    print("Project module smoke passed.")
