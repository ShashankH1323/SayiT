/* api.ts — framework-agnostic bridge to the pywebview Python `Api`
 * (wisper/webui.py). Uses window.pywebview.api when present, else a built-in
 * mock ported from wisper/web/app.js so the UI fully previews in a browser. */
import type {
  Status, Settings, Options, DeviceInfo, HistoryItem, ModelsStatus, ModelInfo,
} from "./types";

declare global {
  interface Window {
    pywebview?: { api: any };
  }
}

function clamp01(v: number): number {
  return v < 0 || isNaN(v) ? 0 : v > 1 ? 1 : v;
}

/* ---------------- mock API (browser preview, no Python) ---------------- */
const mockApi = (() => {
  let state: Status["state"] = "idle", lastText = "", t0 = 0;
  let lastError: string | null = null;
  const devs: DeviceInfo[] = [
    "Pebble Comet Headset — WASAPI", "WO Mic Device — WASAPI",
    "Realtek(R) Audio — WASAPI", "Microphone Array — WASAPI",
  ];
  const st: Settings = {
    hotkey: "ctrl+alt+space", input_device: "Pebble Comet Headset",
    model: "large-v3-turbo", device: "cuda", compute_type: "float16",
    samplerate: 16000, language: "en", output_language: "en",
    cleanup_mode: "light", stt_provider: "groq",
    groq_model: "whisper-large-v3-turbo", sound_effects: true,
    history_size: 50, paste_mode: "auto",
  };
  const mstat: ModelsStatus = {
    tiny: true, base: true, small: true, medium: false, "large-v3": false, turbo: true,
  };
  let hist: HistoryItem[] = [
    { ts: "2026-09-23T12:14:02", text: "Ship the frameless window build, then wire the bridge to the Python side." },
    { ts: "2026-09-23T11:58:40", text: "Remind me to apply scale before the boolean and re-check the mic level meter." },
    { ts: "2026-09-23T10:02:11", text: "The quarterly numbers look strong; draft a short summary for the team." },
    { ts: "2026-09-22T18:41:05", text: "Push the branch and open a PR once the tests pass locally." },
  ];
  const SAMPLE = [
    "That worked perfectly, let us move on to the next part.",
    "Add pagination to the users endpoint and return the total count.",
    "Note to self: the spotlight metaphor is the whole point here.",
  ];
  const delay = <T>(v: T, ms = 55): Promise<T> => new Promise((r) => setTimeout(() => r(v), ms));
  const copy = <T>(o: T): T => JSON.parse(JSON.stringify(o));
  return {
    get_status(): Promise<Status> {
      let level = 0;
      if (state === "recording") {
        const s = (performance.now() - t0) / 1000;
        level = clamp01(0.42 + 0.4 * Math.sin(s * 7.5) * (0.5 + 0.5 * Math.sin(s * 2.3)) + (Math.random() - 0.5) * 0.16);
      }
      return delay({ state, last_text: lastText, last_error: lastError, level });
    },
    toggle(): Promise<null> {
      if (state === "idle" || state === "error") { state = "recording"; lastError = null; t0 = performance.now(); }
      else if (state === "recording") {
        state = "processing";
        setTimeout(() => {
          lastText = SAMPLE[Math.floor(Math.random() * SAMPLE.length)];
          hist.unshift({ ts: new Date().toISOString().slice(0, 19), text: lastText });
          state = "idle";
        }, 1100);
      }
      return delay(null);
    },
    cancel(): Promise<null> { state = "idle"; lastError = null; return delay(null); },
    list_devices(): Promise<DeviceInfo[]> { return delay(devs.slice()); },
    refresh_devices(): Promise<DeviceInfo[]> { return delay(devs.slice(), 400); },
    set_device(name: string): Promise<null> { st.input_device = name; return delay(null); },
    get_settings(): Promise<Settings> { return delay(copy(st)); },
    get_options(): Promise<Options> {
      return delay({
        cleanup_modes: ["light", "casual", "formal", "structured", "raw"],
        paste_modes: ["auto", "ctrl_v", "ctrl_shift_v"],
        stt_providers: ["groq", "local"],
        groq_models: ["whisper-large-v3-turbo", "whisper-large-v3"],
        languages: ["auto", "en", "es", "fr", "de", "hi", "kn", "te", "ta", "mr", "bn", "gu", "ja", "zh"],
        local_models: ["tiny", "base", "small", "medium", "large-v3", "turbo"],
      });
    },
    set_setting(key: string, value: unknown): Promise<null> { (st as any)[key] = value; return delay(null); },
    models_status(): Promise<ModelsStatus> { return delay(copy(mstat)); },
    download_model(name: string): Promise<ModelsStatus> { mstat[name] = true; return delay(copy(mstat), 1500); },
    history_load(size?: number): Promise<HistoryItem[]> { return delay(hist.slice(0, size || 50)); },
    history_delete(ts: string, text: string): Promise<null> {
      hist = hist.filter((r) => !(r.ts === ts && r.text === text)); return delay(null);
    },
    history_clear(): Promise<null> { hist = []; return delay(null); },
    window_minimize(): Promise<null> { console.log("[mock] window_minimize"); return delay(null); },
    window_close(): Promise<null> { console.log("[mock] window_close"); return delay(null); },
  };
})();

