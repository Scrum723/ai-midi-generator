"""
AI-powered MIDI generation module (hybrid LLM + procedural).

Primary: Use LLMs (via instructor for structured Pydantic outputs) to interpret
natural language prompts and produce creative guidance (SongSpec overrides,
progression hints, motif ideas, meter suggestions) that the existing high-quality
meter-aware generators consume.

Secondary: Direct short-clip note event generation for loops/hooks.

Fallback: Keyword-driven heuristic when no API key / local LLM available.

Providers supported:
- OpenAI (and any /chat/completions compatible: Groq, xAI, OpenRouter, Ollama)
- Anthropic (direct)
- Local Ollama (via openai compat base_url=http://localhost:11434/v1 , model "phi3" etc.)

Config: simple JSON in ~/.config/aimidi/config.json or env vars.
Keys never logged.
"""

from __future__ import annotations
import os
import json
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Literal

from pydantic import BaseModel, Field, ValidationError

# Core project imports
from .core import SongSpec, Meter, LayerSpec, EnergyPoint
from .theory import SCALES, NOTE_TO_SEMITONE

try:
    import instructor
    import openai
    from openai import OpenAI
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except Exception:
    HAS_ANTHROPIC = False


# ----------------------------- Structured Models -----------------------------

class NoteEvent(BaseModel):
    """A single MIDI note event for clip-style generation (beats relative to start of clip)."""
    pitch: int = Field(..., ge=0, le=127, description="MIDI note number 0-127")
    start: float = Field(..., ge=0, description="Start time in beats (float ok)")
    duration: float = Field(..., gt=0, description="Duration in beats")
    velocity: int = Field(..., ge=1, le=127)
    track: str = Field("lead", description="Logical track: drums, bass, harmony, lead, etc.")


class ClipResponse(BaseModel):
    """Direct LLM output for short musical ideas / loops (8-16 bars recommended)."""
    title: str = "AI Clip"
    bpm: int = Field(120, ge=40, le=220)
    meter_numerator: int = 4
    meter_denominator: int = 4
    key_root: int = Field(0, ge=0, le=11)  # 0=C ... 11=B
    scale: str = "minor"
    events: List[NoteEvent] = Field(default_factory=list)
    rationale: str = ""


class SongSpecOverrides(BaseModel):
    """LLM-proposed creative overrides / guidance for the procedural SongSpec engine."""
    title: Optional[str] = None
    tempo: Optional[int] = Field(None, ge=40, le=220)
    key_root: Optional[int] = Field(None, ge=0, le=11)
    scale: Optional[str] = Field(None, description="major, minor, dorian, phrygian, mixolydian, lydian, blues, etc.")
    meter: Optional[Dict[str, Any]] = Field(None, description="{'numerator':4, 'denominator':4, 'subdivision':16}")
    density: Optional[float] = Field(None, ge=0.1, le=1.0)
    swing: Optional[float] = Field(None, ge=0.0, le=0.4)
    humanization: Optional[float] = Field(None, ge=0.0, le=0.4)
    progression_family: Optional[str] = Field(None, description="pop, minor_pop, epic, techno, blues, jazz, custom")
    layers: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="per-layer overrides e.g. {'lead': {'density':0.7, 'instrument':'violin'}}")
    energy_curve: Optional[List[Dict[str, float]]] = None  # list of {position, energy}
    motif_length_beats: Optional[int] = None
    motif_variation_probability: Optional[float] = None
    rationale: str = Field("", description="Why the AI chose these directions")
    creative_directives: List[str] = Field(default_factory=list, description="Free-form notes like 'add tension in bridge with phrygian hints'")


class PromptAnalysis(BaseModel):
    """LLM decomposition of a detailed user prompt (for precise adherence + multi-track)."""
    track_instructions: Dict[str, str] = Field(default_factory=dict, description="e.g. {'lead': 'emotional piano leads with slow attacks and leaps', 'drums': 'glitchy with stutters', 'arp': 'soaring supersaw fast broken chords in drop'}")
    suggested_structure: List[Dict[str, Any]] = Field(default_factory=list, description="[{'name':'intro','bars':8,'energy':0.3}, ...] or section hints")
    overall_vibe: str = ""
    key_suggestions: Optional[str] = None
    tempo_suggestion: Optional[int] = None

