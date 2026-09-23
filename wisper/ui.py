"""Core tkinter control window for Wisper: live state, input-level meter, mic
picker, a Start/Stop toggle, and the last transcription.

State is mutated from a worker thread, so the window POLLS app.state /
app.last_text / app.last_error and app.audio.current_level() every 100 ms
rather than being called back.
# ponytail: poll app.state at 100ms, no thread-safe event plumbing — one window.

Sections are built in separate _build_* methods so a later Settings/Models
panel can be appended without disturbing this layout.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk

from wisper import history, models
from wisper.app import State
from wisper.audio import list_input_devices, refresh_input_devices
from wisper.stt import GROQ_AVAILABLE_MODELS

# State -> (label shown, colour). Amber for any in-flight stage, per spec.
_STATE_VIEW: dict[State, tuple[str, str]] = {
    State.IDLE: ("Idle", "#9e9e9e"),
    State.RECORDING: ("Recording…", "#e53935"),
    State.TRANSCRIBING: ("Transcribing…", "#c07000"),
    State.CLEANING: ("Cleaning…", "#c07000"),
    State.PASTING: ("Pasting…", "#c07000"),
    State.ERROR: ("Error", "#a00"),
}


class WisperUI:
    """Status/control window for a running WisperApp (poll-driven, 100 ms)."""

    def __init__(self, app):
        self.app = app
        self.root = tk.Tk()
        self.root.title("Wisper")
        self.root.minsize(400, 560)
        self.root.geometry("440x660")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda _e: self.app.cancel())

        self._build_tabs()
        self._build_status()
        self._build_meter()
        self._build_mic()
        self._build_controls()
        self._build_transcript()
        self._build_settings()
        self._build_history()

        self._hist_last_text = None  # gate: reload history only when last_text changes
        self._refresh()

    # --- sections ---------------------------------------------------------
    def _build_tabs(self) -> None:
        """A Notebook holding a scrollable Dictate tab (with settings) and a History tab."""
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True)

        # Scrollable Dictate tab
        self._dictate_tab = ttk.Frame(self.nb)
        self.dictate_canvas = tk.Canvas(self._dictate_tab, highlightthickness=0, bg="#f5f5f5")
        self.dictate_sb = ttk.Scrollbar(self._dictate_tab, orient="vertical", command=self.dictate_canvas.yview)
        self._dictate = ttk.Frame(self.dictate_canvas)

        self._dictate.bind(
            "<Configure>",
            lambda _e: self.dictate_canvas.configure(scrollregion=self.dictate_canvas.bbox("all"))
        )
        self._dictate_win = self.dictate_canvas.create_window((0, 0), window=self._dictate, anchor="nw")
        self.dictate_canvas.bind(
            "<Configure>",
            lambda event: self.dictate_canvas.itemconfig(self._dictate_win, width=event.width)
        )
        self.dictate_canvas.configure(yscrollcommand=self.dictate_sb.set)

        self.dictate_canvas.pack(side="left", fill="both", expand=True)
        self.dictate_sb.pack(side="right", fill="y")

        # History tab
        self._history = ttk.Frame(self.nb)

        self.nb.add(self._dictate_tab, text="Dictate")
        self.nb.add(self._history, text="History")
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_status(self) -> None:
        self.status = tk.Label(self._dictate, text="Idle", font=("Segoe UI", 20, "bold"),
                               fg="white", bg="#9e9e9e", pady=12)
        self.status.pack(fill="x")

    def _build_meter(self) -> None:
        # The user's mics are flaky (some silent); this is how they confirm a mic
        # actually hears them. Driven by app.audio.current_level()*100 in refresh.
        tk.Label(self._dictate, text="Input level", font=("Segoe UI", 9)).pack(pady=(6, 0))
        self.level = ttk.Progressbar(self._dictate, orient="horizontal",
                                     mode="determinate", maximum=100)
        self.level.pack(fill="x", padx=10, pady=(0, 4))

    def _build_mic(self) -> None:
        self._mics = list_input_devices()            # [(label, index), ...]
        self._labels = [label for label, _ in self._mics]
        
        lbl_frame = ttk.Frame(self._dictate)
        lbl_frame.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(lbl_frame, text="Microphone", font=("Segoe UI", 9)).pack(side="left")

        mic_row = ttk.Frame(self._dictate)
        mic_row.pack(fill="x", padx=10, pady=(0, 4))
        self.mic = ttk.Combobox(mic_row, state="readonly", values=self._labels)
        self.mic.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._select_current_device()
        self.mic.bind("<<ComboboxSelected>>", self._on_mic_change)

        self.mic_refresh_btn = ttk.Button(mic_row, text="🔄 Refresh", width=10, command=self._on_refresh_mics)
        self.mic_refresh_btn.pack(side="right")

    def _on_refresh_mics(self) -> None:
        """Rescan system audio input devices and refresh combobox."""
        self._mics = refresh_input_devices()
        self._labels = [label for label, _ in self._mics]
        self.mic["values"] = self._labels
        self._select_current_device()

    def _build_controls(self) -> None:
        ctrl_frame = ttk.Frame(self._dictate)
        ctrl_frame.pack(pady=6)

        self.toggle_btn = tk.Button(ctrl_frame, text="Start dictation",
                                    font=("Segoe UI", 12), command=self.app.toggle)
        self.toggle_btn.pack(side="left", padx=4, ipadx=8, ipady=4)

        self.cancel_btn = tk.Button(ctrl_frame, text="Cancel (Esc)",
                                    font=("Segoe UI", 10), command=self.app.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=4, ipadx=4, ipady=4)

    def _build_transcript(self) -> None:
        # Errors displayed cleanly here; no transcript box on Dictate tab (transcripts live in History)
        self.error = tk.Label(self._dictate, text="", fg="#a00", anchor="w",
                              justify="left", wraplength=380, font=("Segoe UI", 9))
        self.error.pack(fill="x", padx=10, pady=(0, 4))

    # --- history tab ------------------------------------------------------
    def _build_history(self) -> None:
        """Scrollable card-based list of past transcripts with copy & delete buttons."""
        f = self._history
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)

        # Header bar with title and Clear All
        hdr = ttk.Frame(f)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 2))
        ttk.Label(hdr, text="Transcription History", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.clear_hist_btn = ttk.Button(hdr, text="🗑️ Clear All", command=self._on_clear_all_history)
        self.clear_hist_btn.pack(side="right")

        self.hist_canvas = tk.Canvas(f, highlightthickness=0, bg="#f5f5f5")
        self.hist_sb = ttk.Scrollbar(f, orient="vertical", command=self.hist_canvas.yview)
        self.hist_container = ttk.Frame(self.hist_canvas)

        self.hist_container.bind(
            "<Configure>",
            lambda _e: self.hist_canvas.configure(scrollregion=self.hist_canvas.bbox("all"))
        )
        self.hist_window = self.hist_canvas.create_window((0, 0), window=self.hist_container, anchor="nw")
        self.hist_canvas.bind(
            "<Configure>",
            lambda event: self.hist_canvas.itemconfig(self.hist_window, width=event.width)
        )
        self.hist_canvas.configure(yscrollcommand=self.hist_sb.set)

        self.hist_canvas.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.hist_sb.grid(row=1, column=1, sticky="ns", pady=(0, 6), padx=(0, 4))

        # Global mousewheel handler so scrolling works everywhere over history and dictate
        self.root.bind_all("<MouseWheel>", self._on_global_mousewheel)

    def _on_global_mousewheel(self, event) -> None:
        """Smooth mousewheel scrolling anywhere over the active tab."""
        try:
            sel = self.nb.select()
            if sel == str(self._history):
                self.hist_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif hasattr(self, "_dictate_tab") and sel == str(self._dictate_tab):
                self.dictate_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_clear_all_history(self) -> None:
        history.clear_all()
        self._reload_history()

    def _on_tab_changed(self, _event=None) -> None:
        """Refresh history when its tab is opened."""
        if self.nb.select() == str(self._history):
            self._reload_history()

    def _reload_history(self) -> None:
        """Repopulate history cards from history.load() (newest first)."""
        for w in self.hist_container.winfo_children():
            w.destroy()

        rows = history.load(self.app.config.history_size)
        if not rows:
            lbl = ttk.Label(self.hist_container, text="No dictation history yet.",
                            foreground="#888", font=("Segoe UI", 10))
            lbl.pack(pady=20, padx=10)
            self._hist_last_text = self.app.last_text
            return

        for r in rows:
            ts = r.get("ts", "")
            txt = r.get("text", "")
            if not txt.strip():
                continue

            card = ttk.LabelFrame(self.hist_container, text=f" {ts} ")
            card.pack(fill="x", padx=8, pady=4, expand=True)

            card_body = ttk.Frame(card)
            card_body.pack(fill="x", padx=6, pady=4, expand=True)

            txt_box = tk.Text(card_body, height=min(4, max(2, len(txt) // 38 + 1)),
                              wrap="word", font=("Segoe UI", 9), relief="flat", bg="#fafafa")
            txt_box.insert("1.0", txt)
            txt_box.config(state="disabled")
            txt_box.pack(side="left", fill="both", expand=True, padx=(0, 6))

            btn_frame = ttk.Frame(card_body)
            btn_frame.pack(side="right", anchor="ne")

            copy_btn = ttk.Button(btn_frame, text="📋 Copy", width=8)

            def _make_copy_cmd(b=copy_btn, t=txt):
                def _do_copy():
                    self.root.clipboard_clear()
                    self.root.clipboard_append(t)
                    b.config(text="✓ Copied")
                    self.root.after(1500, lambda: b.config(text="📋 Copy"))
                return _do_copy

            copy_btn.config(command=_make_copy_cmd(copy_btn, txt))
            copy_btn.pack(side="top", pady=2)

            del_btn = ttk.Button(btn_frame, text="🗑️ Delete", width=8)

            def _make_del_cmd(target_ts=ts, target_txt=txt):
                def _do_del():
                    history.delete_record(target_ts, target_txt)
                    self._reload_history()
                return _do_del

            del_btn.config(command=_make_del_cmd(ts, txt))
            del_btn.pack(side="top", pady=2)

        self._hist_last_text = self.app.last_text

    # --- mic selection ----------------------------------------------------
    @staticmethod
    def _name_of(label: str) -> str:
        """Pure device name from a list_input_devices() label (drops host API)."""
        return label.split(" — ")[0]

    def _select_current_device(self) -> None:
        """Show config.input_device if it matches a device, else the first entry.
        On a config match we also point app.audio at that name so meter+capture
        use the shown mic; on the fallback we leave audio.device alone so
        AudioCapture's auto (WASAPI-default) pick still stands."""
        want = self.app.config.input_device
        for label in self._labels:
            if self._name_of(label) == want:
                self.mic.set(label)
                self.app.audio.device = want
                return
        if self._labels:
            self.mic.set(self._labels[0])

    def _on_mic_change(self, _event=None) -> None:
        label = self.mic.get()
        if not label:
            return
        name = self._name_of(label)          # substring, stable across sessions
        self.app.audio.device = name
        self.app.config.input_device = name
        self.app.config.save()               # persist so it survives restart

    # --- refresh ----------------------------------------------------------
    def _refresh(self) -> None:
        state = self.app.state
        label, colour = _STATE_VIEW.get(state, (state.name.title(), "#9e9e9e"))
        self.status.config(text=label, bg=colour)
        self.level["value"] = self.app.audio.current_level() * 100
        self.toggle_btn.config(
            text="Stop" if state is State.RECORDING else "Start dictation")
        self.cancel_btn.config(
            state="normal" if state is State.RECORDING else "disabled")
        # Lock the mic while capturing/processing; only change it when IDLE.
        self.mic.config(state="readonly" if state is State.IDLE else "disabled")
        self.mic_refresh_btn.config(state="normal" if state is State.IDLE else "disabled")

        # Show the error only while ERROR is the current state. app._process now
        # rests in ERROR (no same-tick flip to IDLE), so the 100 ms poll catches it;
        # the next toggle clears it, so it never lingers under "Idle".
        self.error.config(
            text=f"Error: {self.app.last_error}" if state is State.ERROR else "")
        # Reload history only when a new transcript landed (last_text changed), not
        # every tick; selecting the History tab also refreshes it (_on_tab_changed).
        if self.app.last_text != self._hist_last_text:
            self._reload_history()
        self._poll_download()
        self.root.after(100, self._refresh)

    def run(self) -> None:
        self.root.mainloop()

    def _on_close(self) -> None:
        """Release the mic before destroying the window: closing mid-recording
        must not leak the input device (BUG 2)."""
        try:
            self.app.audio.stop()
        except Exception:
            pass
        self.root.destroy()

    # --- settings / models ------------------------------------------------
    def _build_settings(self) -> None:
        """Settings + model manager appended below the transcript."""
        f = ttk.LabelFrame(self._dictate, text="Settings")
        f.pack(fill="x", padx=10, pady=(0, 8))
        f.columnconfigure(1, weight=1)

        self._dl_thread = None
        self._dl_result = ""
        self._dl_error = False
        self._dl_name = ""

        # 0. STT Engine / Provider
        ttk.Label(f, text="STT Engine").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.provider_cb = ttk.Combobox(
            f, state="readonly", values=["groq (Cloud ~0.3s)", "local (faster-whisper)"]
        )
        current_p = "groq (Cloud ~0.3s)" if getattr(self.app.config, "stt_provider", "groq") == "groq" else "local (faster-whisper)"
        self.provider_cb.set(current_p)
        self.provider_cb.grid(row=0, column=1, columnspan=2, sticky="ew", padx=6, pady=3)
        self.provider_cb.bind("<<ComboboxSelected>>", self._on_provider_change)

        # 1. model picker + download
        ttk.Label(f, text="Model").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.model_cb = ttk.Combobox(f, state="readonly")
        self.model_cb.grid(row=1, column=1, sticky="ew", padx=6, pady=3)
        self.dl_btn = ttk.Button(f, text="Download", command=self._on_download)
        self.dl_btn.grid(row=1, column=2, padx=6, pady=3)
        self.dl_status = ttk.Label(f, text="", foreground="#555", wraplength=340)
        self.dl_status.grid(row=2, column=0, columnspan=3, sticky="w", padx=6)
        self._update_model_dropdown()
        self.model_cb.bind("<<ComboboxSelected>>", self._on_model_change)

        # 2. hotkey editor
        ttk.Label(f, text="Hotkey").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        self.hotkey_entry = ttk.Entry(f)
        self.hotkey_entry.insert(0, self.app.config.hotkey)
        self.hotkey_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=3)
        ttk.Button(f, text="Apply", command=self._on_hotkey_apply).grid(
            row=3, column=2, padx=6, pady=3)
        self.hotkey_status = ttk.Label(
            f, text="format: e.g. ctrl+space, ctrl+alt+d", foreground="#555")
        self.hotkey_status.grid(row=4, column=0, columnspan=3, sticky="w", padx=6)

        # 3. mode / language toggles -> config + save (read live per-utterance)
        self._config_combo(f, 5, "Style / Mode", ["light", "casual", "formal", "structured", "raw"],
                           self.app.config.cleanup_mode, "cleanup_mode")
        self._config_combo(f, 6, "Paste", ["auto", "ctrl_v", "ctrl_shift_v"],
                           self.app.config.paste_mode, "paste_mode")
        langs = ["auto", "en", "hi", "kn", "te", "ta", "mr", "bn", "gu", "es", "fr", "de", "ja"]
        self._config_combo(f, 7, "Input lang", langs,
                           self.app.config.language or "auto", "language",
                           auto_none=True)
        self._config_combo(f, 8, "Output lang", langs,
                           self.app.config.output_language, "output_language")

        # 4. Sound effects toggle (Wisper Flow earcons)
        self.sound_var = tk.BooleanVar(value=getattr(self.app.config, "sound_effects", True))
        def _on_sound_toggle():
            self.app.config.sound_effects = self.sound_var.get()
            self.app.config.save()
        sound_chk = ttk.Checkbutton(f, text="Sound effects (warm audio cues)",
                                    variable=self.sound_var, command=_on_sound_toggle)
        sound_chk.grid(row=9, column=0, columnspan=3, sticky="w", padx=6, pady=4)

    def _config_combo(self, parent, row: int, label: str, values: list[str],
                      current, attr: str, auto_none: bool = False):
        """A readonly combobox bound to an app.config attr (writes + save())."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w",
                                            padx=6, pady=3)
        cb = ttk.Combobox(parent, state="readonly", values=values)
        cb.set(current if current in values else values[0])
        cb.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=3)

        def _on_change(_e=None, attr=attr, cb=cb, auto_none=auto_none):
            val = cb.get()
            setattr(self.app.config, attr,
                    None if (auto_none and val == "auto") else val)
            self.app.config.save()

        cb.bind("<<ComboboxSelected>>", _on_change)
        return cb

    def _update_model_dropdown(self) -> None:
        """Update model combobox values and download button based on active provider."""
        provider = getattr(self.app.config, "stt_provider", "groq")
        if provider == "groq":
            self.model_cb["values"] = list(GROQ_AVAILABLE_MODELS)
            current = getattr(self.app.config, "groq_model", "whisper-large-v3-turbo")
            if current in GROQ_AVAILABLE_MODELS:
                self.model_cb.set(current)
            else:
                self.model_cb.set(GROQ_AVAILABLE_MODELS[0])
            self.dl_btn.config(state="disabled")
            self.dl_status.config(text="Cloud model: ultra-fast (~0.3s) hosted on Groq")
        else:
            self.model_cb["values"] = self._model_labels()
            self._select_current_model()
            self.dl_btn.config(state="normal")
            name = self._selected_model()
            if name and models.is_downloaded(name):
                self.dl_status.config(text=f"Active: {name}")
            elif name:
                self.dl_status.config(text=f"{name} not downloaded - click Download")

    def _on_provider_change(self, _event=None) -> None:
        val = self.provider_cb.get()
        provider = "groq" if "groq" in val else "local"
        self.app.set_stt_provider(provider)
        self._update_model_dropdown()

    def _model_labels(self) -> list[str]:
        """AVAILABLE_MODELS (fast->accurate), each tagged downloaded / not."""
        status = dict(models.model_status())          # offline, no network
        marks = {True: " ✓", False: " ↓"}   # check = have, down = get
        return [n + marks[bool(status.get(n))] for n in models.AVAILABLE_MODELS]

    def _select_current_model(self) -> None:
        try:
            self.model_cb.current(models.AVAILABLE_MODELS.index(self.app.config.model))
        except ValueError:                             # unknown model -> first entry
            if models.AVAILABLE_MODELS:
                self.model_cb.current(0)

    def _selected_model(self) -> str | None:
        """Combobox selection -> model name (index-mapped to AVAILABLE_MODELS)."""
        i = self.model_cb.current()
        return models.AVAILABLE_MODELS[i] if 0 <= i < len(models.AVAILABLE_MODELS) else None

    def _on_model_change(self, _event=None) -> None:
        provider = getattr(self.app.config, "stt_provider", "groq")
        if provider == "groq":
            name = self.model_cb.get()
            if name:
                self.app.set_groq_model(name)
                self.dl_status.config(text=f"Active Groq model: {name}")
            return
        name = self._selected_model()
        if not name:
            return
        if models.is_downloaded(name):
            self.app.set_model(name)                   # active now (lazy, guarded)
            self.dl_status.config(text=f"Active: {name}")
        else:
            self.dl_status.config(text=f"{name} not downloaded - click Download")

    def _on_download(self) -> None:
        if self._dl_thread is not None:                # one download at a time
            return
        name = self._selected_model()
        if not name:
            return
        if models.is_downloaded(name):
            self.app.set_model(name)
            self.dl_status.config(text=f"Active: {name}")
            return
        self._dl_name = name
        self.dl_btn.config(state="disabled")
        self.dl_status.config(text=f"Downloading {name}... (first time can take minutes)")
        self._dl_thread = threading.Thread(
            target=self._download_worker, args=(name,), daemon=True)
        self._dl_thread.start()

    def _download_worker(self, name: str) -> None:
        """Runs OFF the tk thread: sets _dl_result/_dl_error flags only; the
        refresh-loop poll (main thread) owns the widgets.
        # ponytail: is_alive() poll + indeterminate status, no byte-% progress.
        """
        try:
            models.download(name)                      # BLOCKING (background)
            self._dl_result, self._dl_error = "Downloaded ✓", False
        except Exception as e:                         # worker must never vanish silently
            self._dl_result, self._dl_error = f"Download failed: {e}", True

    def _poll_download(self) -> None:
        """Called from _refresh; a no-op unless a download thread just finished.
        Re-enables the button, shows the result, re-tags labels, and activates
        the model on success."""
        t = self._dl_thread
        if t is None or t.is_alive():
            return
        self._dl_thread = None
        self.dl_btn.config(state="normal")
        self.dl_status.config(text=self._dl_result)
        self._refresh_model_labels()
        if not self._dl_error and self._dl_name:
            self.app.set_model(self._dl_name)          # selected + now present -> active
        self._dl_name = ""

    def _refresh_model_labels(self) -> None:
        """Re-tag combobox marks after a download; preserve the selection."""
        i = self.model_cb.current()
        self.model_cb["values"] = self._model_labels()
        if 0 <= i < len(models.AVAILABLE_MODELS):
            self.model_cb.current(i)

    def _on_hotkey_apply(self) -> None:
        value = self.hotkey_entry.get().strip()
        if not value:
            self.hotkey_status.config(text="Enter a hotkey, e.g. ctrl+space")
            return
        before = self.app.last_error
        self.app.set_hotkey(value)                     # guarded, persists, never raises
        err = self.app.last_error
        if err and err != before:                      # only THIS apply's error
            self.hotkey_status.config(text=f"Invalid: {err}")
        else:
            self.hotkey_status.config(text=f"Hotkey updated: {value}")