function backend(): any {
  return (typeof window !== "undefined" && window.pywebview && window.pywebview.api) || mockApi;
}

/* ---------------- typed bridge surface (mirrors wisper/webui.py Api) ---- */
export const api = {
  get_status: (): Promise<Status> => Promise.resolve(backend().get_status()),
  toggle: (): Promise<null> => Promise.resolve(backend().toggle()),
  cancel: (): Promise<null> => Promise.resolve(backend().cancel()),
  list_devices: (): Promise<DeviceInfo[]> => Promise.resolve(backend().list_devices()),
  refresh_devices: (): Promise<DeviceInfo[]> => Promise.resolve(backend().refresh_devices()),
  set_device: (name: string): Promise<null> => Promise.resolve(backend().set_device(name)),
  get_settings: (): Promise<Settings> => Promise.resolve(backend().get_settings()),
  get_options: (): Promise<Options> => Promise.resolve(backend().get_options()),
  set_setting: (key: string, value: unknown): Promise<null> => Promise.resolve(backend().set_setting(key, value)),
  models_status: (): Promise<ModelsStatus> => Promise.resolve(backend().models_status()),
  download_model: (name: string): Promise<ModelInfo | ModelsStatus> => Promise.resolve(backend().download_model(name)),
  history_load: (size?: number): Promise<HistoryItem[]> => Promise.resolve(backend().history_load(size)),
  history_delete: (ts: string, text: string): Promise<null> => Promise.resolve(backend().history_delete(ts, text)),
  history_clear: (): Promise<null> => Promise.resolve(backend().history_clear()),
  window_minimize: (): Promise<null> => Promise.resolve(backend().window_minimize()),
  window_close: (): Promise<null> => Promise.resolve(backend().window_close()),
};

/* Resolves when the Python bridge is live; in a plain browser resolves after a
 * tick so the mock is used. Mirrors app.js's pywebviewready + 350ms fallback. */
export function bridgeReady(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || (window.pywebview && window.pywebview.api)) {
      resolve();
      return;
    }
    let done = false;
    const go = () => { if (done) return; done = true; resolve(); };
    window.addEventListener("pywebviewready", go); // real bridge, when Python is ready
    setTimeout(go, 350); // otherwise fall back to the mock preview
  });
}

/* Polls get_status and invokes cb with each Status; returns an unsubscribe fn.
 * Re-polls after each response settles (no overlap), like app.js's ~30fps loop. */
export function subscribeStatus(cb: (s: Status) => void, intervalMs = 200): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const tick = () => {
    if (stopped) return;
    api.get_status()
      .then((s) => { if (!stopped && s) cb(s); })
      .catch(() => {})
      .then(() => { if (!stopped) timer = setTimeout(tick, intervalMs); });
  };
  tick();
  return () => { stopped = true; if (timer) clearTimeout(timer); };
}
