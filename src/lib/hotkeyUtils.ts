/**
 * hotkeyUtils.ts — canonical parsing, normalization, formatting, and detection
 * for keyboard & mouse hotkeys in Say It.
 */

export interface ParsedHotkey {
  canonical: string;       // e.g. "ctrl+space", "mouse4", "ctrl+mouse4"
  parts: string[];         // e.g. ["Ctrl", "Space"], ["Mouse 4"]
  display: string;         // e.g. "Ctrl + Space", "Mouse 4 (Side)"
  isMouse: boolean;
  mouseButton?: "mouse4" | "mouse5" | "middle" | "right";
}

const MODIFIER_ORDER = ["ctrl", "alt", "shift", "windows"];

export const MOUSE_BUTTON_NAMES: Record<string, string> = {
  mouse4: "Mouse 4",
  mouse5: "Mouse 5",
  middle: "Middle Click",
  right: "Right Click",
};

/**
 * Normalizes any hotkey string to standard canonical form (e.g. "ctrl+space").
 */
export function normalizeHotkey(raw: string): string {
  if (!raw || !raw.trim()) return "ctrl+space";
  let s = raw.trim().toLowerCase();

  // Normalize spaces and multi-word names
  s = s.replace(/mouse\s*4|side\s*(button\s*)?1|x1|\bback\b/g, "mouse4");
  s = s.replace(/mouse\s*5|side\s*(button\s*)?2|x2|\bforward\b/g, "mouse5");
  s = s.replace(/mouse\s*3|middle\s*click/g, "middle");
  s = s.replace(/mouse\s*2|right\s*click/g, "right");

  const tokens = s.replace(/[+\-_]/g, " ").split(/\s+/).filter(Boolean);
  const modifiers = new Set<string>();
  let primaryKey = "";

  for (const t of tokens) {
    if (t === "ctrl" || t === "control") modifiers.add("ctrl");
    else if (t === "alt" || t === "option") modifiers.add("alt");
    else if (t === "shift") modifiers.add("shift");
    else if (t === "win" || t === "cmd" || t === "windows" || t === "super" || t === "meta") modifiers.add("windows");
    else if (t in MOUSE_BUTTON_NAMES) primaryKey = t;
    else primaryKey = t;
  }

  const result: string[] = [];
  for (const m of MODIFIER_ORDER) {
    if (modifiers.has(m)) result.push(m);
  }
  if (primaryKey) result.push(primaryKey);

  return result.join("+") || "ctrl+space";
}

/**
 * Returns clean capitalized parts for rendering individual keycaps (e.g. ["Ctrl", "Space"]).
 */
export function formatHotkeyParts(hotkey: string): string[] {
  const norm = normalizeHotkey(hotkey);
  return norm.split("+").map((p) => {
    switch (p) {
      case "ctrl":
        return "Ctrl";
      case "alt":
        return "Alt";
      case "shift":
        return "Shift";
      case "windows":
        return "Win";
      case "space":
        return "Space";
      case "mouse4":
        return "Mouse 4";
      case "mouse5":
        return "Mouse 5";
      case "middle":
        return "Middle Click";
      case "right":
        return "Right Click";
      case "enter":
        return "Enter";
      case "backspace":
        return "Backspace";
      default:
        return p.length <= 3 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1);
    }
  });
}

/**
 * Returns formatted string like "Ctrl + Space" or "Mouse 4 (Side)".
 */
export function formatHotkeyDisplay(hotkey: string): string {
  const parts = formatHotkeyParts(hotkey);
  return parts.join(" + ");
}

/**
 * Checks whether a hotkey string involves a mouse button.
 */
export function isMouseHotkey(hotkey: string): boolean {
  const norm = normalizeHotkey(hotkey);
  return /(mouse4|mouse5|middle|right)/.test(norm);
}

/**
 * Translates a KeyboardEvent into a canonical hotkey string, or null if only modifiers held.
 */
export function parseKeyboardEvent(e: KeyboardEvent): { hotkey: string | null; isEscape: boolean } {
  if (e.key === "Escape" || e.code === "Escape") {
    return { hotkey: null, isEscape: true };
  }

  // Modifiers alone do not complete a keybind
  const isModOnly = ["Control", "Alt", "Shift", "Meta"].includes(e.key);
  if (isModOnly) {
    return { hotkey: null, isEscape: false };
  }

  const parts: string[] = [];
  if (e.ctrlKey) parts.push("ctrl");
  if (e.altKey) parts.push("alt");
  if (e.shiftKey) parts.push("shift");
  if (e.metaKey) parts.push("windows");

  let keyPart = "";
  if (e.code === "Space" || e.key === " ") {
    keyPart = "space";
  } else if (e.code.startsWith("Key")) {
    keyPart = e.code.slice(3).toLowerCase();
  } else if (e.code.startsWith("Digit")) {
    keyPart = e.code.slice(5).toLowerCase();
  } else if (/^F\d{1,2}$/i.test(e.key)) {
    keyPart = e.key.toLowerCase();
  } else {
    keyPart = e.key.toLowerCase();
  }

  if (keyPart && !parts.includes(keyPart)) {
    parts.push(keyPart);
  }

  return { hotkey: parts.join("+"), isEscape: false };
}

/**
 * Translates a MouseEvent / PointerEvent into a canonical hotkey string (including modifiers).
 */
export function parseMouseEvent(e: MouseEvent): string | null {
  let mouseBtn = "";
  if (e.button === 3) mouseBtn = "mouse4"; // Back / Side button 1
  else if (e.button === 4) mouseBtn = "mouse5"; // Forward / Side button 2
  else if (e.button === 1) mouseBtn = "middle"; // Middle wheel click
  else if (e.button === 2) mouseBtn = "right";  // Right click
  else return null; // Ignore standard left click so clicking buttons works

  const parts: string[] = [];
  if (e.ctrlKey) parts.push("ctrl");
  if (e.altKey) parts.push("alt");
  if (e.shiftKey) parts.push("shift");
  if (e.metaKey) parts.push("windows");
  parts.push(mouseBtn);

  return parts.join("+");
}

/**
 * Matches a KeyboardEvent against the configured hotkey.
 */
export function matchesHotkey(e: KeyboardEvent, hotkey: string): boolean {
  if (!hotkey) return false;
  const norm = normalizeHotkey(hotkey);
  const parts = norm.split("+");
  const reqCtrl = parts.includes("ctrl");
  const reqAlt = parts.includes("alt");
  const reqShift = parts.includes("shift");
  const reqWin = parts.includes("windows");
  const mainKeys = parts.filter((p) => !["ctrl", "alt", "shift", "windows"].includes(p));

  if (e.ctrlKey !== reqCtrl) return false;
  if (e.altKey !== reqAlt) return false;
  if (e.shiftKey !== reqShift) return false;
  if (e.metaKey !== reqWin) return false;

  if (mainKeys.length === 0) return false;
  const main = mainKeys[0];

  if (main === "space") {
    return e.code === "Space" || e.key === " ";
  }
  if (main.length === 1) {
    return e.key.toLowerCase() === main || e.code.toLowerCase() === `key${main}`;
  }
  if (/^f\d{1,2}$/.test(main)) {
    return e.key.toLowerCase() === main;
  }
  return e.key.toLowerCase() === main || e.code.toLowerCase() === main;
}
