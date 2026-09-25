// Onboarding 03 — Permissions & Input Device Setup.
// Allows dynamic auto-detection & switching of input device,
// and shows a live audio waveform visualizer of the input device.
import { useEffect, useState, useRef } from "react";
import { Mic, ArrowLeft, RefreshCw, CheckCircle2 } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { useWaveform } from "../../lib/useLevelHistory";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { PaginationDots } from "../primitives/PaginationDots";
import { SelectField } from "../app/SettingsShell";

const bareName = (s: string) => s.split("—")[0].trim();

function LiveWaveformVisualizer({ level }: { level: number }) {
  const BARS = 18;
  const isSpeaking = level > 0.01;
  // Rolling-history waveform: bars scroll with the voice; calm/flat when silent.
  const heights = useWaveform(level, BARS, 4, 34);

  return (
    <div className="flex h-11 items-center justify-center gap-1.5 px-2 select-none" aria-hidden="true">
      {Array.from({ length: BARS }).map((_, i) => {
        return (
          <span
            key={i}
            className={cn(
              "w-[3.5px] rounded-full transition-[height,background-color,opacity] duration-75 ease-out",
              isSpeaking
                ? "bg-gradient-to-t from-teal to-teal-deep shadow-[0_0_8px_rgba(16,185,129,0.55)] opacity-95"
                : "bg-ink/15 opacity-40"
            )}
            style={{
              height: `${heights[i]}px`,
            }}
          />
        );
      })}
    </div>
  );
}

export function Permissions() {
  const { status, devices, settings, actions } = useApp();
  const [refreshing, setRefreshing] = useState(false);

  const currentDev = settings?.input_device || "";

  // Start live mic preview when on this screen; stop on exit
  useEffect(() => {
    actions.startPreview(currentDev);
    return () => {
      actions.stopPreview();
    };
  }, [currentDev, actions]);

  const micOptions = [
    { value: "", label: "Auto-detect (System Default)" },
    ...devices.map((d) => ({ value: d, label: d })),
  ];

  // Match current setting to options
  let selectedValue = "";
  if (currentDev) {
    const found = devices.find((d) => d === currentDev || bareName(d) === bareName(currentDev));
    if (found) {
      selectedValue = found;
    } else {
      selectedValue = currentDev;
      micOptions.push({ value: currentDev, label: `${bareName(currentDev)} (Current)` });
    }
  }

  const isSpeaking = status.level > 0.01;

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft select-none">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-5 px-8 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <div className="relative flex items-center justify-center">
          <div
            aria-hidden
            className={cn(
              "absolute h-32 w-32 rounded-full transition-all duration-300 blur-2xl",
              isSpeaking ? "bg-teal-soft opacity-90 scale-125" : "bg-accent-soft opacity-70 scale-100"
            )}
          />
          <IconOrb
            icon={<Mic size={32} strokeWidth={1.75} className={cn("transition-transform duration-200", isSpeaking && "scale-110")} />}
            tone={isSpeaking ? "teal" : "accent"}
            size={88}
            className={cn("relative transition-all duration-200", isSpeaking && "shadow-[0_0_24px_rgba(16,185,129,0.4)] scale-105")}
          />
        </div>

        <div className="flex flex-col items-center gap-2">
          <h1 className="text-display font-display text-ink">Microphone setup</h1>
          <p className="max-w-sm text-body text-ink-secondary">
            Say It listens through your microphone to transcribe speech instantly. Your voice stays private and local.
          </p>
        </div>

        {/* Dynamic device picker with auto-detect and refresh */}
        <div className="flex items-center gap-2 max-w-sm w-full justify-center">
          <SelectField
            aria-label="Microphone"
            value={selectedValue}
            options={micOptions}
            className="w-full max-w-[260px] text-caption truncate"
            onValueChange={async (v) => {
              await actions.setDevice(v);
              await actions.startPreview(v);
            }}
          />
          <GlassButton
            variant="secondary"
            size="sm"
            aria-label="Refresh microphones"
            disabled={refreshing}
            icon={<RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />}
            onClick={async () => {
              setRefreshing(true);
              try {
                await actions.refreshDevices();
              } finally {
                setRefreshing(false);
              }
            }}
          />
        </div>

        {/* Live Audio Waveform card */}
        <div className="flex flex-col items-center gap-2 rounded-2xl glass px-6 py-3.5 min-w-[280px] max-w-[340px] shadow-soft-sm">
          <div className="flex items-center justify-center h-10 w-full">
            <LiveWaveformVisualizer level={status.level} />
          </div>
          <div className="flex items-center gap-1.5 text-caption transition-colors duration-200">
            {isSpeaking ? (
              <span className="flex items-center gap-1.5 font-medium text-teal-deep">
                <CheckCircle2 className="h-3.5 w-3.5 text-teal" /> Microphone working properly
              </span>
            ) : (
              <span className="text-ink-tertiary">
                Speak into your mic to test audio…
              </span>
            )}
          </div>
        </div>
      </main>

      <footer className="flex flex-col items-center gap-3 pb-8">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[200px]"
          onClick={() => actions.setOnboarding("hotkey")}
        >
          Continue
        </GlassButton>
        <GlassButton
          variant="ghost"
          size="sm"
          icon={<ArrowLeft size={16} strokeWidth={2} />}
          onClick={() => actions.setOnboarding("welcome")}
        >
          Back
        </GlassButton>
        <PaginationDots count={4} active={1} className="mt-2" />
      </footer>
    </div>
  );
}
