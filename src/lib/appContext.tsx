/* appContext.tsx — the single place that talks to the Python bridge.
 * Screens stay presentational: they read state + call actions from useApp().
 * Pull-based: poll get_status() every 200ms (api.subscribeStatus) and call
 * bridge methods on user action. */
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, subscribeStatus, bridgeReady } from "./api";
import type {
  Status, Settings, Options, DeviceInfo, ModelsStatus, HistoryItem,
} from "./types";

export type Route = "home" | "history" | "transcription" | "settings-general" | "settings-audio" | "about";
export type OnboardingStep = "splash" | "welcome" | "permissions" | "hotkey" | "ready" | null;

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
  windowDrag(): Promise<void>;
  navigate(route: Route): void;
  setOnboarding(step: OnboardingStep): void;
  finishOnboarding(): void;
}

export interface AppContextValue {
  status: Status;
  settings: Settings | null;
  options: Options | null;
  devices: DeviceInfo[];
  models: ModelsStatus;
  route: Route;
  onboarding: OnboardingStep;
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
  const [route, setRoute] = useState<Route>("home");
  const [onboarding, setOnboardingStep] = useState<OnboardingStep>("splash");
  const [pastedToast, setPastedToast] = useState<string | null>(null);

  const prevStatus = useRef<Status | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Splash always shows briefly, then first-run onboarding or straight home.
  useEffect(() => {
    let onboarded = false;
    try { onboarded = localStorage.getItem(ONBOARD_KEY) === "1"; } catch {}
    const t = setTimeout(() => setOnboardingStep(onboarded ? null : "welcome"), SPLASH_MS);
    return () => clearTimeout(t);
  }, []);

  // Initial fetch + 200ms status poll, gated on the real bridge being live.
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
        setStatus(next);
        if (prev && prev.state === "processing" && next.state === "idle"
            && next.last_text && next.last_text !== prev.last_text) {
          setPastedToast(next.last_text);
          if (toastTimer.current) clearTimeout(toastTimer.current);
          toastTimer.current = setTimeout(() => setPastedToast(null), TOAST_MS);
        }
        prevStatus.current = next;
      }, 60);
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
      const poll = setInterval(() => { api.models_status().then(setModels).catch(() => {}); }, 500);
      try { await api.download_model(name); } catch (e) { console.error(e); }
      finally {
        clearInterval(poll);
        try { setModels(await api.models_status()); } catch {}
      }
    },
    async refreshModels() {
      try { setModels(await api.models_status()); } catch (e) { console.error(e); }
    },
    async minimize() { try { await api.window_minimize(); } catch (e) { console.error(e); } },
    async close() { try { await api.window_close(); } catch (e) { console.error(e); } },
    async windowDrag() { try { await api.window_drag(); } catch (e) { console.error(e); } },
    navigate(r) { setRoute(r); },
    setOnboarding(step) { setOnboardingStep(step); },
    finishOnboarding() {
      try { localStorage.setItem(ONBOARD_KEY, "1"); } catch {}
      setOnboardingStep(null);
      setRoute("home");
    },
  }), []);
  const value = useMemo<AppContextValue>(() => ({
    status, settings, options, devices, models, route, onboarding, pastedToast, actions,
  }), [status, settings, options, devices, models, route, onboarding, pastedToast, actions]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used within <AppProvider>");
  return v;
}
