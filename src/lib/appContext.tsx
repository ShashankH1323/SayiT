import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, subscribeStatus, bridgeReady } from "./api";
import {
  playHapticActivation,
  playHapticDeactivation,
  playHapticSuccess,
  playHapticFailure,
} from "./hapticAudio";
import type {
  Status, Settings, Options, DeviceInfo, ModelsStatus, HistoryItem, DownloadProgress,
} from "./types";

export type Route = "home" | "history" | "transcription" | "settings-general" | "settings-audio" | "about";
export type OnboardingStep = "splash" | "welcome" | "permissions" | "hotkey" | "ready" | null;
export type WindowMode = "full" | "minibar";

export interface AppActions {
  toggle(): Promise<void>;
  cancel(): Promise<void>;
  startPreview(device?: string): Promise<void>;
  stopPreview(): Promise<void>;
  setDevice(name: string): Promise<void>;
  refreshDevices(): Promise<void>;
  setSetting<K extends keyof Settings>(key: K, value: Settings[K]): Promise<void>;
  historyLoad(size?: number): Promise<HistoryItem[]>;
  historyDelete(ts: string, text: string): Promise<void>;
  historyClear(): Promise<void>;
  downloadModel(name: string): Promise<void>;
  refreshModels(): Promise<void>;
  minimize(): Promise<void>;
  close(): Promise<void>;
  quit(): Promise<void>;
  setWindowMode(mode: WindowMode): Promise<void>;
  navigate(route: Route): void;
  setOnboarding(step: OnboardingStep): void;
  finishSplash(): void;
  finishOnboarding(): void;
}

export interface AppContextValue {
  status: Status;
  settings: Settings | null;
  options: Options | null;
  devices: DeviceInfo[];
  models: ModelsStatus;
  downloadProgress: DownloadProgress | null;
  route: Route;
  onboarding: OnboardingStep;
  windowMode: WindowMode;
  pastedToast: string | null;
  actions: AppActions;
}

const IDLE_STATUS: Status = { state: "idle", last_text: "", last_error: null, level: 0 };
const ONBOARD_KEY = "say-it-onboarded";
const SPLASH_MS = 1200;
const TOAST_MS = 2500;