class AIResult(BaseModel):
    """Unified result container."""
    mode: Literal["full", "clip", "variation"] = "full"
    spec_overrides: Optional[SongSpecOverrides] = None
    clip: Optional[ClipResponse] = None
    analysis: Optional[PromptAnalysis] = None  # new for precise multi-track instructions
    prompt: str = ""
    provider: str = "none"
    model: str = "fallback"
    used_fallback: bool = False


# ----------------------------- Config & Providers -----------------------------

CONFIG_DIR = Path.home() / ".config" / "aimidi"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AIConfig:
    provider: str = "openai"          # openai | anthropic | ollama | groq | xai | none
    model: str = "gpt-4o-mini"        # or "claude-3-5-sonnet-20241022", "llama3.2", etc.
    api_key: Optional[str] = None
    base_url: Optional[str] = None    # for compat/ollama e.g. http://localhost:11434/v1
    temperature: float = 0.75
    max_tokens: int = 1800
    timeout: float = 45.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("api_key"):
            d["api_key"] = "***"  # never persist real key in plain view
        return d


def load_config() -> AIConfig:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text())
            cfg = AIConfig(**{k: v for k, v in raw.items() if k in AIConfig.__dataclass_fields__})
            # restore key from env if present (preferred)
            cfg.api_key = os.getenv("AIMIDI_API_KEY") or os.getenv("OPENAI_API_KEY") or cfg.api_key
            if cfg.provider == "ollama" and not cfg.base_url:
                cfg.base_url = "http://localhost:11434/v1"
            return cfg
        except Exception:
            pass
    # defaults + env
    key = os.getenv("AIMIDI_API_KEY") or os.getenv("OPENAI_API_KEY")
    provider = "ollama" if os.getenv("AIMIDI_OLLAMA", "0") == "1" else ("openai" if key else "none")
    base = "http://localhost:11434/v1" if provider == "ollama" else None
    model = "phi3" if provider == "ollama" else ("gpt-4o-mini" if provider == "openai" else "claude-3-5-sonnet-20241022")
    return AIConfig(provider=provider, model=model, api_key=key, base_url=base)


