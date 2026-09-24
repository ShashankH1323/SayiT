/* types.ts — shapes mirrored from the pywebview Python bridge (wisper/webui.py
 * Api) and the mock in wisper/web/app.js. Field names are kept identical to
 * what Python returns so the running app keeps working unchanged. */

/** State strings the backend emits (webui.py _STATE_MAP values + mock). */
export type BackendState = "idle" | "recording" | "processing" | "error";

/** App-level view enum (superset of BackendState, plus pre-boot views). */
export type AppState = "loading" | "landing" | "idle" | "recording" | "processing" | "error";

/** get_status() -> live poll payload (~30fps in app.js, 200ms here). */
export interface Status {
  state: BackendState;
  last_text: string;
  last_error: string | null;
  level: number; // 0..1 mic level
}

/** get_settings() -> current config. `input_device` is null when auto. */
export interface Settings {
  hotkey: string;
  input_device: string | null;
  model: string;
  device: string;
  compute_type: string;
  samplerate: number;
  language: string;
  output_language: string;
  cleanup_mode: "light" | "casual" | "formal" | "structured" | "raw";
  stt_provider: "groq" | "local";
  groq_model: "whisper-large-v3-turbo" | "whisper-large-v3";
  sound_effects: boolean;
  history_size: number;
  paste_mode: "auto" | "ctrl_v" | "ctrl_shift_v" | "off";
  noise_suppression: boolean;
  input_threshold: number; // 0..1
  launch_at_login: boolean;
  show_minibar: boolean;
}

/** get_options() -> selectable value lists. */
export interface Options {
  cleanup_modes: string[];
  paste_modes: string[];
  stt_providers: string[];
  groq_models: string[];
  languages: string[];
  local_models: string[];
}

/** A single {value,label} choice derived from an Options array (app.js toOpts). */
export interface OptionEntry {
  value: string;
  label: string;
}

/** list_devices()/refresh_devices() -> plain device label strings. */
export type DeviceInfo = string;

/** history_load() item; history_delete(ts, text) keys off both fields. */
export interface HistoryItem {
  ts: string;
  text: string;
}

/** models_status() -> { "<model name>": downloaded? }. */
export type ModelsStatus = Record<string, boolean>;

/** download_model() return shape. */
export interface ModelInfo {
  name: string;
  downloaded: boolean;
  path: string | null;
  error: string | null;
}

/** download_progress() -> live model-download feed. `pct` is 0..100 when known. */
export interface DownloadProgress {
  active: boolean;
  name: string | null;
  done: boolean;
  error: string | null;
  pct: number | null;
}