const Ctx = createContext<AppContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(IDLE_STATUS);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [models, setModels] = useState<ModelsStatus>({});
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const [route, setRoute] = useState<Route>("home");
  const [onboarding, setOnboardingStep] = useState<OnboardingStep>("splash");
  const [windowMode, setWindowModeState] = useState<WindowMode>("full");
  const [pastedToast, setPastedToast] = useState<string | null>(null);

  const prevStatus = useRef<Status | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const downloadPoll = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  // Latest sound_effects, read by the mount-once status poll without re-subscribing.
  const soundEnabledRef = useRef(true);
  soundEnabledRef.current = settings?.sound_effects !== false;

  // Clear any lingering model-download poll on unmount.
  useEffect(() => () => { if (downloadPoll.current) clearInterval(downloadPoll.current); }, []);

  // Fallback safety timer for splash screen
  useEffect(() => {
    const t = setTimeout(() => {
      let onboarded = false;
      try { onboarded = localStorage.getItem(ONBOARD_KEY) === "1"; } catch {}
      if (onboarded) {
        setOnboardingStep(null);
        setRoute("home");
        setWindowModeState("full");
        api.set_window_mode("full").catch(() => {});
      } else {
        setOnboardingStep((prev) => (prev === "splash" ? "welcome" : prev));
      }
    }, SPLASH_MS + 1000);
    return () => clearTimeout(t);
  }, []);

  // Sync mode-minibar class to document root for 100% transparent minibar rendering
  useEffect(() => {
    if (windowMode === "minibar") {
      document.documentElement.classList.add("mode-minibar");
      document.body.classList.add("mode-minibar");
    } else {
      document.documentElement.classList.remove("mode-minibar");
      document.body.classList.remove("mode-minibar");
    }
  }, [windowMode]);

  // Initial fetch + status poll with haptic earcons and auto error popup expansion
  useEffect(() => {
    let alive = true;
    let unsub = () => {};
    bridgeReady().then(async () => {
      if (!alive) return;
      const [s, o, d, m] = await Promise.allSettled([
        api.get_settings(), api.get_options(), api.list_devices(), api.models_status(),
      ]);
      if (!alive) return;
      if (s.status === "fulfilled") setSettings(s.value);
      if (o.status === "fulfilled") setOptions(o.value);
      if (d.status === "fulfilled") setDevices(d.value);
      if (m.status === "fulfilled") setModels(m.value);
      unsub = subscribeStatus((next) => {
        const prev = prevStatus.current;
        // Only push a React update when something visible actually changed. The
        // backend returns a fresh Status object every tick even when idle, so an
        // unconditional setStatus re-rendered the WHOLE app (the context value
        // depends on `status`) many times/sec for the app's entire lifetime —
        // heaviest on Permissions (live meter + .glass over animated blobs),
        // which is what froze onboarding. Gating on content (level quantized to
        // ~2%) makes an idle screen do zero re-render work.
        if (
          !prev ||
          prev.state !== next.state ||
          prev.last_text !== next.last_text ||
          prev.last_error !== next.last_error ||
          Math.abs((prev.level || 0) - (next.level || 0)) >= 0.02
        ) {
          setStatus(next);
        }

        // Haptic feedback cues (activation, deactivation, success, failure)
        const soundEnabled = soundEnabledRef.current;
        if (prev && soundEnabled) {
          if (prev.state === "idle" && next.state === "recording") {
            playHapticActivation();
          } else if (prev.state === "recording" && next.state === "processing") {
            playHapticDeactivation();
          } else if (next.state === "error" && prev.state !== "error") {
            playHapticFailure();
          }
        }

        // Auto-expand minibar to large popup if error occurs
        if (next.state === "error") {
          setWindowModeState((currentMode) => {
            if (currentMode === "minibar") {
              api.set_window_mode("full").catch(() => {});
              return "full";
            }
            return currentMode;
          });
        }

        // Paste success toast
        if (prev && prev.state === "processing" && next.state === "idle"
            && next.last_text && next.last_text !== prev.last_text) {
          if (soundEnabled) playHapticSuccess();
          setPastedToast(next.last_text);
          if (toastTimer.current) clearTimeout(toastTimer.current);
          toastTimer.current = setTimeout(() => setPastedToast(null), TOAST_MS);
        }
        prevStatus.current = next;
      }, 80);
    }).catch(() => {});
    return () => { alive = false; unsub(); if (toastTimer.current) clearTimeout(toastTimer.current); };
  }, []);

  const actions = useMemo<AppActions>(() => ({
    async toggle() { try { await api.toggle(); } catch (e) { console.error(e); } },
    async cancel() { try { await api.cancel(); } catch (e) { console.error(e); } },
    async startPreview(device?: string) { try { await api.start_preview(device); } catch (e) { console.error(e); } },
    async stopPreview() { try { await api.stop_preview(); } catch (e) { console.error(e); } },
    async setDevice(name) {
      setSettings((p) => (p ? ({ ...p, input_device: name || null }) : p));
      try { await api.set_device(name); } catch (e) { console.error(e); }
    },
    async refreshDevices() {
      try { setDevices(await api.refresh_devices()); } catch (e) { console.error(e); }
    },
    async setSetting(key, value) {
      setSettings((p) => (p ? ({ ...p, [key]: value } as Settings) : p));
      try { await api.set_setting(key as string, value); } catch (e) { console.error(e); }
    },
    async historyLoad(size) {
      try { return await api.history_load(size); } catch (e) { console.error(e); return []; }
    },
    async historyDelete(ts, text) {
      try { await api.history_delete(ts, text); } catch (e) { console.error(e); }
    },
    async historyClear() { try { await api.history_clear(); } catch (e) { console.error(e); } },
    async downloadModel(name) {
      if (downloadPoll.current) clearInterval(downloadPoll.current);
      downloadPoll.current = setInterval(() => {
        api.models_status().then(setModels).catch(() => {});
        api.download_progress().then((p) => {
          setDownloadProgress(p);
          if (p.done || p.error) {
            if (downloadPoll.current) clearInterval(downloadPoll.current);
            downloadPoll.current = undefined;
            api.models_status().then(setModels).catch(() => {});
          }
        }).catch(() => {});
      }, 500);
      try { await api.download_model(name); } catch (e) {
        console.error(e);
        if (downloadPoll.current) clearInterval(downloadPoll.current);
        downloadPoll.current = undefined;
        try { setModels(await api.models_status()); } catch {}
      }
    },
    async refreshModels() {
      try { setModels(await api.models_status()); } catch (e) { console.error(e); }
    },
    async minimize() { try { await api.window_minimize(); } catch (e) { console.error(e); } },
    async close() {
      // Collapses into floating Mini Bar state as requested
      setWindowModeState("minibar");
      try { await api.set_window_mode("minibar"); } catch (e) { console.error(e); }
    },
    async quit() {
      try { await api.window_quit(); } catch (e) { console.error(e); }
    },
    async setWindowMode(mode: WindowMode) {
      setWindowModeState(mode);
      try { await api.set_window_mode(mode); } catch (e) { console.error(e); }
    },
    navigate(r) { setRoute(r); },
    setOnboarding(step) { setOnboardingStep(step); },
    finishSplash() {
      let onboarded = false;
      try { onboarded = localStorage.getItem(ONBOARD_KEY) === "1"; } catch {}
      if (onboarded) {
        setOnboardingStep(null);
        setRoute("home");
        setWindowModeState("full");
        api.set_window_mode("full").catch(() => {});
      } else {
        setOnboardingStep("welcome");
      }
    },
    finishOnboarding() {
      try { localStorage.setItem(ONBOARD_KEY, "1"); } catch {}
      setOnboardingStep(null);
      setRoute("home");
      setWindowModeState("full");
      api.set_window_mode("full").catch(() => {});
    },
  }), []);

  const value = useMemo<AppContextValue>(() => ({
    status, settings, options, devices, models, downloadProgress, route, onboarding, windowMode, pastedToast, actions,
  }), [status, settings, options, devices, models, downloadProgress, route, onboarding, windowMode, pastedToast, actions]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used within <AppProvider>");
  return v;
}
