# 05 – Global Hotkeys & Instant Whole-Paragraph Text Injection

Scope: how Wisper toggles recording with a **system-wide hotkey** and then drops the
**entire transcript at once** into whatever text field currently has focus (VS Code,
Notepad, a browser box, the Claude Code terminal). Owns nothing about audio/STT/UI.

---

## Recommendations (read this first)

| Concern | Recommendation |
|---|---|
| **Global hotkey (Windows)** | `keyboard` library, **toggle mode** (press-start / press-stop) as default; **push-to-talk (hold)** as a config option. No admin required, focus-independent, one-line hotkey registration, user-configurable string. Fall back to native `RegisterHotKey` (ctypes) only if you hit anticheat/games or need OS-guaranteed conflict detection. |
| **Text injection** | **Clipboard-set + Ctrl+V paste** as primary — instant, app-agnostic, correct for Unicode/Indic. Save prior clipboard → set `CF_UNICODETEXT` → send paste → restore. **SendInput Unicode (`KEYEVENTF_UNICODE`) typing** as the fallback when paste is blocked. |
| **Terminals** | Detect the foreground window class; send **Ctrl+Shift+V** for terminal apps (Windows Terminal / VS Code integrated terminal / conhost), plain **Ctrl+V** everywhere else. Clipboard paste (not synthetic typing) so the terminal's own **bracketed-paste** framing protects multi-line text. |

Rationale in the sections below.

---

## Part 1 — Global Hotkey

### Requirements

- **System-wide**: fires even when Wisper has no focus / no visible window.
- **Toggle** by default (press to start, press again to stop). **Push-to-talk** (record
  while held) as an option → needs both key-down and key-up.
- **User-configurable** key combo, persisted to config.
- Graceful behaviour when the chosen combo is already taken by another app.

### Library comparison (Windows 11 primary)

| | `keyboard` | `pynput` | Native `RegisterHotKey` (ctypes) |
|---|---|---|---|
| Install | `pip install keyboard` | `pip install pynput` | stdlib `ctypes` only |
| Admin/elevation on Windows | **Not required** | **Not required** | **Not required** |
| Focus-independent | Yes (low-level global hook) | Yes (global listener) | Yes (registered with the OS) |
| Toggle mode | `add_hotkey(cb)` | `GlobalHotKeys({combo: cb})` | `WM_HOTKEY` message on key-down |
| Push-to-talk (hold) | `add_hotkey(..., trigger_on_release=True)` + key hooks, or two `on_press`/`on_release` hooks | `Listener(on_press, on_release)` + flag | **Hard** — only signals on key-down; no key-up event |
| Suppress the key from other apps | Yes (**Windows-only** feature) | `suppress=True` (careful: blocks globally) | No (hotkey still delivered to you, not suppressed) |
| Conflict handling | Silent — hook sees the key regardless; no "already registered" error | Same | **Explicit** — `RegisterHotKey` **fails** if the combo is owned by another app (lets you warn the user) |
| Parse combo from string | `add_hotkey("ctrl+alt+space", …)` | `HotKey.parse("<ctrl>+<alt>+h")` | You map modifiers + VK yourself |
| Threading gotcha | callback runs on hook thread — keep it fast, hand work to a queue | On Windows callbacks run **on an OS thread**; long/blocking work **freezes input system-wide** — dispatch to a worker thread | `WM_HOTKEY` on your message loop — keep the loop responsive |
| Cross-platform | Win + Linux (**Linux needs sudo**, reads raw devices); macOS **experimental** | Win + macOS (**needs Accessibility permission**) + Linux X11; **Wayland unsupported** | Windows-only |
| Maturity | Very mature, tiny API | Mature, actively maintained | OS primitive, rock-solid but verbose |

Sources: keyboard behaviour (no admin on Windows, global hook captures keys regardless of
focus, Windows-only suppression, Linux needs sudo, macOS experimental) confirmed on PyPI.
pynput `HotKey`/`GlobalHotKeys` API and the Windows "callbacks run on an OS thread, don't
block" caveat confirmed in the pynput docs.

### Verdict

Use **`keyboard`**. It is the least code for exactly this job, needs no elevation, and is
focus-independent. Register a toggle handler; for push-to-talk register press/release
hooks on the same combo and start/stop on the transitions.

Keep native `RegisterHotKey` (below) in your back pocket for two situations: (1) the
`keyboard` global hook is swallowed by an anticheat/full-screen game that grabs input
first, or (2) you want the OS to *tell you* the combo is already claimed so you can prompt
the user for a different one — `keyboard` won't detect that conflict.

```python
# keyboard — toggle (default)
import keyboard
recording = False
def toggle():
    global recording
    recording = not recording
    (start_recording if recording else stop_and_inject)()   # hand heavy work to a thread
keyboard.add_hotkey("ctrl+alt+space", toggle)   # combo comes from user config

# keyboard — push-to-talk (option)
keyboard.add_hotkey("ctrl+alt+space", start_recording, trigger_on_release=False)
keyboard.on_release_key("space", lambda e: stop_and_inject())   # or track the full combo
```

