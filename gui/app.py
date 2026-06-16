"""
MIDI Song Generator - Desktop App (CustomTkinter)

This is the beginning of the accessible GUI the user requested.
It lets you visually control SongSpec parameters (key, meter, style, etc.)
and generate full songs.

Run with:
    source .venv/bin/activate
    python -m gui.app
"""

import customtkinter as ctk
import random
import os
import subprocess
import threading
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", message="Unable to find acceptable character detection dependency")

# Make sure we can import the library
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_generator.core import SongSpec, Meter, EnergyPoint, LayerSpec
from midi_generator.styles import PRESETS, COMMON_METERS
from midi_generator.generate import generate_song, ai_generate_song, HAS_AI
from midi_generator.ai import load_config, save_config, AIConfig, generate_with_ai, NoteEvent
from midi_generator.playback import MIDIPlayer, list_output_ports, find_iac_port
from midi_generator.project import SongProject, project_from_spec_and_events
from midi_generator.generate import HAS_PROJECT

# Basic instrument choices the user can pick from in the GUI
INSTRUMENT_CHOICES = {
    "Lead": ["square_lead", "saw_lead", "calliope", "violin", "trumpet", "choir", "voice", "guitar_clean", "guitar_overdrive"],
    "Harmony": ["pad_choir", "pad_warm", "pad_sweep", "strings", "electric_piano", "organ"],
    "Bass": ["bass_finger", "bass_pick", "bass_fretless", "bass_slap", "square_lead"],
    "Vocals": ["choir", "voice", "synth_brass", "pad_choir"],  # "vocals" proxy via MIDI instruments
}


class MidiSongApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MIDI Song Generator")
        self.geometry("980x720")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.current_spec: SongSpec | None = None
        self.last_generated_path: str | None = None

        self._build_ui()

    def _build_ui(self):
        # Top bar
        top = ctk.CTkFrame(self, height=60)
        top.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(top, text="MIDI Song Generator", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", padx=15)

        self.status_label = ctk.CTkLabel(top, text="Ready", text_color="gray70")
        self.status_label.pack(side="right", padx=15)

        # Main container
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # Left column - Controls (scrollable so it doesn't feel cramped)
        left_container = ctk.CTkFrame(main, width=420)
        left_container.pack(side="left", fill="y", padx=(0, 8), pady=5)

        left = ctk.CTkScrollableFrame(left_container, width=400, label_text="Controls")
        left.pack(fill="both", expand=True)

        # === AI PROMPT (Primary creative interface) ===
        ctk.CTkLabel(left, text="✨ AI Prompt (text → MIDI)", font=ctk.CTkFont(weight="bold", size=13)).pack(anchor="w", padx=12, pady=(8, 2))
        self.prompt_box = ctk.CTkTextbox(left, height=78, font=ctk.CTkFont(size=12))
        self.prompt_box.pack(fill="x", padx=10, pady=2)
        self.prompt_box.insert("1.0", "dark cinematic piano and sparse strings, emotional, rainy night, 5/4, 72 bpm")

        ai_btn_row = ctk.CTkFrame(left)
        ai_btn_row.pack(fill="x", padx=10, pady=(4, 8))
        self.ai_generate_btn = ctk.CTkButton(ai_btn_row, text="🤖  GENERATE WITH AI", height=38, font=ctk.CTkFont(size=14, weight="bold"),
                                             command=self._on_ai_generate, fg_color="#3a7ca5")
        self.ai_generate_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(ai_btn_row, text="Variation", width=80, command=self._on_ai_variation).pack(side="left", padx=2)

        # === Generation Mode (NEW) ===
        ctk.CTkLabel(left, text="What to Generate", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))
        self.mode_var = ctk.StringVar(value="Full Song")
        mode_frame = ctk.CTkFrame(left)
        mode_frame.pack(fill="x", padx=10, pady=2)
        modes = ["Full Song", "Drum Loop", "Bass Line", "Hook / Melody", "Beat (Drums + Bass)"]
        for m in modes:
            ctk.CTkRadioButton(mode_frame, text=m, variable=self.mode_var, value=m,
                               command=self._on_mode_change).pack(anchor="w", padx=8, pady=2)

        # === Quick Instrument Variation (addresses "no variations in instruments") ===
        ctk.CTkLabel(left, text="Quick Instrument Choices", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        inst_frame = ctk.CTkFrame(left)
        inst_frame.pack(fill="x", padx=10, pady=2)

        self.lead_inst_var = ctk.StringVar(value="square_lead")
        ctk.CTkLabel(inst_frame, text="Lead:").pack(side="left", padx=(6,2))
        ctk.CTkComboBox(inst_frame, values=INSTRUMENT_CHOICES["Lead"], variable=self.lead_inst_var, width=130).pack(side="left", padx=2)

        self.harmony_inst_var = ctk.StringVar(value="pad_warm")
        ctk.CTkLabel(inst_frame, text="Harmony:").pack(side="left", padx=(8,2))
        ctk.CTkComboBox(inst_frame, values=INSTRUMENT_CHOICES["Harmony"], variable=self.harmony_inst_var, width=120).pack(side="left", padx=2)

        self.bass_inst_var = ctk.StringVar(value="bass_finger")
        ctk.CTkLabel(inst_frame, text="Bass:").pack(side="left", padx=(8,2))
        ctk.CTkComboBox(inst_frame, values=INSTRUMENT_CHOICES["Bass"], variable=self.bass_inst_var, width=110).pack(side="left", padx=2)

        self.vocal_inst_var = ctk.StringVar(value="choir")
        ctk.CTkLabel(inst_frame, text="Vocals:").pack(side="left", padx=(8,2))
        ctk.CTkComboBox(inst_frame, values=INSTRUMENT_CHOICES["Vocals"], variable=self.vocal_inst_var, width=100).pack(side="left", padx=2)

        # === Presets / Genre ===
        ctk.CTkLabel(left, text="Genre / Style (sub-genres & hybrids supported)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(12, 4))
        self.preset_var = ctk.StringVar(value="pop")
        preset_frame = ctk.CTkFrame(left)
        preset_frame.pack(fill="x", padx=10, pady=2)

        # Show presets in two columns for less mess
        preset_names = list(PRESETS.keys())
        for i in range(0, len(preset_names), 2):
            row = ctk.CTkFrame(preset_frame)
            row.pack(fill="x")
            ctk.CTkRadioButton(row, text=preset_names[i].capitalize(), variable=self.preset_var, value=preset_names[i]).pack(side="left", padx=6, pady=2)
            if i + 1 < len(preset_names):
                ctk.CTkRadioButton(row, text=preset_names[i+1].capitalize(), variable=self.preset_var, value=preset_names[i+1]).pack(side="left", padx=6, pady=2)

        # Genre override / hybrid text (new)
        genre_frame = ctk.CTkFrame(left)
        genre_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(genre_frame, text="Genre (or hybrid e.g. future_bass+cinematic):").pack(side="left", padx=4)
        self.genre_entry = ctk.CTkEntry(genre_frame, width=220, placeholder_text="future_bass")
        self.genre_entry.pack(side="left", padx=4)
        self.genre_entry.insert(0, "cinematic")

        # Style reference (MIDI upload for analysis)
        style_ref_frame = ctk.CTkFrame(left)
        style_ref_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(style_ref_frame, text="Load MIDI Seed (style ref)", width=160, command=self._load_midi_seed).pack(side="left", padx=4)
        self.style_ref_label = ctk.CTkLabel(style_ref_frame, text="(optional)", text_color="gray60")
        self.style_ref_label.pack(side="left", padx=4)

        # === Key ===
        ctk.CTkLabel(left, text="Key", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(12, 4))

        key_frame = ctk.CTkFrame(left)
        key_frame.pack(fill="x", padx=10, pady=2)

        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        self.key_root_var = ctk.StringVar(value="C")
        ctk.CTkComboBox(key_frame, values=notes, variable=self.key_root_var, width=80).pack(side="left", padx=4)

        scales = ["major", "minor", "dorian", "mixolydian", "harmonic_minor", "minor_pentatonic"]
        self.scale_var = ctk.StringVar(value="minor")
        ctk.CTkComboBox(key_frame, values=scales, variable=self.scale_var, width=160).pack(side="left", padx=4)

        # === Time Signature ===
        ctk.CTkLabel(left, text="Time Signature", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(12, 4))

        ts_frame = ctk.CTkFrame(left)
        ts_frame.pack(fill="x", padx=10, pady=2)

        self.meter_var = ctk.StringVar(value="4/4 Straight")
        meter_names = [str(m) for m in COMMON_METERS]
        ctk.CTkOptionMenu(ts_frame, values=meter_names, variable=self.meter_var, width=220,
                          command=self._on_meter_change).pack(side="left", padx=4)

        # === Tempo & Duration ===
        ctk.CTkLabel(left, text="Tempo (BPM)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(12, 2))
        self.tempo_slider = ctk.CTkSlider(left, from_=60, to=160, number_of_steps=100, command=self._update_estimated)
        self.tempo_slider.set(118)
        self.tempo_slider.pack(fill="x", padx=12, pady=2)
        self.tempo_label = ctk.CTkLabel(left, text="118 BPM")
        self.tempo_label.pack(anchor="w", padx=12)

        ctk.CTkLabel(left, text="Duration (minutes)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self.duration_slider = ctk.CTkSlider(left, from_=2.0, to=8.0, number_of_steps=60, command=self._update_estimated)
        self.duration_slider.set(4.8)
        self.duration_slider.pack(fill="x", padx=12, pady=2)
        self.duration_label = ctk.CTkLabel(left, text="4.8 minutes (~128 bars)")
        self.duration_label.pack(anchor="w", padx=12)

        # Variation controls (new)
        ctk.CTkLabel(left, text="Variation & Feel", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self.complexity_slider = ctk.CTkSlider(left, from_=0.0, to=1.0, number_of_steps=20)
        self.complexity_slider.set(0.5)
        self.complexity_slider.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(left, text="Complexity (ornaments / density)").pack(anchor="w", padx=12)
        self.intensity_slider = ctk.CTkSlider(left, from_=0.0, to=1.0, number_of_steps=20)
        self.intensity_slider.set(0.5)
        self.intensity_slider.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(left, text="Emotional Intensity").pack(anchor="w", padx=12)
        self.randomness_slider = ctk.CTkSlider(left, from_=0.0, to=1.0, number_of_steps=20)
        self.randomness_slider.set(0.3)
        self.randomness_slider.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(left, text="Randomness / Variation Amount").pack(anchor="w", padx=12)

        # === Seed ===
        seed_frame = ctk.CTkFrame(left)
        seed_frame.pack(fill="x", padx=10, pady=(12, 4))
        ctk.CTkLabel(seed_frame, text="Seed (for reproducibility)").pack(side="left", padx=6)
        self.seed_entry = ctk.CTkEntry(seed_frame, width=100, placeholder_text="random")
        self.seed_entry.pack(side="left", padx=4)
        ctk.CTkButton(seed_frame, text="Random", width=70, command=self._random_seed).pack(side="left", padx=4)

        # Batch + Preview (new)
        batch_frame = ctk.CTkFrame(left)
        batch_frame.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(batch_frame, text="Batch count:").pack(side="left", padx=4)
        self.batch_count = ctk.CTkEntry(batch_frame, width=50)
        self.batch_count.insert(0, "5")
        self.batch_count.pack(side="left", padx=2)
        ctk.CTkButton(batch_frame, text="Batch Gen", width=90, command=self._on_batch_generate).pack(side="left", padx=4)

        ctk.CTkButton(left, text="▶ Full Song Audio Preview", height=32, command=self._on_audio_preview).pack(fill="x", padx=12, pady=4)

        # === Generate Button ===
        self.generate_btn = ctk.CTkButton(
            left, text="🎵  GENERATE SONG", height=52, font=ctk.CTkFont(size=18, weight="bold"),
            command=self._on_generate
        )
        self.generate_btn.pack(fill="x", padx=12, pady=20)

        # Right side - Output & Info
        right = ctk.CTkFrame(main)
        right.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(right, text="Output", font=ctk.CTkFont(weight="bold", size=16)).pack(anchor="w", padx=12, pady=(8, 4))

        self.output_text = ctk.CTkTextbox(right, height=220, font=ctk.CTkFont(family="Menlo", size=12))
        self.output_text.pack(fill="both", expand=True, padx=10, pady=4)

        # Action buttons
        btn_frame = ctk.CTkFrame(right)
        btn_frame.pack(fill="x", padx=10, pady=8)

        self.open_finder_btn = ctk.CTkButton(btn_frame, text="📂  Reveal in Finder", command=self._reveal_in_finder, state="disabled")
        self.open_finder_btn.pack(side="left", padx=4)

        self.open_garageband_btn = ctk.CTkButton(btn_frame, text="🎹  Open in GarageBand", command=self._open_in_garageband, state="disabled")
        self.open_garageband_btn.pack(side="left", padx=4)

        self.save_project_btn = ctk.CTkButton(btn_frame, text="💾 Save Project", command=self._save_current_project, state="disabled")
        self.save_project_btn.pack(side="left", padx=4)

        self.export_stems_btn = ctk.CTkButton(btn_frame, text="📤 Export Stems", command=self._export_stems, state="disabled")
        self.export_stems_btn.pack(side="left", padx=4)
        self.open_garageband_btn.pack(side="left", padx=4)

        # === Track Editor for Full Song Editing & Control (#3 - most important) ===
        # Implements every decision in the plan: in-memory editable TrackData (events + params), per-track tweak, targeted regen, note-level editing (text list), real-time update to project, re-render.
        ctk.CTkLabel(right, text="Track Editor - Full Song Editing & Control (real-time)", font=ctk.CTkFont(weight="bold", size=13)).pack(anchor="w", padx=12, pady=(14, 4))

        self.track_select_var = ctk.StringVar(value="(generate to load tracks)")
        self.track_select = ctk.CTkOptionMenu(right, variable=self.track_select_var, values=["(generate first)"], command=self._on_track_select)
        self.track_select.pack(fill="x", padx=10, pady=2)

        self.track_editor_frame = ctk.CTkFrame(right)
        self.track_editor_frame.pack(fill="both", expand=False, padx=10, pady=4)

        # Params row
        param_row = ctk.CTkFrame(self.track_editor_frame)
        param_row.pack(fill="x", pady=2)
        ctk.CTkLabel(param_row, text="Density:").pack(side="left", padx=4)
        self.track_density = ctk.CTkEntry(param_row, width=60)
        self.track_density.pack(side="left", padx=2)
        ctk.CTkLabel(param_row, text="Octave:").pack(side="left", padx=4)
        self.track_octave = ctk.CTkEntry(param_row, width=50)
        self.track_octave.pack(side="left", padx=2)
        ctk.CTkLabel(param_row, text="Instr:").pack(side="left", padx=4)
        self.track_instr = ctk.CTkEntry(param_row, width=120)
        self.track_instr.pack(side="left", padx=2)

        # Instructions
        ctk.CTkLabel(self.track_editor_frame, text="Track Instructions (for regen):").pack(anchor="w", padx=4, pady=(4,0))
        self.track_instructions = ctk.CTkTextbox(self.track_editor_frame, height=40)
        self.track_instructions.pack(fill="x", padx=4, pady=2)

        # Event editor (note-level: pitch start dur vel - editable list)
        ctk.CTkLabel(self.track_editor_frame, text="Events (edit lines: pitch start dur vel):").pack(anchor="w", padx=4, pady=(4,0))
        self.track_events_text = ctk.CTkTextbox(self.track_editor_frame, height=80, font=ctk.CTkFont(family="Menlo", size=10))
        self.track_events_text.pack(fill="x", padx=4, pady=2)

        # Action buttons for this track
        track_btns = ctk.CTkFrame(self.track_editor_frame)
        track_btns.pack(fill="x", pady=4)
        ctk.CTkButton(track_btns, text="Apply Params+Events", command=self._apply_track_edit, width=140).pack(side="left", padx=2)
        ctk.CTkButton(track_btns, text="Regen This Track", command=self._regen_selected_track, width=120).pack(side="left", padx=2)
        ctk.CTkButton(track_btns, text="Humanize Track", command=self._humanize_selected_track, width=110).pack(side="left", padx=2)

        # Estimated info
        self.estimate_label = ctk.CTkLabel(right, text="Estimated length: —", text_color="gray70")
        self.estimate_label.pack(anchor="w", padx=12, pady=6)

        self.mode_hint = ctk.CTkLabel(right, text="Tip: For Drum Loops / Bass Lines / Hooks, shorter durations (30-90s) usually work better.", 
                                      text_color="gray55", wraplength=420, justify="left")
        self.mode_hint.pack(anchor="w", padx=12, pady=(4, 8))

        # Quick tip
        tip = ctk.CTkLabel(right, text="Tip: Change the Time Signature to 5/4 or 7/8 and hit Generate to hear how the new engine adapts.", 
                           text_color="gray60", wraplength=420, justify="left")
        tip.pack(anchor="w", padx=12, pady=(10, 0))

        # === AI Status + Live MIDI to DAW (plugin-like integration) ===
        ctk.CTkLabel(right, text="AI & Live MIDI (DAW Integration)", font=ctk.CTkFont(weight="bold", size=13)).pack(anchor="w", padx=12, pady=(14, 4))

        self.ai_status = ctk.CTkLabel(right, text="AI: heuristic (no API key) — set key in Settings for full power", text_color="gray60", wraplength=420)
        self.ai_status.pack(anchor="w", padx=12, pady=2)

        live_frame = ctk.CTkFrame(right)
        live_frame.pack(fill="x", padx=10, pady=4)

        self.port_var = ctk.StringVar(value="IAC Driver Bus 1 (if enabled)")
        # Defer actual port enumeration (list_output_ports uses rtmidi C ext) until after app is running
        # to avoid PyEval_RestoreThread / GIL fatal errors in py2app bundles (common with C extensions + threads at init).
        # Provide sensible defaults for IAC (macOS virtual MIDI).
        default_ports = [
            "IAC Driver Bus 1 (if enabled)",
            "IAC Driver Bus 2",
            "IAC Driver Bus 3",
            "(no ports - enable IAC in Audio MIDI Setup)",
        ]
        self.port_menu = ctk.CTkOptionMenu(live_frame, values=default_ports, variable=self.port_var, width=260)
        self.port_menu.pack(side="left", padx=4)

        # Add refresh button to enumerate real ports at runtime (after mainloop starts)
        ctk.CTkButton(live_frame, text="↻", width=30, command=self._refresh_ports).pack(side="left", padx=2)

        self.live_btn = ctk.CTkButton(live_frame, text="▶ Stream to DAW", width=120, command=self._toggle_live_stream)
        self.live_btn.pack(side="left", padx=4)

        ctk.CTkButton(live_frame, text="⏹", width=36, command=self._stop_live).pack(side="left", padx=2)

        self.live_status = ctk.CTkLabel(right, text="Arm a MIDI track in your DAW (GarageBand/FL/Logic/Ableton) then Stream. IAC must be enabled in Audio MIDI Setup.", 
                                        text_color="gray55", wraplength=420, justify="left")
        self.live_status.pack(anchor="w", padx=12, pady=(2, 6))

        self.player: Optional[MIDIPlayer] = None
        self.current_project: Optional['SongProject'] = None  # PR3 skeleton

        # Initial state
        self._update_estimated()
        self._random_seed()

    def _on_preset_change(self):
        self._update_estimated()

    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode != "Full Song":
            # Suggest shorter, more loop-friendly lengths for non-song modes
            if self.duration_slider.get() > 1.5:
                self.duration_slider.set(0.8)  # ~45-60 seconds loops
            self._update_estimated()
            self.status_label.configure(text=f"Mode: {mode} (shorter loops recommended)")

    def _on_meter_change(self, value):
        self._update_estimated()

    def _update_estimated(self, _=None):
        tempo = int(self.tempo_slider.get())
        duration_min = self.duration_slider.get()
        self.tempo_label.configure(text=f"{tempo} BPM")

        bars = int((duration_min * 60 / tempo) * 4)   # rough 4/4 assumption for display
        self.duration_label.configure(text=f"{duration_min:.1f} minutes (~{bars} bars)")

        self.estimate_label.configure(text=f"Estimated length: ~{duration_min:.1f} min at {tempo} BPM")

    def _random_seed(self):
        self.seed_entry.delete(0, "end")
        self.seed_entry.insert(0, str(random.randint(1, 999999)))

    def _refresh_ports(self):
        """Runtime refresh of MIDI output ports (deferred to avoid early rtmidi GIL crash in bundled app)."""
        try:
            ports = list_output_ports()[:8]
            if ports and not ports[0].startswith("("):
                self.port_menu.configure(values=ports)
                self.live_status.configure(text="Ports refreshed. Select your IAC bus.")
            else:
                self.live_status.configure(text="No MIDI ports found. Enable IAC in Audio MIDI Setup.")
        except Exception as e:
            self.live_status.configure(text=f"Port refresh error: {e}")

    def _load_midi_seed(self):
        # Simple file dialog via tkinter
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Select MIDI for style reference", filetypes=[("MIDI", "*.mid *.midi")])
        if not path:
            return
        try:
            from midi_generator.ai import analyze_midi_for_style
            stats = analyze_midi_for_style(path)
            if "error" not in stats:
                self.style_ref_label.configure(text=f"Seed: {Path(path).name} (t={stats.get('suggested_tempo')})")
                # auto-fill some UI
                if stats.get("suggested_tempo"):
                    self.tempo_slider.set(stats["suggested_tempo"])
                if stats.get("suggested_scale"):
                    self.scale_var.set(stats["suggested_scale"])
                # append to prompt for AI
                current = self.prompt_box.get("1.0", "end").strip()
                self.prompt_box.delete("1.0", "end")
                self.prompt_box.insert("1.0", current + f" (in style of uploaded MIDI {Path(path).name})")
                self._style_ref_path = path  # for later use in build_spec
            else:
                self.style_ref_label.configure(text="Analysis failed")
        except Exception as e:
            self.style_ref_label.configure(text=f"Error: {e}")

    def _build_spec_from_ui(self) -> SongSpec:
        # ... (existing body, we will enhance below)
        preset_name = self.preset_var.get()
        base_spec = PRESETS[preset_name]

        root = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"].index(self.key_root_var.get())

        selected_name = self.meter_var.get()
        selected_meter = next((m for m in COMMON_METERS if str(m) == selected_name), COMMON_METERS[0])

        try:
            seed = int(self.seed_entry.get()) if self.seed_entry.get().strip() else None
        except ValueError:
            seed = None

        layers = base_spec.layers.copy()

        if "lead" in layers:
            lead_choice = self.vocal_inst_var.get() if self.mode_var.get() == "Hook / Melody" else self.lead_inst_var.get()
            layers["lead"] = LayerSpec(**{**layers["lead"].__dict__, "instrument": lead_choice})
        if "harmony" in layers:
            layers["harmony"] = LayerSpec(**{**layers["harmony"].__dict__, "instrument": self.harmony_inst_var.get()})
        if "bass" in layers:
            layers["bass"] = LayerSpec(**{**layers["bass"].__dict__, "instrument": self.bass_inst_var.get()})

        # New params
        genre = self.genre_entry.get().strip() or base_spec.genre
        complexity = getattr(self, 'complexity_slider', None) and self.complexity_slider.get() or base_spec.complexity
        intensity = getattr(self, 'intensity_slider', None) and self.intensity_slider.get() or base_spec.emotional_intensity
        rand = getattr(self, 'randomness_slider', None) and self.randomness_slider.get() or base_spec.randomness

        spec = SongSpec(
            seed=seed,
            key_root=root,
            scale=self.scale_var.get(),
            meter=selected_meter,
            tempo=int(self.tempo_slider.get()),
            genre=genre,
            groove_template=base_spec.groove_template,
            complexity=complexity,
            emotional_intensity=intensity,
            randomness=rand,
            duration_seconds=self.duration_slider.get() * 60,
            density=base_spec.density,
            swing=base_spec.swing,
            layers=layers,
            metadata=base_spec.metadata.copy() | {
                "style_hint": preset_name,
                "generation_mode": self.mode_var.get(),
                "style_ref_midi": getattr(self, '_style_ref_path', None),
            }
        )
        return spec

    # (the implementation above the first def _build_spec_from_ui already includes the enhanced version with genre/variation)

    def _on_generate(self):
        self.generate_btn.configure(state="disabled", text="Generating...")
        self.status_label.configure(text="Generating song...", text_color="#ffaa00")
        self.output_text.delete("1.0", "end")

        spec = self._build_spec_from_ui()
        self.current_spec = spec

        def worker():
            try:
                path = generate_song(spec)
                self.last_generated_path = path
                self.after(0, lambda: self._generation_done(path, spec))
            except Exception as e:
                self.after(0, lambda: self._generation_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _generation_done(self, path: str, spec: SongSpec):
        self.generate_btn.configure(state="normal", text="🎵  GENERATE SONG")
        self.status_label.configure(text="Done ✓", text_color="#00cc88")

        import mido
        mid = mido.MidiFile(path)
        dur_min = mid.length / 60

        text = f"✓ Generated: {Path(path).name}\n"
        text += f"   Duration: {dur_min:.2f} minutes\n"
        text += f"   Key: {['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][spec.key_root]} {spec.scale}\n"
        text += f"   Meter: {spec.meter}\n"
        text += f"   Tempo: {spec.tempo} BPM\n"
        text += f"   Seed: {spec.seed}\n\n"
        text += f"File saved to:\n{path}\n"

        self.output_text.insert("1.0", text)

        self.open_finder_btn.configure(state="normal")
        self.open_garageband_btn.configure(state="normal")
        self.save_project_btn.configure(state="normal")
        self.export_stems_btn.configure(state="normal")
        # preview button is always available via the dedicated UI button we added

        # PR3 skeleton: wrap last gen in a project if possible
        if HAS_PROJECT and self.current_spec and self.last_generated_path:
            try:
                self.current_project = project_from_spec_and_events(
                    Path(self.last_generated_path).stem,
                    self.current_spec,
                    {},  # events will be populated by full PR2+ generators
                    prompt=self.prompt_box.get("1.0", "end").strip() if hasattr(self, "prompt_box") else ""
                )
            except Exception:
                self.current_project = None
        self._refresh_editor_after_gen()

    def _generation_error(self, error_msg: str):
        self.generate_btn.configure(state="normal", text="🎵  GENERATE SONG")
        self.status_label.configure(text="Error", text_color="#ff5555")
        self.output_text.insert("1.0", f"Generation failed:\n{error_msg}\n")

    def _reveal_in_finder(self):
        if self.last_generated_path and os.path.exists(self.last_generated_path):
            subprocess.run(["open", "-R", self.last_generated_path])

    def _open_in_garageband(self):
        if self.last_generated_path and os.path.exists(self.last_generated_path):
            # Try to open with GarageBand, fall back to default app
            try:
                subprocess.run(["open", "-a", "GarageBand", self.last_generated_path])
            except Exception:
                subprocess.run(["open", self.last_generated_path])

    def _save_current_project(self):
        if not self.current_project:
            self.status_label.configure(text="No project to save (generate first)", text_color="#ffaa00")
            return
        import os
        proj_dir = os.path.expanduser("~/AI-MIDI-Projects")
        os.makedirs(proj_dir, exist_ok=True)
        safe_name = "".join(c for c in (self.current_project.name or "untitled") if c.isalnum() or c in " -_").strip()[:40] or "untitled"
        out = os.path.join(proj_dir, f"{safe_name}.json")
        try:
            self.current_project.save(out)
            self.status_label.configure(text=f"Project saved: {out}", text_color="#00cc88")
            # also ensure a full midi exists for convenience
            if self.last_generated_path and os.path.exists(self.last_generated_path):
                import shutil
                shutil.copy(self.last_generated_path, os.path.join(proj_dir, f"{safe_name}.mid"))
        except Exception as e:
            self.status_label.configure(text=f"Save failed: {e}", text_color="#ff5555")

    def _export_stems(self):
        if not self.current_project:
            self.status_label.configure(text="Generate first to export stems", text_color="#ffaa00")
            return
        import os, tempfile, subprocess
        out_dir = tempfile.mkdtemp(prefix="aimidi_stems_")
        try:
            paths = self.current_project.export_stems(out_dir)
            self.status_label.configure(text=f"Stems exported ({len(paths)} files) to {out_dir}", text_color="#00cc88")
            subprocess.run(["open", out_dir])
        except Exception as e:
            self.status_label.configure(text=f"Stems export failed: {e}", text_color="#ff5555")

    # ==================== Full Track Editor Implementation for #3 ====================
    # Every plan decision: editable events list + per-track params, targeted regen with prompt/instructions,
    # note-level (text edit of pitch/start/dur/vel), real-time apply to project, humanize, re-render support.

    def _refresh_track_list(self):
        if not self.current_project or not self.current_project.tracks:
            self.track_select.configure(values=["(no tracks)"])
            self.track_select_var.set("(no tracks)")
            return
        names = [k for k in self.current_project.tracks.keys() if self.current_project.tracks[k].enabled]
        self.track_select.configure(values=names or ["(no enabled tracks)"])
        if names:
            self.track_select_var.set(names[0])
            self._on_track_select(names[0])

    def _on_track_select(self, track_name=None):
        if track_name is None:
            track_name = self.track_select_var.get()
        if not self.current_project or track_name not in self.current_project.tracks:
            return
        self.current_track_name = track_name
        td = self.current_project.tracks[track_name]

        # Populate params
        self.track_density.delete(0, "end")
        self.track_density.insert(0, str(td.params.density))
        self.track_octave.delete(0, "end")
        self.track_octave.insert(0, str(td.params.octave))
        self.track_instr.delete(0, "end")
        self.track_instr.insert(0, td.params.instrument or "")

        # Instructions
        self.track_instructions.delete("1.0", "end")
        self.track_instructions.insert("1.0", td.instructions or "")

        # Events as editable lines
        self.track_events_text.delete("1.0", "end")
        for ev in td.events[:50]:  # limit display for UI
            line = f"{ev.pitch} {ev.start:.2f} {ev.duration:.2f} {ev.velocity}\n"
            self.track_events_text.insert("end", line)

    def _apply_track_edit(self):
        if not self.current_project or not self.current_track_name:
            return
        td = self.current_project.tracks[self.current_track_name]

        # Params
        try:
            td.params.density = float(self.track_density.get())
            td.params.octave = int(self.track_octave.get())
            td.params.instrument = self.track_instr.get().strip() or td.params.instrument
        except:
            pass

        # Instructions
        td.instructions = self.track_instructions.get("1.0", "end").strip()

        # Parse events from text (simple robust parser)
        new_events = []
        text = self.track_events_text.get("1.0", "end")
        for line in text.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    pitch = int(parts[0])
                    start = float(parts[1])
                    dur = float(parts[2])
                    vel = int(parts[3])
                    new_events.append(NoteEvent(pitch=pitch, start=start, duration=dur, velocity=vel, track=self.current_track_name))
                except:
                    continue
        if new_events:
            td.events = new_events

        # Real-time update to project
        self.status_label.configure(text=f"Track '{self.current_track_name}' updated in project", text_color="#00cc88")

        # Optionally re-render a new MIDI from edited project for live/export
        if self.last_generated_path:
            try:
                new_mid = self.current_project.export_full_midi(self.last_generated_path)  # overwrite
                self.status_label.configure(text=f"Track updated + MIDI re-rendered", text_color="#00cc88")
            except Exception as e:
                self.status_label.configure(text=f"Edit applied (re-render failed: {e})", text_color="#ffaa00")

    def _regen_selected_track(self):
        if not self.current_project or not self.current_track_name:
            return
        prompt = self.track_instructions.get("1.0", "end").strip() or f"regenerate {self.current_track_name} musically"
        self.status_label.configure(text=f"Regenerating track {self.current_track_name}...", text_color="#ffaa00")

        def worker():
            try:
                from midi_generator.ai import generate_with_ai
                # Use AI to get fresh events for this track (leverages precise instructions)
                res = generate_with_ai(prompt, base_spec=self.current_project.spec, mode="clip")
                if res.clip and res.clip.events:
                    # Filter/assign to this track
                    new_evs = [e for e in res.clip.events if e.track == self.current_track_name] or res.clip.events
                    # Convert if needed
                    td = self.current_project.tracks[self.current_track_name]
                    td.events = new_evs
                    self.after(0, lambda: self._on_track_select(self.current_track_name))
                    self.after(0, lambda: self.status_label.configure(text=f"Track {self.current_track_name} regenerated", text_color="#00cc88"))
                    # Re-render
                    if self.last_generated_path:
                        self.current_project.export_full_midi(self.last_generated_path)
                else:
                    self.after(0, lambda: self.status_label.configure(text="Regen used fallback (edit manually)", text_color="#ffaa00"))
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(text=f"Regen error: {e}", text_color="#ff5555"))

        threading.Thread(target=worker, daemon=True).start()

    def _humanize_selected_track(self):
        if not self.current_project or not self.current_track_name:
            return
        td = self.current_project.tracks[self.current_track_name]
        import random
        rng = random.Random()
        for ev in td.events:
            ev.velocity = max(1, min(127, ev.velocity + rng.randint(-8, 8)))
            ev.start += rng.uniform(-0.02, 0.02)  # small timing humanization
        self._on_track_select(self.current_track_name)
        self.status_label.configure(text=f"Track {self.current_track_name} humanized (timing/vel)", text_color="#00cc88")
        if self.last_generated_path:
            try:
                self.current_project.export_full_midi(self.last_generated_path)
            except:
                pass

    # Helper to refresh editor after generation (call from _generation_done)
    def _refresh_editor_after_gen(self):
        if self.current_project:
            self._refresh_track_list()

    # ----------------------------- AI + Live additions -----------------------------

    def _refresh_ai_status(self):
        try:
            cfg = load_config()
            if cfg.provider == "none" or not cfg.api_key:
                self.ai_status.configure(text="AI: heuristic fallback (configure API key for real LLMs)", text_color="gray60")
            else:
                self.ai_status.configure(text=f"AI: {cfg.provider} / {cfg.model}", text_color="#66ccff")
        except Exception:
            self.ai_status.configure(text="AI ready (heuristic)")

    def _on_ai_generate(self):
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            prompt = "interesting groovy musical idea"
        self.generate_btn.configure(state="disabled", text="AI thinking...")
        self.ai_generate_btn.configure(state="disabled", text="Generating...")
        self.status_label.configure(text="Calling AI + generator...", text_color="#ffaa00")
        self.output_text.delete("1.0", "end")

        def worker():
            try:
                # Use hybrid path
                path = ai_generate_song(
                    prompt=prompt,
                    base_spec=self._build_spec_from_ui(),
                    mode=self.mode_var.get() if self.mode_var.get() != "Full Song" else "full",
                    duration_seconds=self.duration_slider.get() * 60,
                )
                self.last_generated_path = path
                # also keep a spec snapshot
                self.current_spec = self._build_spec_from_ui()
                self.after(0, lambda: self._generation_done(path, self.current_spec))
            except Exception as e:
                self.after(0, lambda: self._generation_error(str(e)))
            finally:
                self.after(0, self._enable_ai_buttons)

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_variation(self):
        prompt = self.prompt_box.get("1.0", "end").strip() or "similar but with more energy and variation"
        if self.last_generated_path and self.current_spec:
            prompt = f"variation of previous: {prompt}"
        self._on_ai_generate()  # reuses same flow for now

    def _on_batch_generate(self):
        try:
            n = int(self.batch_count.get())
        except:
            n = 5
        prompt = self.prompt_box.get("1.0", "end").strip() or "interesting composition"
        self.status_label.configure(text=f"Batch generating {n} songs...", text_color="#ffaa00")
        self.output_text.delete("1.0", "end")

        def worker():
            from midi_generator.generate import batch_generate
            try:
                base = self._build_spec_from_ui()
                paths = batch_generate(prompt, count=n, base_spec=base, seed=random.randint(1, 999999))
                self.after(0, lambda: self.output_text.insert("1.0", "Batch complete:\n" + "\n".join(paths)))
                if paths:
                    self.last_generated_path = paths[0]
                    self.current_spec = base
                    self.open_finder_btn.configure(state="normal")
                    self.save_project_btn.configure(state="normal")
            except Exception as e:
                self.after(0, lambda: self.output_text.insert("1.0", f"Batch error: {e}"))
            finally:
                self.after(0, lambda: self.status_label.configure(text="Batch done", text_color="#00cc88"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_audio_preview(self):
        if not self.last_generated_path:
            self.status_label.configure(text="Generate a song first for preview", text_color="#ffaa00")
            return
        self.status_label.configure(text="Rendering audio preview...", text_color="#ffaa00")

        def worker():
            from midi_generator.preview import render_preview, play_preview
            try:
                if self.current_project:
                    wav = self.current_project.render_audio_preview()
                else:
                    wav = render_preview(self.last_generated_path)
                if wav:
                    self.after(0, lambda: self.status_label.configure(text=f"Preview ready: {wav.name}", text_color="#00cc88"))
                    # Auto-play on mac
                    play_preview(wav)
                else:
                    self.after(0, lambda: self.status_label.configure(text="Preview failed (see console)", text_color="#ff5555"))
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(text=f"Preview error: {e}", text_color="#ff5555"))

        threading.Thread(target=worker, daemon=True).start()

    def _enable_ai_buttons(self):
        self.generate_btn.configure(state="normal", text="🎵  GENERATE SONG")
        self.ai_generate_btn.configure(state="normal", text="🤖  GENERATE WITH AI")

    def _toggle_live_stream(self):
        if self.player and self.player.is_playing:
            self._stop_live()
            return

        # Prefer edited project events for real-time if available (supports #3 edits in live)
        if self.current_project and any(self.current_project.tracks.values()):
            # Convert project events to the format expected by play_events
            all_events = []
            for tname, td in self.current_project.tracks.items():
                if not td.enabled: continue
                for ev in td.events:
                    all_events.append({"tick": int(ev.start * 480), "raw": {"type": "note_on", "note": ev.pitch, "velocity": ev.velocity, "channel": 0 if "drum" not in tname.lower() else 9}})
            port = self.port_var.get()
            if "no ports" in port or "enable IAC" in port:
                port = find_iac_port() or port
            self.player = MIDIPlayer(port_name=port, callback=self._live_callback)
            self.player.play_events(all_events, bpm=self.current_project.spec.tempo or 120, loop=True)
            self.live_btn.configure(text="⏸ Pause Stream", fg_color="#c45c5c")
            self.status_label.configure(text=f"Streaming EDITED project to {port} (loop)!", text_color="#00cc88")
            return

        path = self.last_generated_path
        if not path or not os.path.exists(path):
            self.status_label.configure(text="Generate something first", text_color="#ffaa00")
            return

        port = self.port_var.get()
        if "no ports" in port or "enable IAC" in port:
            port = find_iac_port() or port

        self.player = MIDIPlayer(port_name=port, callback=self._live_callback)
        ok = self.player.play_midi_file(path, loop=True)
        if ok:
            self.live_btn.configure(text="⏸ Pause Stream", fg_color="#c45c5c")
            self.status_label.configure(text=f"Streaming to {self.player.port_name} (loop) — record in DAW!", text_color="#00cc88")
        else:
            self.status_label.configure(text="Failed to start live MIDI (check port / IAC)", text_color="#ff5555")

    def _stop_live(self):
        if self.player:
            self.player.stop()
            self.live_btn.configure(text="▶ Stream to DAW", fg_color=("#3a7ca5", "#1f6aa5"))
            self.status_label.configure(text="Live stream stopped", text_color="gray70")

    def _live_callback(self, msg: str):
        self.after(0, lambda: self.live_status.configure(text=msg[:120]))

if __name__ == "__main__":
    app = MidiSongApp()
    app.after(100, app._refresh_ai_status)
    app.mainloop()
