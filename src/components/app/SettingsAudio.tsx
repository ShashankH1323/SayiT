/* SettingsAudio — Audio settings tab: input device, local speech model +
 * download, and read-only advanced info. Consumer of useApp() only. */
import { useEffect, useState } from "react";
import { Mic, RefreshCw, Boxes, Download, Check, Loader2, Circle, Server, Cpu, Activity } from "lucide-react";
import type { ReactNode } from "react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { SettingRow } from "../primitives/SettingRow";
import { GlassButton } from "../primitives/GlassButton";
import {
  SettingsShell, SettingsSection, SelectField, SettingsLoading, humanize,
} from "./SettingsShell";

// Python strips " — HostAPI" from device labels (_bare_device_name), so match
// the saved (bare) input_device against the full labels list on both sides.
const bareName = (s: string) => s.split("—")[0].trim();
function matchDevice(devices: string[], input: string | null): string {
  if (!input) return "";
  return devices.find((d) => d === input || bareName(d) === bareName(input)) ?? "";
}

function ReadOnlyRow({ label, value, icon, description }: {
  label: string; value: string; icon: ReactNode; description?: string;
}) {
  return (
    <SettingRow label={label} description={description} icon={icon}>
      <span className="rounded-field bg-canvas-soft px-3 py-1 text-caption font-medium text-ink-secondary">
        {value}
      </span>
    </SettingRow>
  );
}