```python
# Native fallback: RegisterHotKey via ctypes (Windows) — detects conflicts, no admin
import ctypes
from ctypes import wintypes
u32 = ctypes.windll.user32
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
if not u32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x20):  # 0x20 = VK_SPACE
    ...  # combo already owned by another app — ask the user to pick another
msg = wintypes.MSG()
while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
    if msg.message == 0x0312:   # WM_HOTKEY
        toggle()
```
`RegisterHotKey` only fires on key-down, so push-to-talk needs the hook libraries, not this.

**Make it configurable**: store the combo as a string (e.g. `"ctrl+alt+space"`) plus a
`mode: toggle | push_to_talk` flag in config; re-register on change (`keyboard.remove_hotkey`
/ re-`add_hotkey`). Validate the combo parses before saving.

---

## Part 2 — Text Injection

### The three methods

| Method | Speed | App coverage | Unicode / Indic | Clipboard side-effect | Verdict |
|---|---|---|---|---|---|
| **1. Clipboard + Ctrl+V** | Instant (one paste event) | Nearly universal | Correct — target renders the text via its own layout engine (Devanagari conjuncts, Kannada, combining marks all fine) | Clobbers clipboard (must save/restore) | **Primary** |
| **2. SendInput Unicode typing** (`KEYEVENTF_UNICODE`) | Slow, char-by-char; droppable under load | Broad, but IME/terminals can mangle | Works (UTF-16 units; surrogate pairs for astral) but complex-script sequences and dead keys are riskier | None | **Fallback** |
| **3. Per-app APIs** (UIA `SetValue`, accessibility) | n/a | Only cooperating apps; brittle | Depends | None | **Not viable generally** |

### Why clipboard-paste beats char-by-char typing

- **Speed**: pasting is a single `WM_PASTE`; typing a 300-char paragraph is 300+ synthetic
  key events the target processes one at a time (and may drop if sent too fast).
- **Reliability**: synthetic keystrokes get intercepted by autocomplete, dead keys,
  IME composition, and key-repeat logic. A paste hands the app a finished string.
- **Unicode / Indic**: this is the decisive one. A Devanagari/Kannada grapheme is often
  several code points (base + virama + consonant + matra). As clipboard text the app's
  text engine shapes it correctly. As synthetic keystrokes there is no real keyboard that
  produces those code points directly — you'd rely on `KEYEVENTF_UNICODE` emitting raw
  UTF-16 units, which many apps and *especially* IMEs/terminals reorder or drop. Paste
  sidesteps all of it.

### The clipboard mechanism (save → set → paste → restore)

1. **Save** the current clipboard. Text is easy (`CF_UNICODETEXT`). **Caveat**: the
   clipboard may hold non-text formats (image, HTML, file drop). You can only reliably
   snapshot/restore the *text*; images/rich formats are best-effort or lost. Document this
   as a known limitation — most users copy text, and losing a stray image from the
   clipboard is a minor annoyance vs. the value of instant injection.
2. **Set** the transcript as `CF_UNICODETEXT` (UTF-16). Use `win32clipboard`
   (`pywin32`) or raw `ctypes` (`OpenClipboard`/`EmptyClipboard`/`SetClipboardData`) so
   you control the exact format; `pyperclip` works for the common text case but hides the
   format handling.
3. **Send paste** (Ctrl+V, or Ctrl+Shift+V for terminals — see below) to the **target**
   window.
4. **Restore** the saved clipboard after the paste has been consumed.

**Timing / race concerns** (the sharp edge):

- Paste is **asynchronous** — the target reads the clipboard when it processes the paste
  message, which may be *after* your `SendInput` returns. **Restore too early and you paste
  the old contents.** Add a short delay (≈50–150 ms, tune per machine) between sending the
  paste and restoring, or restore on a timer/next tick.
- A tiny delay (~20–50 ms) between *setting* the clipboard and *sending* the paste avoids
  fast apps reading a half-written clipboard.
- Only one process can own the clipboard at a time; wrap open/close tightly and retry on
  `OpenClipboard` failure (another app may hold it momentarily).

### Edge cases

- **Terminals (Claude Code / VS Code integrated terminal / Windows Terminal / conhost)**:
  plain Ctrl+V is often *not* paste in a terminal — in readline/PSReadLine and many shells
  Ctrl+V is "quoted insert / literal-next". The paste shortcut is usually **Ctrl+Shift+V**.
  Detect the foreground window's class (`GetForegroundWindow` → `GetClassName`) and send
  **Ctrl+Shift+V** for known terminals (Windows Terminal: `CASCADIA_HOSTING_WINDOW_CLASS`;
  legacy console: `ConsoleWindowClass`; VS Code is an Electron window — its integrated
  terminal takes Ctrl+Shift+V). Everywhere else send Ctrl+V.
