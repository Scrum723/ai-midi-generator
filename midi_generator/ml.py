"""
Optional Local ML module (stub for Phase 5 / v2).

When torch + a small model is available, this can provide an alternative
to pure LLM for "complete song generation" (learned long-term coherence).

The API is deliberately compatible with the rest of the system:
- Accepts prompt + optional base project/spec.
- Returns updates in the form of NoteEvent lists or SongSpecOverrides
  so the same SongProject / TrackData / editing / export pipeline works unchanged.

Current implementation: pure placeholder (no torch required). Users can
`pip install torch` and replace the inference body later.

Hybrid recommendation (per plan): LLM for prompt ease + precise adherence;
ML for prudent complete/coherent song gen on long forms. Both feed the
editable project model.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import os

try:
    import torch
    HAS_TORCH = True
except Exception:
    HAS_TORCH = False

from .ai import NoteEvent, SongSpecOverrides
from .core import SongSpec


class LocalMLGenerator:
    """Drop-in compatible generator for local ML inference."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.available = HAS_TORCH and (model_path is None or os.path.exists(model_path))
        self._model = None  # placeholder for real loaded model

    def is_available(self) -> bool:
        return self.available

    def generate(
        self,
        prompt: str,
        base_spec: Optional[SongSpec] = None,
        duration_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Returns a dict with either:
          - 'overrides': SongSpecOverrides
          - 'events': Dict[str, List[NoteEvent]]   # per-track
        The caller (ai_generate / project) can merge exactly as with LLM results.
        """
        if not self.available:
            return {"overrides": SongSpecOverrides(rationale="ML not available (torch or model missing)"), "used_ml": False}

        # === PLACEHOLDER ===
        # In a real implementation:
        #   - tokenize prompt + conditioning (length, key from base_spec, etc.)
        #   - run forward pass (MPS on Apple Silicon)
        #   - decode to NoteEvent lists or high-level structure
        #   - return in the dict above
        #
        # For now we return a helpful stub that the rest of the pipeline accepts.
        return {
            "overrides": SongSpecOverrides(
                rationale="Local ML stub (replace with real inference). Prompt was: " + prompt[:80],
                density=0.7,
            ),
            "events": {},  # real version would populate per-track NoteEvent lists
            "used_ml": True,
            "note": "Install torch + a compatible MIDI model and implement inference here.",
        }


# Convenience for the rest of the app
_default_ml = LocalMLGenerator()

def generate_with_local_ml(prompt: str, **kwargs) -> Dict[str, Any]:
    return _default_ml.generate(prompt, **kwargs)


if __name__ == "__main__":
    g = LocalMLGenerator()
    print("ML available:", g.is_available())
    out = g.generate("test future bass drop")
    print("Stub output keys:", list(out.keys()))
