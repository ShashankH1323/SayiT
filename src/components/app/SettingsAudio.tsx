/* SettingsAudio — Audio settings tab: input device, local speech model +
 * download, and read-only advanced info. Consumer of useApp() only. */
import { useState } from "react";
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
  const { settings, options, devices, models, actions } = useApp();
  const [downloading, setDownloading] = useState<string | null>(null);
  const [refreshingDevices, setRefreshingDevices] = useState(false);

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
  const activeBusy = downloading === activeModel;

  return (
    <SettingsShell>
      <SettingsSection title="Input">
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
              onClick={async () => {
                setDownloading(activeModel);
                try { await actions.downloadModel(activeModel); } finally { setDownloading(null); }
              }}
            >
              {activeBusy ? "Downloading…" : "Download"}
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
            const busy = downloading === m;
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
