/* SettingsGeneral — General settings tab. Every control is a consumer of
 * useApp(); writes go through actions.setSetting (optimistic). */
import { useEffect, useState } from "react";
import {
  Globe, Languages, Cloud, Cpu, Sparkles, ClipboardPaste, Volume2, ListOrdered, Keyboard,
} from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { SettingRow } from "../primitives/SettingRow";
import {
  SettingsShell, SettingsSection, SelectField, SettingsLoading, humanize, langLabel,
} from "./SettingsShell";

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

/** Number field that commits on blur / Enter (fewer bridge writes than per-keystroke). */
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
      className="no-drag h-9 w-24 rounded-field border border-hairline bg-white px-3 text-right text-label text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
    />
  );
}

/** Editable hotkey box (kbd style); commits on blur / Enter. */
function HotkeyField({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const commit = () => {
    const v = draft.trim();
    if (v && v !== value) onCommit(v);
    else setDraft(value);
  };
  return (
    <input
      aria-label="Recording hotkey"
      value={draft}
      spellCheck={false}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      className="no-drag h-9 w-44 rounded-field border border-hairline bg-canvas-soft px-3 text-center text-label tracking-wide text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
    />
  );
}

export function SettingsGeneral() {
  const { settings, options, actions } = useApp();

  return (
    <SettingsShell>
      {!settings || !options ? (
        <SettingsLoading />
      ) : (
        <>
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

          <SettingsSection title="Transcription">
            <SettingRow label="Speech provider" description="Where transcription runs." icon={<Cloud />}>
              <Segmented
                label="Speech provider"
                value={settings.stt_provider}
                options={options.stt_providers}
                onChange={(v) => actions.setSetting("stt_provider", v)}
              />
            </SettingRow>
            {settings.stt_provider === "groq" && (
              <SettingRow label="Groq model" description="Cloud model used with the Groq provider." icon={<Cpu />}>
                <SelectField
                  aria-label="Groq model"
                  value={settings.groq_model}
                  options={options.groq_models.map((m) => ({ value: m, label: humanize(m) }))}
                  onValueChange={(v) => actions.setSetting("groq_model", v)}
                />
              </SettingRow>
            )}
            <SettingRow label="Cleanup mode" description="How transcripts are tidied before pasting." icon={<Sparkles />}>
              <SelectField
                aria-label="Cleanup mode"
                value={settings.cleanup_mode}
                options={options.cleanup_modes.map((m) => ({ value: m, label: humanize(m) }))}
                onValueChange={(v) => actions.setSetting("cleanup_mode", v)}
              />
            </SettingRow>
          </SettingsSection>

          <SettingsSection title="Behavior">
            <SettingRow label="Paste mode" description="How text lands at your cursor." icon={<ClipboardPaste />}>
              <SelectField
                aria-label="Paste mode"
                value={settings.paste_mode}
                options={options.paste_modes.map((m) => ({ value: m, label: humanize(m) }))}
                onValueChange={(v) => actions.setSetting("paste_mode", v)}
              />
            </SettingRow>
            <SettingRow label="Sound effects" description="Play a cue when recording starts and stops." icon={<Volume2 />}>
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
            <SettingRow label="Hotkey" description="Shortcut to start and stop dictation." icon={<Keyboard />}>
              <HotkeyField value={settings.hotkey} onCommit={(v) => actions.setSetting("hotkey", v)} />
            </SettingRow>
          </SettingsSection>
        </>
      )}
    </SettingsShell>
  );
}