- **Bracketed paste**: terminals that support it wrap pasted text in `ESC[200~ … ESC[201~`
  so a multi-line paste is treated as data, not as a run of Enter-presses that execute
  commands. This framing only happens on a **real paste** — another reason to *paste*
  into terminals rather than SendInput-type into them (typed newlines would fire commands).
- **Focus at paste time**: capture `GetForegroundWindow()` **when recording starts** and,
  if Wisper ever shows a window, `SetForegroundWindow` back to that handle before pasting —
  otherwise you paste into your own app. If Wisper stays a background/no-window process,
  focus already sits on the target and no restore is needed.
- **Apps that block programmatic paste** (some hardened/secure input fields, certain
  banking or password fields): the paste no-ops. Detect nothing changed if you can, and
  **fall back to SendInput Unicode typing**.
- **Very long text**: clipboard handles megabytes fine; SendInput typing gets painfully
  slow — one more reason clipboard is primary and typing is only the fallback.

### Fallback: SendInput Unicode typing

When paste is blocked, send each character as `KEYEVENTF_UNICODE` (no VK, `wScan` = the
UTF-16 code unit; emit two events for surrogate pairs). Slower and more fragile for Indic,
but it doesn't touch the clipboard and works in fields that reject paste. Chunk with tiny
sleeps to avoid dropped input.

```python
# ctypes SendInput with KEYEVENTF_UNICODE (fallback) — one INPUT per UTF-16 unit
KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x4, 0x2
# for ch in text: for unit in ch.encode('utf-16-le') pairs -> send down+up with wScan=unit
```

---

## Part 3 — Cross-platform notes (portability, brief)

| OS | Hotkey | Inject text | Notes |
|---|---|---|---|
| **Windows 11** (primary) | `keyboard` / `RegisterHotKey` | clipboard + Ctrl+V (Ctrl+Shift+V in terminals) | as above |
| **macOS** | `pynput` (needs **Accessibility** permission) | set `NSPasteboard` → synth **Cmd+V** via `CGEventCreateKeyboardEvent` (Quartz) | app must be granted Accessibility; no admin |
| **Linux / X11** | `keyboard` (needs **root**) or `pynput` (X11) | `xclip`/`xsel` to set clipboard → `xdotool key ctrl+v`, or `xdotool type` | works on X11 |
| **Linux / Wayland** | global capture largely **blocked by design** | `wl-clipboard` (`wl-copy`) + `wtype`, or `ydotool` (needs `uinput`/root) | Wayland restricts synthetic input & global hooks; expect friction |

---

## Assumptions & open questions for synthesis

- **Assumed**: Wisper runs as a background process with no focused window at inject time,
  so the target field keeps focus and no `SetForegroundWindow` dance is needed. If a UI
  window is added, revisit focus restore.
- **Assumed**: losing non-text clipboard contents (image/HTML/files) on injection is an
  acceptable, documented limitation. Confirm with UX owner.
- **Open**: exact paste-consumed delay before clipboard restore is machine-dependent —
  needs empirical tuning (start 100 ms; consider clipboard-viewer/next-tick restore instead
  of a fixed sleep).
- **Open**: reliable programmatic detection of "paste was blocked" to trigger the SendInput
  fallback — may need a heuristic (e.g. verify field changed) or a user-visible fallback toggle.
- **Open**: full list of terminal window classes that need Ctrl+Shift+V (Windows Terminal,
  conhost, VS Code, Alacritty, WezTerm…) — maintain a small classlist in config.
- **Open**: whether to depend on `pywin32` (clean clipboard-format API) vs pure `ctypes`
  (zero deps). Leaning pure `ctypes` + optional `pyperclip` for the simple text path.
- **Dependency choice deferred to synthesis**: `keyboard` vs adding `pynput` — if
  cross-platform (macOS) matters early, `pynput` covers Win+mac in one lib despite the
  Windows callback-threading caveat.

## Sources

- `keyboard` library — PyPI (no admin on Windows, global hook captures keys regardless of
  focus, Windows-only suppression, Linux needs sudo, macOS experimental):
  <https://pypi.org/project/keyboard/>
- `pynput` keyboard docs — `HotKey` / `GlobalHotKeys`, push-to-talk via press/release,
  Windows "callbacks run on an OS thread, don't block" caveat, `suppress`:
  <https://pynput.readthedocs.io/en/latest/keyboard.html>
- `pynput` platform limitations (macOS Accessibility, Linux X11/Wayland):
  <https://pynput.readthedocs.io/en/latest/limitations.html>
- Bracketed paste (xterm `ESC[?2004h`, `ESC[200~ … ESC[201~`; why pasted text is framed):
  <https://en.wikipedia.org/wiki/Bracketed-paste>
- Win32 `RegisterHotKey` / `WM_HOTKEY` (fails when combo already registered; key-down only):
  <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey>
- Win32 `SendInput` + `KEYEVENTF_UNICODE` (inject arbitrary Unicode via `wScan`):
  <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput>