export function SettingsAudio() {
  const { status, settings, options, devices, models, actions, downloadProgress } = useApp();
  const [refreshingDevices, setRefreshingDevices] = useState(false);
  const [testingMic, setTestingMic] = useState(false);

  // Stop any running mic preview if the user navigates away mid-test (idempotent).
  useEffect(() => () => { actions.stopPreview(); }, []);

  if (!settings || !options) {
    return <SettingsShell><SettingsLoading /></SettingsShell>;
  }

  // Microphone options: Auto ("") + current devices; keep a saved-but-missing
  // device visible so the select never silently reads "Auto".
  const micOptions: { value: string; label: string }[] = [
    { value: "", label: "Auto-detect (recommended)" },
    ...devices.map((d) => ({ value: d, label: d })),
  ];
  let micValue = matchDevice(devices, settings.input_device);
  if (!micValue && settings.input_device) {
    micValue = settings.input_device;
    micOptions.push({ value: settings.input_device, label: `${bareName(settings.input_device)} (not connected)` });
  }

  const activeModel = settings.model;
  const activeDownloaded = models[activeModel] === true;
  const activeBusy = !!downloadProgress?.active && downloadProgress.name === activeModel;

  return (
    <SettingsShell>
      <SettingsSection title="Audio Configuration">
        <SettingRow label="Microphone" description="Input device used for dictation." icon={<Mic />}>
          <div className="flex items-center gap-2">
            <SelectField
              aria-label="Microphone"
              value={micValue}
              options={micOptions}
              onValueChange={(v) => actions.setDevice(v)}
            />
            <GlassButton
              variant="secondary"
              size="sm"
              aria-label="Refresh device list"
              disabled={refreshingDevices}
              icon={<RefreshCw className={cn("h-4 w-4", refreshingDevices && "animate-spin")} />}
              onClick={async () => {
                setRefreshingDevices(true);
                try { await actions.refreshDevices(); } finally { setRefreshingDevices(false); }
              }}
            />
          </div>
        </SettingRow>

        {/* Input sensitivity meter matching Card 13 */}
        <SettingRow
          label="Input sensitivity"
          description="Adjust threshold and view live audio response level."
          icon={<Activity />}
        >
          <div className="flex flex-col gap-2 min-w-[200px]">
            <div className="flex items-center gap-1 h-5 px-1 py-0.5 rounded-md bg-canvas-soft border border-hairline">
              {Array.from({ length: 24 }).map((_, i) => {
                const threshold = (i + 1) / 24;
                const active = (status.level || 0) >= threshold * 0.7;
                return (
                  <span
                    key={i}
                    className={cn(
                      "w-1.5 h-3 rounded-full transition-all duration-75",
                      active ? (i > 18 ? "bg-accent" : "bg-teal") : "bg-ink/15"
                    )}
                  />
                );
              })}
            </div>
            <input
              type="range"
              min={10}
              max={100}
              value={Math.round(settings.input_threshold * 100)}
              onChange={(e) => actions.setSetting("input_threshold", Number(e.target.value) / 100)}
              className="h-1.5 w-full accent-accent cursor-pointer"
            />
          </div>
        </SettingRow>

        {/* Noise suppression toggle matching Card 13 */}
        <SettingRow
          label="Noise suppression"
          description="Reduce ambient room noise and keyboard clicks for cleaner transcriptions."
          icon={<Cpu />}
        >
          <button
            type="button"
            role="switch"
            aria-checked={settings.noise_suppression}
            onClick={() => actions.setSetting("noise_suppression", !settings.noise_suppression)}
            className={cn(
              "no-drag relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-pill border-2 border-transparent transition-colors duration-200",
              settings.noise_suppression ? "bg-accent" : "bg-ink/15"
            )}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-soft-sm transition duration-200",
                settings.noise_suppression ? "translate-x-5" : "translate-x-0"
              )}
            />
          </button>
        </SettingRow>

        {/* Test Microphone action button matching Card 13 */}
        <SettingRow
          label="Test microphone"
          description={testingMic ? "Listening... Speak to test level bars above." : "Check if your microphone captures audio clearly."}
          icon={<Mic />}
        >
          <GlassButton
            variant={testingMic ? "primary" : "secondary"}
            size="sm"
            icon={<Mic className={cn("h-4 w-4", testingMic && "animate-pulse text-white")} />}
            onClick={async () => {
              if (testingMic) {
                setTestingMic(false);
                await actions.stopPreview();
              } else {
                setTestingMic(true);
                await actions.startPreview(settings.input_device || undefined);
              }
            }}
          >
            {testingMic ? "Stop test" : "Start test"}
          </GlassButton>
        </SettingRow>
      </SettingsSection>

      <SettingsSection title="Speech model">
        <SettingRow label="Local speech model" description="Whisper model used when the provider is Local." icon={<Boxes />}>
          <div className="flex items-center gap-2">
            <SelectField
              aria-label="Local speech model"
              value={activeModel}
              options={options.local_models.map((m) => ({ value: m, label: humanize(m) }))}
              onValueChange={(v) => actions.setSetting("model", v)}
            />
            <GlassButton
              variant="secondary"
              size="sm"
              aria-label="Refresh model status"
              icon={<RefreshCw className="h-4 w-4" />}
              onClick={() => actions.refreshModels()}
            />
          </div>
        </SettingRow>
        <SettingRow
          label="Model files"
          description={activeDownloaded
            ? `${humanize(activeModel)} is downloaded and ready.`
            : `${humanize(activeModel)} isn't downloaded yet.`}
        >
          {activeDownloaded ? (
            <span className="inline-flex items-center gap-1.5 rounded-pill bg-teal-soft px-3 py-1 text-caption font-medium text-teal-deep">
              <Check className="h-3.5 w-3.5" /> Downloaded
            </span>
          ) : (
            <GlassButton
              size="sm"
              disabled={activeBusy}
              icon={activeBusy
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Download className="h-4 w-4" />}
              onClick={() => actions.downloadModel(activeModel)}
            >
              {activeBusy
                ? (downloadProgress?.pct != null ? `${Math.round(downloadProgress.pct)}%` : "Downloading…")
                : "Download"}
            </GlassButton>
          )}
        </SettingRow>
      </SettingsSection>

      <SettingsSection title="Installed models">
        <p className="pt-2 text-caption text-ink-secondary">
          Local models run 100% on-device for maximum privacy. Accelerated by NVIDIA CUDA or modern multi-core CPUs.
        </p>
        <div className="flex flex-wrap gap-1.5 py-3.5">
          {options.local_models.map((m) => {
            const done = models[m] === true;
            const busy = !!downloadProgress?.active && downloadProgress.name === m;
            return (
              <span
                key={m}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-1 text-caption font-medium",
                  done ? "border-teal/20 bg-teal-soft text-teal-deep" : "border-hairline bg-white text-ink-secondary",
                )}
              >
                {busy
                  ? <Loader2 className="h-3 w-3 animate-spin" />
                  : done
                    ? <Check className="h-3 w-3" />
                    : <Circle className="h-3 w-3 opacity-50" />}
                {humanize(m)}
              </span>
            );
          })}
        </div>
      </SettingsSection>

      <SettingsSection title="Advanced">
        <ReadOnlyRow
          label="Compute acceleration"
          value={humanize(settings.device)}
          icon={<Server />}
          description="NVIDIA CUDA GPU is automatically utilized when available, falling back to CPU."
        />
      </SettingsSection>
    </SettingsShell>
  );
}
