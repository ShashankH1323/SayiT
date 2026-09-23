// HotkeyGuide.tsx — Interactive shortcut guide during onboarding.
// Shows reactive keycaps that illuminate in real-time as the user presses keys,
// allows rebinding to any keyboard or mouse side keys, and confirms readiness.
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Keyboard,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  SlidersHorizontal,
  Sparkles,
  MousePointer,
  RotateCcw,
} from "lucide-react";
import confetti from "canvas-confetti";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { PaginationDots } from "../primitives/PaginationDots";
import {
  formatHotkeyParts,
  formatHotkeyDisplay,
  normalizeHotkey,
  parseKeyboardEvent,
  parseMouseEvent,
  matchesHotkey,
  isMouseHotkey,
} from "../../lib/hotkeyUtils";

export function HotkeyGuide() {
  const { settings, actions } = useApp();
  const currentHotkey = settings?.hotkey || "ctrl+space";
  const hotkeyParts = formatHotkeyParts(currentHotkey);

  const [pressedKeys, setPressedKeys] = useState<Set<string>>(new Set());
  const [success, setSuccess] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editRecordedCombo, setEditRecordedCombo] = useState<string | null>(null);

  // Keep track of pressed physical keys in window
  useEffect(() => {
    if (isEditing) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if editing something else
      const nextPressed = new Set(pressedKeys);
      if (e.ctrlKey) nextPressed.add("ctrl");
      if (e.altKey) nextPressed.add("alt");
      if (e.shiftKey) nextPressed.add("shift");
      if (e.metaKey) nextPressed.add("windows");
      if (e.code === "Space" || e.key === " ") nextPressed.add("space");
      else if (e.code.startsWith("Key")) nextPressed.add(e.code.slice(3).toLowerCase());
      else if (e.code.startsWith("Digit")) nextPressed.add(e.code.slice(5).toLowerCase());
      else if (/^F\d{1,2}$/i.test(e.key)) nextPressed.add(e.key.toLowerCase());
      else nextPressed.add(e.key.toLowerCase());

      setPressedKeys(nextPressed);

      // Check if hotkey matched
      if (matchesHotkey(e, currentHotkey)) {
        e.preventDefault();
        triggerSuccess();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      setPressedKeys((prev) => {
        const next = new Set(prev);
        if (!e.ctrlKey) next.delete("ctrl");
        if (!e.altKey) next.delete("alt");
        if (!e.shiftKey) next.delete("shift");
        if (!e.metaKey) next.delete("windows");
        if (e.code === "Space" || e.key === " ") next.delete("space");
        else if (e.code.startsWith("Key")) next.delete(e.code.slice(3).toLowerCase());
        else if (e.code.startsWith("Digit")) next.delete(e.code.slice(5).toLowerCase());
        else if (/^F\d{1,2}$/i.test(e.key)) next.delete(e.key.toLowerCase());
        else next.delete(e.key.toLowerCase());
        return next;
      });
    };

    const handleMouseDown = (e: MouseEvent) => {
      const mouseHot = parseMouseEvent(e);
      if (mouseHot && normalizeHotkey(mouseHot) === normalizeHotkey(currentHotkey)) {
        e.preventDefault();
        triggerSuccess();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("auxclick", handleMouseDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("auxclick", handleMouseDown);
    };
  }, [currentHotkey, isEditing, pressedKeys]);

  const triggerSuccess = useCallback(() => {
    if (success) return;
    setSuccess(true);
    try {
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.65 },
        colors: ["#3b82f6", "#14b8a6", "#6366f1"],
      });
    } catch {}
  }, [success]);

  // Listener when in "Edit keybinds" mode
  useEffect(() => {
    if (!isEditing) return;

    const onKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const parsed = parseKeyboardEvent(e);
      if (parsed.isEscape) {
        // Cancel edit mode and keep default/current
        setIsEditing(false);
        setEditRecordedCombo(null);
        return;
      }

      if (parsed.hotkey) {
        setEditRecordedCombo(parsed.hotkey);
        actions.setSetting("hotkey", parsed.hotkey);
        setTimeout(() => {
          setIsEditing(false);
          setEditRecordedCombo(null);
        }, 400);
      }
    };

    const onMouseDown = (e: MouseEvent) => {
      const mouseHot = parseMouseEvent(e);
      if (mouseHot) {
        e.preventDefault();
        e.stopPropagation();
        setEditRecordedCombo(mouseHot);
        actions.setSetting("hotkey", mouseHot);
        setTimeout(() => {
          setIsEditing(false);
          setEditRecordedCombo(null);
        }, 400);
      }
    };

    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("mousedown", onMouseDown, true);
    window.addEventListener("auxclick", onMouseDown, true);

    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("mousedown", onMouseDown, true);
      window.removeEventListener("auxclick", onMouseDown, true);
    };
  }, [isEditing, actions]);

  const handleResetDefault = () => {
    actions.setSetting("hotkey", "ctrl+space");
    setIsEditing(false);
  };

  const isMouse = isMouseHotkey(currentHotkey);

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft select-none">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-6 px-8 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <div className="relative flex items-center justify-center">
          <div
            aria-hidden
            className={cn(
              "absolute h-32 w-32 rounded-full opacity-70 blur-2xl transition-colors duration-500",
              success ? "bg-teal-soft" : "bg-accent-soft",
            )}
          />
          <IconOrb
            icon={
              success ? (
                <CheckCircle2 size={36} strokeWidth={2} className="text-teal-deep animate-in zoom-in-75 duration-300" />
              ) : (
                <Keyboard size={34} strokeWidth={1.75} />
              )
            }
            tone={success ? "teal" : "accent"}
            size={88}
            className="relative transition-all duration-300"
          />
        </div>

        <div className="flex flex-col items-center gap-2">
          {success ? (
            <>
              <h1 className="text-display font-display text-ink animate-in fade-in-0 duration-300">
                Okay done, you are good to go!
              </h1>
              <p className="max-w-sm text-body text-teal-deep font-medium">
                You are ready to say it. Press your shortcut anytime from any application.
              </p>
            </>
          ) : (
            <>
              <h1 className="text-display font-display text-ink">
                Try your shortcut
              </h1>
              <p className="max-w-sm text-body text-ink-secondary">
                Press{" "}
                <span className="font-semibold text-ink">
                  {formatHotkeyDisplay(currentHotkey)}
                </span>{" "}
                on your keyboard to test dictation.
              </p>
            </>
          )}
        </div>

        {/* Reactive Key Display Container */}
        <div className="relative flex flex-col items-center gap-4">
          <div
            className={cn(
              "glass rounded-2xl p-6 shadow-soft-lg flex flex-col items-center gap-4 transition-all duration-300 min-w-[320px] max-w-md",
              success && "ring-2 ring-teal shadow-teal-soft",
              isEditing && "ring-2 ring-accent animate-pulse",
            )}
          >
            {isEditing ? (
              <div className="flex flex-col items-center gap-2 py-2">
                <span className="text-caption font-semibold uppercase tracking-wider text-accent">
                  Recording Keybind
                </span>
                <p className="text-body font-medium text-ink">
                  {editRecordedCombo ? formatHotkeyDisplay(editRecordedCombo) : "Press any keys or mouse side button…"}
                </p>
                <span className="text-caption text-ink-tertiary">
                  Hit <kbd className="rounded border px-1.5 py-0.5 text-[11px] bg-canvas">Esc</kbd> to cancel and keep default
                </span>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-center gap-3">
                  {hotkeyParts.map((part, idx) => {
                    const keyLower = part.toLowerCase();
                    const isDown =
                      pressedKeys.has(keyLower) ||
                      (keyLower === "ctrl" && pressedKeys.has("ctrl")) ||
                      (keyLower === "space" && pressedKeys.has("space")) ||
                      (keyLower === "alt" && pressedKeys.has("alt")) ||
                      (keyLower === "shift" && pressedKeys.has("shift")) ||
                      success;

                    return (
                      <div key={idx} className="flex items-center gap-3">
                        <KeyCap
                          label={part}
                          isDown={isDown}
                          success={success}
                        />
                        {idx < hotkeyParts.length - 1 && (
                          <span className="text-ink-tertiary text-lg font-light">+</span>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="flex items-center gap-1.5 text-caption text-ink-tertiary">
                  {success ? (
                    <span className="flex items-center gap-1 text-teal-deep font-medium">
                      <Sparkles size={14} /> Shortcut verified & ready
                    </span>
                  ) : (
                    <span>Keys light up as you press them</span>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Edit keybinds toggle button */}
          {!success && !isEditing && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="no-drag inline-flex items-center gap-1.5 text-caption font-medium text-accent hover:text-accent-deep transition-colors px-3 py-1.5 rounded-pill hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <SlidersHorizontal size={14} />
                Edit keybinds
              </button>
              {currentHotkey !== "ctrl+space" && (
                <button
                  type="button"
                  onClick={handleResetDefault}
                  className="no-drag inline-flex items-center gap-1 text-caption text-ink-tertiary hover:text-ink transition-colors px-2 py-1 rounded-pill"
                >
                  <RotateCcw size={12} />
                  Reset to default
                </button>
              )}
            </div>
          )}
        </div>
      </main>

      <footer className="flex flex-col items-center gap-3 pb-8">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[200px]"
          iconRight={<ArrowRight size={18} strokeWidth={2} />}
          onClick={() => actions.finishOnboarding()}
        >
          {success ? "Start using Say It" : "Continue to Home"}
        </GlassButton>
        <GlassButton
          variant="ghost"
          size="sm"
          icon={<ArrowLeft size={16} strokeWidth={2} />}
          onClick={() => actions.setOnboarding("permissions")}
        >
          Back
        </GlassButton>
        <PaginationDots count={3} active={2} className="mt-2" />
      </footer>
    </div>
  );
}

/**
 * 3D-styled tactile virtual keycap that reacts dynamically to key presses.
 */
function KeyCap({
  label,
  isDown,
  success,
}: {
  label: string;
  isDown: boolean;
  success: boolean;
}) {
  const isWide = label.length > 3 || label === "Space";

  return (
    <div
      className={cn(
        "relative flex items-center justify-center rounded-xl border font-ui font-semibold transition-all duration-100 ease-out select-none",
        isWide ? "min-w-[76px] px-4 h-12 text-sm" : "h-12 w-12 text-base",
        isDown
          ? success
            ? "bg-teal text-white border-teal-deep shadow-inner translate-y-1 scale-95 shadow-teal/30"
            : "bg-accent text-white border-accent-deep shadow-inner translate-y-1 scale-95 shadow-accent/30"
          : "bg-white text-ink border-black/10 shadow-[0_4px_0_0_rgba(0,0,0,0.08)] hover:border-black/20",
      )}
    >
      <span>{label}</span>
      {/* Visual bevel highlight */}
      <div
        className={cn(
          "absolute inset-x-0 top-0 h-1 rounded-t-xl transition-opacity",
          isDown ? "opacity-0" : "bg-white/60",
        )}
      />
    </div>
  );
}
