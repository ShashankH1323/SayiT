/* SettingsGeneral — General settings tab. Every control is a consumer of
 * useApp(); writes go through actions.setSetting (optimistic). */
import { useEffect, useState } from "react";
import {
  Globe, Languages, ClipboardPaste, Volume2, ListOrdered, Keyboard,
} from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { SettingRow } from "../primitives/SettingRow";
import {
  SettingsShell, SettingsSection, SelectField, SettingsLoading, humanize, langLabel,
} from "./SettingsShell";
import { formatHotkeyParts } from "../../lib/hotkeyUtils";

/* ---- local controls (single-use here; not shared primitives) ---- */

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={cn(
        "no-drag relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-pill border-2 border-transparent transition-colors duration-200 ease-in-out",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
        checked ? "bg-accent" : "bg-ink/15",
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-soft-sm ring-0 transition duration-200 ease-in-out",
          checked ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  );
}

function Segmented({ value, options, onChange, label }: {
  value: string; options: string[]; onChange: (v: string) => void; label: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="no-drag inline-flex gap-1 rounded-field border border-hairline bg-canvas-soft p-1"
    >
      {options.map((o) => {
        const active = value === o;
        return (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o)}
            className={cn(
              "h-8 whitespace-nowrap rounded-[9px] px-3 text-caption font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1",
              active ? "bg-white text-accent shadow-soft-sm" : "text-ink-secondary hover:text-ink",
            )}
          >
            {humanize(o)}
          </button>
        );
      })}
    </div>
  );
}

/** Compact number field that commits on blur / Enter (no spinner arrows, snugly centered). */
function NumberField({ value, onCommit, label }: { value: number; onCommit: (n: number) => void; label: string }) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const commit = () => {
    const n = Math.max(1, Math.round(Number(draft) || 0));
    onCommit(n);
    setDraft(String(n));
  };
  return (
    <input
      type="number"
      min={1}
      inputMode="numeric"
      aria-label={label}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      className="no-drag h-8 w-14 rounded-field border border-hairline bg-white px-1 text-center text-label font-semibold text-ink [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
    />
  );
}

/** Tactile hotkey button with background blur and distinct clickable feel (fixed to Control Space). */
function HotkeyButton({ value }: { value: string }) {
  const parts = formatHotkeyParts(value || "ctrl+space");

  return (
    <button
      type="button"
      className="no-drag inline-flex h-9 items-center gap-1.5 rounded-pill border border-hairline bg-white/70 backdrop-blur-md px-3.5 transition-colors hover:bg-white/90 active:scale-[0.98] focus-visible:outline-none"
    >
      <div className="flex items-center gap-1.5">
        {parts.map((p, idx) => (
          <span key={idx} className="flex items-center gap-1.5">
            <kbd className="rounded-md bg-canvas-soft/90 px-2 py-0.5 font-ui text-[12px] font-semibold text-ink border border-hairline">
              {p}
            </kbd>
            {idx < parts.length - 1 && <span className="text-[11px] font-medium text-ink-tertiary">+</span>}
          </span>
        ))}
      </div>
    </button>
  );
}

export function SettingsGeneral() {
  const { settings, options, actions } = useApp();
  const [launchAtLogin, setLaunchAtLogin] = useState(() => {
    try { return localStorage.getItem("say-it-launch-login") === "1"; } catch { return false; }
  });
  const [showMiniBar, setShowMiniBar] = useState(() => {
    try { return localStorage.getItem("say-it-show-minibar") !== "0"; } catch { return true; }
  });

  const toggleLaunchAtLogin = () => {
    const next = !launchAtLogin;
    setLaunchAtLogin(next);
    try { localStorage.setItem("say-it-launch-login", next ? "1" : "0"); } catch {}
  };

  const toggleShowMiniBar = () => {
    const next = !showMiniBar;
    setShowMiniBar(next);
    try { localStorage.setItem("say-it-show-minibar", next ? "1" : "0"); } catch {}
  };

  const isAutoPaste = settings?.paste_mode !== "off";

  return (
    <SettingsShell>
      {!settings || !options ? (
        <SettingsLoading />
      ) : (
        <>
          <SettingsSection title="General Preferences">
            <SettingRow
              label="Launch at login"
              description="Start Say It automatically when Windows starts."
              icon={<Globe />}
            >
              <Toggle
                label="Launch at login"
                checked={launchAtLogin}
                onChange={toggleLaunchAtLogin}
              />
            </SettingRow>

            <SettingRow
              label="Show mini bar"
              description="Float a compact recording pill when idle or minimized."
              icon={<ClipboardPaste />}
            >
              <Toggle
                label="Show mini bar"
                checked={showMiniBar}
                onChange={toggleShowMiniBar}
              />
            </SettingRow>

            <SettingRow
              label="Auto paste"
              description="Automatically paste transcriptions at your cursor."
              icon={<ClipboardPaste />}
            >
              <Toggle
                label="Auto paste"
                checked={isAutoPaste}
                onChange={() => actions.setSetting("paste_mode", isAutoPaste ? "off" : "auto")}
              />
            </SettingRow>

            <SettingRow
              label="Hotkey"
              description="Shortcut to start and stop dictation."
              icon={<Keyboard />}
            >
              <div className="flex items-center gap-2">
                <HotkeyButton value={settings.hotkey} />
                <button
                  type="button"
                  onClick={() => actions.setOnboarding("hotkey")}
                  className="rounded-field border border-hairline bg-white px-2.5 py-1 text-caption font-semibold text-accent hover:bg-accent-soft transition-colors"
                >
                  Change
                </button>
              </div>
            </SettingRow>
          </SettingsSection>

          <SettingsSection title="Language">
            <SettingRow label="Spoken language" description="The language you dictate in." icon={<Globe />}>
              <SelectField
                aria-label="Spoken language"
                value={settings.language}
                options={options.languages.map((c) => ({ value: c, label: langLabel(c) }))}
                onValueChange={(v) => actions.setSetting("language", v)}
              />
            </SettingRow>
            <SettingRow
              label="Output / translation language"
              description="Transcribe or translate into this language."
              icon={<Languages />}
            >
              <SelectField
                aria-label="Output language"
                value={settings.output_language}
                options={options.languages.map((c) => ({ value: c, label: langLabel(c) }))}
                onValueChange={(v) => actions.setSetting("output_language", v)}
              />
            </SettingRow>
          </SettingsSection>

          <SettingsSection title="Audio Feedback & History">
            <SettingRow label="Sound effects (Haptics)" description="Play tactile haptic audio cues when recording and pasting." icon={<Volume2 />}>
              <Toggle
                label="Sound effects"
                checked={settings.sound_effects}
                onChange={() => actions.setSetting("sound_effects", !settings.sound_effects)}
              />
            </SettingRow>
            <SettingRow label="History size" description="How many transcripts to keep." icon={<ListOrdered />}>
              <NumberField
                label="History size"
                value={settings.history_size}
                onCommit={(n) => actions.setSetting("history_size", n)}
              />
            </SettingRow>
          </SettingsSection>
        </>
      )}
    </SettingsShell>
  );
}