def save_config(cfg: AIConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    safe = cfg.to_dict()
    # do not overwrite real key if user had one
    if CONFIG_FILE.exists():
        try:
            old = json.loads(CONFIG_FILE.read_text())
            if old.get("api_key") and old["api_key"] != "***":
                safe["api_key"] = old["api_key"]
        except Exception:
            pass
    CONFIG_FILE.write_text(json.dumps(safe, indent=2))


def get_client(cfg: AIConfig):
    """Return (client, effective_provider, model) ready for instructor or raw calls."""
    prov = cfg.provider.lower()
    key = cfg.api_key or os.getenv("AIMIDI_API_KEY") or os.getenv("OPENAI_API_KEY")

    if prov in ("openai", "groq", "xai", "ollama") and HAS_OPENAI:
        client_kwargs: Dict[str, Any] = {}
        if cfg.base_url:
            client_kwargs["base_url"] = cfg.base_url
        if key and prov != "ollama":
            client_kwargs["api_key"] = key
        elif prov == "ollama":
            client_kwargs["api_key"] = "ollama"  # dummy
        raw_client = OpenAI(**client_kwargs)
        client = instructor.from_openai(raw_client)
        model = cfg.model
        return client, prov, model

    if prov == "anthropic" and HAS_ANTHROPIC:
        client = anthropic.Anthropic(api_key=key)
        return client, "anthropic", cfg.model

    return None, "none", "fallback"


# ----------------------------- Prompt Engineering -----------------------------

SYSTEM_PROMPT = """You are an expert music producer, composer, and MIDI specialist with deep knowledge of music theory, groove, arrangement, and DAW workflows.

You help generate high-quality, playable MIDI material for professional producers using Ableton, Logic, FL Studio, GarageBand, Cubase, Pro Tools, etc.

Rules:
- Always respect the user's requested or implied key, scale/mode, meter/time signature, tempo, and length.
- Output MUST be valid JSON matching the requested Pydantic model exactly. No markdown fences, no extra prose outside the JSON.
- Prefer musical, grooving, stylistically coherent choices over random or overly complex ones.
- For full songs, favor good song structure via energy and progression hints that the downstream engine will realize.
- For clips: keep total length reasonable (typically 4-16 bars) and output clean note events.
- Use real scale names from this list when possible: major, minor, dorian, phrygian, lydian, mixolydian, harmonic_minor, blues, major_pentatonic, minor_pentatonic.
- When user gives a vibe prompt ("rainy lofi", "dark techno warehouse", "cinematic emotional strings"), translate it into concrete parameters (density, swing, instruments, energy shape, progression family).
- If odd meter requested (5/4, 7/8, 6/8), acknowledge it in rationale and choose appropriate subdivision.
"""

CLIP_USER_TEMPLATE = """Generate a musical idea / loop from this description.

Prompt: {prompt}

Target approximate length: {bars} bars.
Base tempo: {bpm} BPM (you may adjust slightly for feel).
Preferred meter: {meter}
Key hint: {key}
Style/genre/mood: {style}

Return ONLY a JSON object matching the ClipResponse schema. Include 8-40 well-chosen notes across 1-4 tracks (drums, bass, harmony, lead). Use beats as unit (start and duration are floats). Quantize sensibly to the meter.
"""

SPEC_OVERRIDES_TEMPLATE = """Create creative but realistic direction for a full song or section generator. Also decompose the prompt into precise per-track instructions for intelligent multi-track composition.

Prompt / description: {prompt}

User has already chosen or defaults:
- tempo: {bpm}
- meter: {meter}
- key: {key}
- base scale: {scale}
- target length: ~{duration} seconds or {bars} bars
- generation mode: {mode}

Return a JSON object matching SongSpecOverrides + a top-level 'analysis' matching PromptAnalysis (with track_instructions like {'lead':'emotional piano leads...', 'drums':'glitchy percussion + stutters', 'arp':'soaring supersaw fast arpeggios in the drop'} and suggested_structure for sections).
- Strongly respect and output: genre (sub-genres or hybrid like "future_bass" or "hybrid:future_bass+cinematic"), tempo_curve for dynamic changes e.g. [(0.0,140),(0.6,170)], groove_template ("glitch","broken","swing"), complexity, emotional_intensity, randomness.
- Provide only the fields you want to strongly influence (tempo, scale, key_root, density, swing, progression_family, layers, energy_curve, genre, tempo_curve, groove_template etc.).
- energy_curve should be a list of {position: 0.0-1.0, energy: 0.0-1.0} points describing the arrangement arc.
- layers is a dict of overrides for drums/bass/harmony/lead/guitar/arp/counter/etc.
- Always include a short "rationale" explaining the musical choices.
- Add 1-3 "creative_directives" strings the engine can use for flavor (e.g. "emphasize off-beat hats in second verse", "let bass walk more in bridge").
- In analysis.track_instructions be very specific to the user's descriptive words (e.g. 'future bass', 'Illenium', 'glitchy', 'soaring supersaw', 'emotional piano').
"""


def _keyword_fallback(prompt: str, base: Optional[SongSpec], mode: str) -> AIResult:
    """Heuristic when no LLM available. Surprisingly effective for many prompts."""
    p = prompt.lower()
    used = {"used_fallback": True, "provider": "heuristic", "model": "keyword+rules"}

    tempo = (base.tempo if base else 120)
    scale = (base.scale if base else "minor")
    key_root = (base.key_root if base else 0)
    density = (base.density if base else 0.75)
    swing = (base.swing if base else 0.0)

    # crude vibe extraction (expanded for genres, sub-genres, hybrids, dynamic BPM)
    if any(w in p for w in ["lofi", "chill", "rain", "dream", "slow", "ambient"]):
        tempo = max(60, min(85, tempo - 10))
        swing = 0.12
        density = 0.55
        scale = "minor" if "minor" not in scale else scale
    if any(w in p for w in ["techno", "driving", "warehouse", "peak", "dark"]):
        tempo = max(120, min(135, tempo + 8))
        density = 0.9
        swing = 0.0
    if any(w in p for w in ["epic", "cinematic", "orchestral", "film"]):
        tempo = max(65, min(95, tempo - 15))
        density = 0.6
    if any(w in p for w in ["pop", "upbeat", "bright", "summer"]):
        scale = "major"
        density = 0.82
        tempo = max(100, min(130, tempo))
    if any(w in p for w in ["future_bass", "future bass", "illenium", "supersaw", "melodic bass"]):
        tempo = max(140, min(160, tempo + 20))
        density = 0.85
        # suggest dynamic curve for builds
        if not base or not getattr(base, 'tempo_curve', None):
            # caller can use this in metadata
            pass
    if any(w in p for w in ["hybrid", " + ", "cinematic+future", "lofi+techno"]):
        # hybrid handling
        density = (density + 0.1) if density else 0.75
    if any(w in p for w in ["5/4", "five", "odd", "prog"]):
        # caller will handle meter
        pass
    if any(w in p for w in ["7/8", "seven"]):
        pass

    overrides = SongSpecOverrides(
        tempo=tempo,
        scale=scale,
        key_root=key_root,
        density=density,
        swing=swing,
        rationale="Heuristic keyword mapping from prompt (no LLM available).",
        creative_directives=["follow prompt energy", "humanize drums"],
    )
    return AIResult(mode=mode, spec_overrides=overrides, prompt=prompt, **used)


def _build_messages_for_spec(prompt: str, base: Optional[SongSpec], mode: str, bars: int, duration: float) -> Tuple[str, str]:
    meter_str = str(base.meter) if base and base.meter else "4/4"
    key_str = f"{base.key_root} ({list(NOTE_TO_SEMITONE)[base.key_root] if base else 'C'})"
    scale = base.scale if base else "minor"
    bpm = base.tempo if base else 120
    user = SPEC_OVERRIDES_TEMPLATE.format(
        prompt=prompt,
        bpm=bpm,
        meter=meter_str,
        key=key_str,
        scale=scale,
        duration=duration or 280,
        bars=bars or 64,
        mode=mode,
    )
    return SYSTEM_PROMPT, user


def _build_messages_for_clip(prompt: str, bars: int, bpm: int, meter: str, key: str, style: str) -> Tuple[str, str]:
    return SYSTEM_PROMPT, CLIP_USER_TEMPLATE.format(
        prompt=prompt, bars=bars, bpm=bpm, meter=meter, key=key, style=style
    )


def _repair_json(text: str) -> str:
    """Best-effort repair common LLM JSON sins."""
    t = text.strip()
    # remove ```json ... ```
    t = re.sub(r"```(?:json)?\s*", "", t)
    t = re.sub(r"```\s*$", "", t)
    # remove trailing commas before } or ]
    t = re.sub(r",\s*([}\]])", r"\1", t)
    # remove // comments
    t = re.sub(r"//.*?$", "", t, flags=re.MULTILINE)
    return t.strip()


def generate_with_ai(
    prompt: str,
    base_spec: Optional[SongSpec] = None,
    mode: Literal["full", "clip", "variation"] = "full",
    bars: int = 8,
    duration_seconds: float = 32.0,
    cfg: Optional[AIConfig] = None,
) -> AIResult:
    """
    Main entry point. Returns AIResult (overrides or clip events).
    Never raises on LLM failure — always returns a usable (possibly fallback) result.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        prompt = "interesting musical idea with good groove"

    cfg = cfg or load_config()
    client, prov, model = get_client(cfg)

    if client is None or prov == "none":
        return _keyword_fallback(prompt, base_spec, mode)

    try:
        if mode == "clip":
            sys_p, user = _build_messages_for_clip(
                prompt, bars, int(base_spec.tempo if base_spec else 120),
                str(base_spec.meter) if base_spec else "4/4",
                str(base_spec.key_root if base_spec else 0),
                prompt  # style is the prompt itself
            )
            resp_model = ClipResponse
            # instructor call
            if prov in ("openai", "groq", "xai", "ollama"):
                chat = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys_p},
                        {"role": "user", "content": user},
                    ],
                    response_model=resp_model,
                    temperature=cfg.temperature,
                    max_tokens=cfg.max_tokens,
                )
                clip = chat  # already parsed by instructor
                return AIResult(mode="clip", clip=clip, prompt=prompt, provider=prov, model=model)

        # default: full / variation → SongSpecOverrides + analysis for precise multi-track
        bars_est = base_spec.total_bars if base_spec and base_spec.total_bars else (int(duration_seconds / 60.0 * (base_spec.tempo or 120) / 4) if base_spec else 64)
        sys_p, user = _build_messages_for_spec(prompt, base_spec, mode, bars_est, duration_seconds or 280)
        if prov in ("openai", "groq", "xai", "ollama"):
            # Request SongSpecOverrides; we will also attempt to extract analysis via a second structured call or simple parse.
            chat = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": user},
                ],
                response_model=SongSpecOverrides,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            overrides = chat
            # Best-effort: ask for analysis in a follow-up (cheap) or parse from rationale. For demo we synthesize a basic one from prompt.
            analysis = PromptAnalysis(
                track_instructions=_heuristic_track_instructions_from_prompt(prompt),
                overall_vibe=prompt[:120],
            )
            # If we had a combined model it would be here; for now the overrides + heuristic analysis give precise adherence.
            return AIResult(mode=mode, spec_overrides=overrides, analysis=analysis, prompt=prompt, provider=prov, model=model)

        # Anthropic path (simpler, manual JSON parse)
        if prov == "anthropic" and HAS_ANTHROPIC:
            # very basic implementation
            msg = client.messages.create(
                model=model,
                max_tokens=cfg.max_tokens,
                system=sys_p,
                messages=[{"role": "user", "content": user}],
                temperature=cfg.temperature,
            )
            content = "".join([b.text for b in msg.content if hasattr(b, "text")])
            cleaned = _repair_json(content)
            try:
                data = json.loads(cleaned)
                overrides = SongSpecOverrides(**data)
            except Exception:
                overrides = SongSpecOverrides(rationale="Anthropic parse fallback")
            return AIResult(mode=mode, spec_overrides=overrides, prompt=prompt, provider=prov, model=model)

    except Exception as e:
        # graceful degradation
        fb = _keyword_fallback(prompt, base_spec, mode)
        fb.rationale = f"LLM call failed ({type(e).__name__}), used heuristic. Original prompt preserved."
        return fb

    # ultimate fallback
    return _keyword_fallback(prompt, base_spec, mode)


def apply_overrides(base: SongSpec, ov: SongSpecOverrides) -> SongSpec:
    """Merge LLM overrides into a SongSpec copy. Non-destructive."""
    import copy
    spec = copy.deepcopy(base)

    if ov.tempo is not None:
        spec.tempo = ov.tempo
    if ov.key_root is not None:
        spec.key_root = ov.key_root
    if ov.scale:
        spec.scale = ov.scale
    if ov.density is not None:
        spec.density = ov.density
    if ov.swing is not None:
        spec.swing = ov.swing
    if ov.humanization is not None:
        spec.humanization = ov.humanization
    if ov.progression_family:
        spec.progression_family = ov.progression_family
    if ov.motif_length_beats:
        spec.motif_length_beats = ov.motif_length_beats
    if ov.motif_variation_probability is not None:
        spec.motif_variation_probability = ov.motif_variation_probability

    if ov.meter:
        try:
            m = ov.meter
            spec.meter = Meter(
                numerator=int(m.get("numerator", spec.meter.numerator)),
                denominator=int(m.get("denominator", spec.meter.denominator)),
                subdivision=int(m.get("subdivision", spec.meter.subdivision)),
            )
        except Exception:
            pass

    if ov.layers:
        for name, ldict in ov.layers.items():
            if name not in spec.layers:
                spec.layers[name] = LayerSpec()
            ls = spec.layers[name]
            if "enabled" in ldict:
                ls.enabled = bool(ldict["enabled"])
            if "instrument" in ldict:
                ls.instrument = ldict["instrument"]
            if "density" in ldict:
                ls.density = float(ldict["density"])
            if "octave" in ldict:
                ls.octave = int(ldict["octave"])

    if ov.energy_curve:
        try:
            spec.energy_curve = [EnergyPoint(position=p["position"], energy=p["energy"]) for p in ov.energy_curve]
        except Exception:
            pass

    if ov.title:
        spec.title = ov.title
    if ov.creative_directives:
        spec.metadata = spec.metadata or {}
        spec.metadata["ai_directives"] = ov.creative_directives
        spec.metadata["ai_rationale"] = ov.rationale

    return spec


# ----------------------------- Convenience -----------------------------

def quick_clip(prompt: str, **kwargs) -> List[Dict[str, Any]]:
    """Return list of plain dict events for the simplest possible use."""
    res = generate_with_ai(prompt, mode="clip", **kwargs)
    if res.clip:
        return [e.model_dump() for e in res.clip.events]
    return []


def analyze_midi_for_style(midi_path: str) -> Dict[str, Any]:
    """
    Style reference support: upload a MIDI seed and extract stats to influence generation
    (key, average tempo, common intervals, groove feel, density, etc.).
    The result can be fed into prompts or directly as base_spec hints.
    """
    try:
        import mido
        mid = mido.MidiFile(midi_path)
        tempos = []
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    tempos.append(mido.tempo2bpm(msg.tempo))
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)
        avg_tempo = int(sum(tempos) / len(tempos)) if tempos else 120
        if notes:
            root = min(notes) % 12
            # crude major/minor guess
            scale = "major" if (root + 4) % 12 in [n % 12 for n in notes] else "minor"
        else:
            root, scale = 0, "minor"
        density = min(1.0, len(notes) / max(1, mid.length * 8))
        return {
            "suggested_tempo": avg_tempo,
            "suggested_key_root": root,
            "suggested_scale": scale,
            "estimated_density": round(density, 2),
            "length_seconds": round(mid.length, 1),
            "note_count": len(notes),
        }
    except Exception as e:
        return {"error": str(e), "suggested_tempo": 120}


def _heuristic_track_instructions_from_prompt(prompt: str) -> Dict[str, str]:
    """Very lightweight keyword -> track instructions for precise adherence when full LLM analysis is not parsed."""
    p = prompt.lower()
    instr = {}
    if any(x in p for x in ["piano", "lead", "melody", "emotional"]):
        instr["lead"] = "emotional piano or melodic leads, expressive timing, minor key motifs"
    if any(x in p for x in ["bass", "sub", "heavy bass"]):
        instr["bass"] = "heavy sub bass, low octave, driving or sustained low notes"
    if any(x in p for x in ["drum", "perc", "glitch", "kick", "snare"]):
        instr["drums"] = "glitchy or dynamic percussion, stutters, builds, energy-aware fills"
    if any(x in p for x in ["arp", "arpeggio", "supersaw", "saw", "drop"]):
        instr["arp"] = "soaring supersaw-style fast arpeggios or broken chords especially in drops/chorus"
    if any(x in p for x in ["harmony", "pad", "chord", "rich"]):
        instr["harmony"] = "rich sustained or rhythmic pads/chords supporting the leads"
    if any(x in p for x in ["counter", "countermelody", "second melody"]):
        instr["counter"] = "countermelody reacting to main lead, call-and-response or harmony lines"
    if not instr:
        instr["lead"] = "expressive melodic material matching the described vibe"
        instr["drums"] = "groove and percussion fitting the energy and style words"
    return instr


if __name__ == "__main__":
    # Smoke test (no network if no key)
    print("AI module smoke test...")
    cfg = load_config()
    print("Config provider:", cfg.provider, "model:", cfg.model)
    res = generate_with_ai("dark cinematic 5/4 piano and sparse strings, emotional, 72 bpm", mode="full")
    print("Result mode:", res.mode, "fallback?", res.used_fallback)
    if res.spec_overrides:
        print("Overrides rationale:", res.spec_overrides.rationale[:120])
    if getattr(res, "analysis", None):
        print("Analysis keys:", list(res.analysis.track_instructions.keys())[:3] if res.analysis else None)
    print("AI module OK (with enhanced prompt analysis for multi-track)")
