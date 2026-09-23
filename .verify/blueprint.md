# Say It — UI Design Blueprint

> Faithful Markdown conversion of `Say_It_UI_Research_and_Claude_Code_Blueprint.docx`.
> Source of truth for building the "Say It" desktop dictation UI (React + Vite + Tailwind,
> single-file build in `dist/`, loaded by a pywebview window sized 720×720).
> The reference board image is extracted to `blueprint-assets/mockup-01.png` and described inline in section 0.

## Blueprint Outline

Reusable primitives (build these before screens — per sections 4 & 8):
1. SoftBlobBackground — deterministic absolute-positioned pastel SVG/CSS blobs (fixed geometry/blur/opacity).
2. SayItMark — logo SVG: three overlapping rounded organic vertical forms, blue→violet→pink gradient, slight translucency. Reused everywhere.
3. SayItWordmark — "Say It" text lockup in deep navy.
4. WindowFrame — lightweight desktop chrome: three small traffic-light dots (left) + minimal top-right window controls (minimize/maximize/close).
5. GlassButton — rounded translucent CTA/button treatment.
6. IconOrb — radial/glass circular shell wrapping a Lucide icon (mic / check).
7. SidebarItem — compact nav item; active = quiet tinted pill (not a loud filled button).
8. StatusPill — status indicator (e.g. Ready).
9. MiniBar — single stable component with 4 visual states (idle/listening/processing/pasted); outer pill geometry + position never change.
10. SettingRow — label/control row for settings.
11. SearchField — search input.
12. PaginationDots — onboarding step dots.

Screens (implement in the order given by section 7: Home → Mini Bar states → History → Settings General → Settings Audio → About → onboarding):
- 01 Splash / Loading — BrandMark + BrandWordmark + SoftBlobBackground + ProgressBar.
- 02 Welcome / Onboarding — WindowFrame + IllustrationPanel + CTA + PaginationDots.
- 03 Permissions — WindowFrame + PermissionCard + MicOrb + PrimaryButton.
- 04 Ready — WindowFrame + SuccessOrb + CTA + PaginationDots.
- 05 Home (Main App) — AppShell + Sidebar + HomeView + MicOrb + StatusBar. (Most important production screen.)
- 06 Mini Bar / Idle — FloatingMiniBar.
- 07 Mini Bar / Listening — FloatingMiniBar + Waveform + StopButton.
- 08 Mini Bar / Processing — FloatingMiniBar + ProcessingSpinner.
- 09 Mini Bar / Pasted — FloatingMiniBar + CheckIndicator.
- 10 Mini Bar / Back to Idle — FloatingMiniBar (visually identical to 06).
- 11 History — AppShell + SearchInput + TranscriptList + Timestamp + PreviewText.
- 12 Settings / General — AppShell + SettingRows + Switch + HotkeyField + Select.
- 13 Settings / Audio — AppShell + Select + Meter + Switch + TestButton.
- 14 About — AppShell + BrandMark + Version + LinkRows.

Board-only marketing chrome (present on the reference board, NOT app screens — do not build into the app): header wordmark + tagline "From your voice to your work.", handwritten notes "Ideas flow better spoken." / "Think it. Say it. Done.", the "Fast · Private · Always with you" dot legend, and the footer strip.

## Design Tokens

From section 5 (approximate values inferred from the raster, to be locked into CSS variables — do NOT scatter raw hex through components):

| Token | Approx value | Usage |
|---|---|---|
| Canvas | #FAFAFC–#FFFFFF family | Very light warm/neutral white; not a pure flat #FFF surface. |
| Primary ink | #0B1640 / deep navy | Headings and high-priority text. |
| Secondary text | ~#52658F | Descriptions, helper text, captions. |
| Accent blue-violet | ~#5A5BFF | Primary CTA, active nav, microphone/check accent. |
| Soft purple | ~#C8B8FF | Background blob + glass glow family. |
| Soft pink | ~#F2C8EE | Background blob family. |
| Soft cyan | ~#C8EAF4 | Background blob family. |
| Glass | rgba(255,255,255,0.65–0.85) | Cards/buttons over pastel background. |
| Border | rgba(100,120,200,0.12–0.22) | Thin, low-contrast borders. |
| Shadow | 0 8–30px rgba(70,80,160,0.10–0.16) | Soft diffuse shadow, never a hard dark drop shadow. |
| Radius | 12–20px | Cards/windows; mini bar is pill-shaped (fully rounded). |
| Stroke | 1.5–2px | Lucide icon stroke; keep consistent. |

Typography: Inter or Manrope for UI text; Caveat (handwriting) for the marketing accent notes only. Full type scale/weights/line-heights not numerically specified — infer from raster; headings are navy semibold/bold, body is muted blue-gray. Green/teal is used for the "Ready" status dot and the audio level meter (observed in raster; not tokenized in the doc).

Icons: Lucide React, one family only — Mic, Home, History, Settings, Search, Check, Globe, Lock, Volume. Animation: Motion for React, only where the reference implies movement (state transitions, active sidebar indicator, subtle entrance/exit, mini-bar state morphing).

---

# SAY IT — UI RESEARCH + PINPOINT-IMPLEMENTATION BLUEPRINT

How to recreate the supplied 1536×1024 reference board in an existing React/Tauri-style codebase with Claude Code

## 0. Reference board image — `blueprint-assets/mockup-01.png`

The document embeds one image (1536×1024, RGBA): the master reference board, placed between the subtitle and section 1. It is a single light canvas showing all 14 app screens laid out in 3 rows, connected by violet chevron arrows, with marketing chrome around the edges. Precise description:

**Global background & chrome:** Soft warm-white canvas (not pure #FFF) with blurred pastel organic blobs (soft purple, pink, cyan) bleeding in from the corners/edges. Top-left corner: the Say It logo mark (three overlapping soft-gradient vertical blobs shading blue → violet → pink) beside the "Say It" wordmark in bold deep-navy, with the tagline "From your voice to your work." in blue-violet directly beneath. Top-right: handwritten script "Ideas flow better spoken." (Caveat-style, navy), and below it a legend of three colored dots — teal "Fast" · violet "Private" · violet "Always with you". Bottom-left footer: logo mark + "Say It" wordmark + thin divider + gray caption "A voice-to-text app for your everyday work." Bottom-right: handwritten script "Think it. Say it. Done."

**Row 1 — onboarding/app flow (screens 1–5), left→right with arrows between:**
- **1. Splash / Loading:** light-lilac window card, three pastel traffic-light dots top-left. Centered gradient blob mark. Gray status text "Starting up…". Thin violet progress bar, ~40% filled.
- **2. Welcome / Onboarding:** window card, three dots. Centered navy heading "Welcome to Say It". Flat cartoon illustration of a diverse group of ~12 people. Below: "Turn your voice into text." (navy) + "Faster. Easier. Everywhere." (gray). Gradient pill CTA "Let's get started" with a circular arrow icon on its right (violet→pink). Three pagination dots below (first active).
- **3. Permissions:** window card, three dots. Navy heading "Allow Microphone Access". Gray subtitle "Say It needs access to your microphone to listen and transcribe." Large violet microphone icon inside a glass circular orb. Glass/gradient pill CTA "Allow microphone". Gray secondary link "Maybe later" below.
- **4. Ready:** window card, three dots. Navy heading "You're all set!". Large white check inside a luminous blue/violet gradient circular orb. Gray centered text "Say It is ready to transcribe. Use Ctrl + Win and start speaking." White outlined/glass pill button "Open app". Three pagination dots below (first active).
- **5. Main App (Home):** full desktop window — three dots top-left AND top-right window controls (minimize, maximize, close). Left compact glass sidebar: logo mark at top, nav items Home (house icon, ACTIVE = tinted pill), History (clock icon), Settings (gear icon). Main area centered: navy heading "Ready when you are", large violet microphone IconOrb, navy semibold "Press Ctrl + Win and speak", smaller gray "Your speech will be transcribed and pasted at your cursor." Bottom status bar: green dot + "Ready" (left); violet "Auto paste" toggle (ON) + globe icon "English" dropdown (right).

**Row 2 — Mini Bar states (screens 6–10):** each labeled by a violet numbered circle badge + title + gray subtitle; each mini bar is a floating glass white pill (fully rounded) with the logo mark on the left; a state caption sits below each pill. Arrows connect 6→7→8→9. Screen 10 is enclosed in a dashed rounded-rectangle to signal the loop back to idle.
- **6. Idle** — "Sits quietly on your screen": logo mark + a quiet dotted-line indicator. Caption "Idle".
- **7. Listening** — "Shows live audio while you speak": logo mark + animated blue/violet vertical waveform bars + a stop button (square in dark circle) at right. Caption "Listening…".
- **8. Processing** — "Transcribing your speech": logo mark + dotted indicator + a circular dotted spinner at right. Caption "Transcribing…".
- **9. Pasted** — "Text has been pasted": logo mark + a check mark in a circle at right. Caption "Pasted!".
- **10. Back to Idle** — "Returns to idle state": identical geometry to 6 (logo mark + dotted indicator). Caption "Ready for next input". (Dashed border = loops to state 6.)

**Row 3 — full desktop windows (screens 11–14):** each is a full window with sidebar (logo, Home, History, Settings; active item is a tinted pill) and window controls top-right.
- **11. History** — "View and search transcripts": heading "History", SearchField with search icon "Search transcripts…", list of transcript cards (colored doc icon + title + right-aligned timestamp + gray preview line): "Meeting notes / 2 min ago / Here are the key points from today's…"; "Project idea / 1 hour ago / We should consider building a mini…"; "Quick thought / 3 hours ago / Just exploring some concepts for the…"; "Todo list / 5 hours ago / Buy groceries, finish thesis draft…".
- **12. Settings – General** — "App preferences": heading "General". Rows: "Launch at login" (toggle ON), "Show mini bar" (toggle ON), "Auto paste" + subtext "Automatically paste transcriptions at your cursor." (toggle ON), "Hotkey" → "Ctrl + Win" key box + "Change" button, "Language" → "English (US)" select.
- **13. Settings – Audio** — "Microphone and audio options": heading "Audio". "Microphone" → "Auto-detect (Recommended)" select; "Input sensitivity" → green segmented level meter/slider (~70% knob); "Noise suppression" + subtext "Reduce background noise for cleaner transcriptions." (violet toggle ON); "Test microphone" → mic icon button + "Start test" button.
- **14. About** — "App info and updates": heading "About". Centered large logo mark + "Say It" wordmark + gray "Version 1.0.0". Link rows with leading icon + trailing chevron: "Check for updates" (refresh icon) ›, "Send feedback" (chat icon) ›, "Privacy policy" (shield/lock icon) ›.

## 1. The key finding

Do not try to assemble this screen by finding one component library that looks like the screenshot. The reference is a custom visual system: soft white/lilac surfaces, blurred pastel blobs, a custom gradient wordmark, small desktop-window chrome, thin blue-violet controls, compact sidebar navigation, and a custom listening-state mini bar. The fastest route to high visual fidelity is therefore: use libraries only for primitives, make the design tokens and custom components deterministic, and use the screenshot as the visual source of truth throughout implementation.

21st.dev is still useful, and its current MCP can search, preview, install and generate components inside an agent workflow. But it should supply primitives—not dictate the final visual language. The 21st documentation explicitly describes the agent problem as choosing real components rather than inventing them, while also noting that the catalogue does not make the design judgement for you.

## 2. Recommended stack for this exact UI

| Layer | Use | Resource | Role in Say It |
|---|---|---|---|
| Base primitives | shadcn/ui | ui.shadcn.com | Button, Sidebar, Select, Switch, Progress, Input, Tooltip, Dialog |
| Component discovery | 21st.dev + 21st MCP | 21st.dev | Find glass buttons, sidebars, progress, selects, macOS patterns |
| Icons | Lucide React | lucide.dev | Mic, Home, History, Settings, Search, Check, Globe, Lock, Volume |
| Animation | Motion for React | motion.dev | Micro-interactions, state transitions, page transitions, mini-bar states |
| Soft background | Custom CSS/SVG first | CSS + SVG | The pastel blobs should be custom deterministic shapes |
| Optional effects | React Bits / Aceternity | reactbits.dev / ui.aceternity.com | Only if a subtle effect is actually needed |
| Fonts | Inter/Manrope + Caveat | Google Fonts / font sources | UI text + handwritten annotation |
| Design source | Figma MCP | developers.figma.com | Best option if the flattened board can be rebuilt as an editable Figma source |

## 3. The exact resources worth using

- **21st MCP for Claude Code** — https://docs.21st.dev/mcp — Connect the catalogue to Claude Code so the agent can search components, inspect real code and install rather than inventing generic UI.
- **21st: component catalogue** — https://21st.dev/ — Primary discovery source. Search specifically for glass button, sidebar, progress bar, select, switch, macOS menu bar, and listen/audio UI.
- **21st: Liquid Glass / Glassmorphism** — https://21st.dev/community/components/explore/liquid-glass-components — Useful for the translucent, softly bordered controls. Use as inspiration/primitives; adapt the final styling to the reference.
- **21st: Liquid Glass Buttons** — https://21st.dev/community/components/explore/liquid-glass-button — Direct source for the rounded translucent CTA/button treatment.
- **21st: Modern Sidebars** — https://21st.dev/community/components/explore/modern-sidebar — Useful for the Home/History/Settings sidebar pattern.
- **21st: macOS Components** — https://21st.dev/community/components/explore/macos-components — Especially relevant because the reference uses desktop-app/window chrome and macOS-like visual conventions.
- **21st: Progress components** — https://21st.dev/community/components/explore/progress-bar-react-js — Useful for the splash/loading progress bar and circular processing state.
- **21st: Select components** — https://21st.dev/community/components/s/select — Useful for Microphone and Language dropdowns in Settings.
- **21st: Toggle/Switch components** — https://21st.dev/community/components/s/toggle-switch — Useful for Auto paste and Noise suppression toggles.
- **shadcn/ui component catalogue** — https://ui.shadcn.com/docs/components — Use as the stable primitive layer. Includes Sidebar, Button, Input, Progress, Select, Switch, Tooltip, Dialog and related controls.
- **shadcn Sidebar** — https://ui.shadcn.com/docs/components/base/sidebar — Strong base for the Home/History/Settings navigation without importing a visually opinionated dashboard.
- **Tailwind sidebar layouts** — https://tailwindcss.com/plus/ui-blocks/application-ui/application-shells/sidebar — Useful reference for desktop sidebar spacing and layout behavior.
- **Lucide** — https://lucide.dev/ — Use one consistent icon family. SVG, scalable, customizable by size, stroke width and color.
- **Motion for React** — https://motion.dev/docs/react — Use for state transitions and micro-interactions. Avoid heavy animation that changes the visual language.
- **Motion layout animation** — https://motion.dev/docs/react-layout-animations — Useful for active sidebar indicators, state transitions and mini-bar morphing between idle/listening/processing/pasted states.
- **React Bits** — https://reactbits.dev/get-started/index — Large catalogue of animation/background components. Relevant categories: Soft Aurora, Blob Cursor, Shape Blur, Spotlight Card, Specular Button, etc.
- **React Bits creative tools** — https://www.reactbits.dev/tools — Its Shape Magic tool is especially useful to construct the soft organic blob shapes as SVG/CSS assets rather than hand-tuning them.
- **Aceternity UI** — https://ui.aceternity.com/explore — Secondary source for subtle background/effect ideas. Do not import its stronger 'hero' effects wholesale; the reference is intentionally quiet.
- **Claude Code CLI** — https://docs.anthropic.com/en/docs/claude-code/cli-usage — Official Claude Code command reference.
- **Claude Code prompt guidance** — https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables — Anthropic notes strong frontend models can fall into generic 'AI slop' without visual constraints and good guidance.
- **Figma MCP — remote server** — https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/ — If you recreate this board as editable Figma frames, Claude Code can consume structured design context instead of interpreting a flattened screenshot.
- **Figma MCP — tools/prompts** — https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/ — Provides get_design_context, metadata, asset download and Code Connect workflows.
- **Figma MCP — code-to-canvas** — https://developers.figma.com/docs/figma-mcp-server/code-to-canvas/ — Lets you capture the implemented UI back into Figma for visual comparison and iteration.
- **Screenshot-to-Code** — https://github.com/abi/screenshot-to-code — Useful as a separate image-to-code experiment (React + Tailwind, current multimodal models), but final production code should still be cleaned and integrated into your existing app.

## 4. What to build yourself instead of searching for

- **Say It logo/wordmark:** the reference mark is distinctive enough that a generic icon library will not reproduce it. Build the mark as an SVG component with three overlapping soft-gradient capsules/blobs and use the same SVG everywhere.
- **Pastel background blobs:** use a small set of absolute-positioned SVG/CSS blobs with fixed geometry, blur and opacity. Do not use a random animated gradient generator; deterministic shapes make screenshot matching much easier.
- **Listening mini bar:** custom component. It needs the exact state sequence Idle → Listening → Processing → Pasted → Idle, with waveform bars only during Listening and a spinner/check at the appropriate stages.
- **Desktop window chrome:** custom lightweight component with three small traffic-light dots and minimal top-right window controls. Do not import a full browser-window mockup library.
- **The large microphone/check circles:** custom radial/glass button shells around Lucide microphone/check icons.
- **The handwritten marketing notes:** use a handwriting font and fixed text positioning rather than an animated text component.

## 5. Reference design tokens to lock before Claude writes UI

| Token | Approximate reference | Usage |
|---|---|---|
| Canvas | #FAFAFC–#FFFFFF family | Very light warm/neutral white; the screenshot is not a pure flat #FFF surface. |
| Primary ink | #0B1640 / deep navy | Headings and high-priority text. |
| Secondary text | #52658F-ish | Descriptions, helper text and captions. |
| Accent blue-violet | #5A5BFF-ish | Primary CTA, active navigation, microphone/check accent. |
| Soft purple | #C8B8FF-ish | Background blob and glass glow family. |
| Soft pink | #F2C8EE-ish | Background blob family. |
| Soft cyan | #C8EAF4-ish | Background blob family. |
| Glass | rgba(255,255,255,0.65–0.85) | Cards/buttons over pastel background. |
| Border | rgba(100,120,200,0.12–0.22) | Thin, low-contrast borders. |
| Shadow | 0 8–30px rgba(70,80,160,0.10–0.16) | Soft diffuse shadow, never a hard dark drop shadow. |
| Radius | 12–20px | Cards/windows; mini bar is pill-shaped. |
| Stroke | 1.5–2px | Lucide icons; keep icon stroke consistent. |

These are starting measurements inferred from the supplied raster, not hidden source-file tokens. The important part is to put them into CSS variables and never scatter raw colors throughout components.

## 6. Screen-by-screen component map

| Screen | Suggested component tree | Visual requirement |
|---|---|---|
| 01 Splash / Loading | BrandMark + BrandWordmark + SoftBlobBackground + ProgressBar | Centered mark, short status text, thin violet progress track. |
| 02 Welcome / Onboarding | WindowFrame + IllustrationPanel + CTA + PaginationDots | Large illustration in a framed card, centered copy, glass/gradient CTA. |
| 03 Permissions | WindowFrame + PermissionCard + MicOrb + PrimaryButton | Large microphone icon, permission copy, main CTA, subtle secondary text. |
| 04 Ready | WindowFrame + SuccessOrb + CTA + PaginationDots | Check icon in luminous circular shell; concise readiness copy. |
| 05 Home | AppShell + Sidebar + HomeView + MicOrb + StatusBar | Most important production screen. Sidebar is compact; central mic action dominates. |
| 06 Mini Bar / Idle | FloatingMiniBar | Compact pill, logo left, small idle dots/wave indicator. |
| 07 Mini Bar / Listening | FloatingMiniBar + Waveform + StopButton | Same geometry as idle, waveform replaces idle indicator, stop control appears. |
| 08 Mini Bar / Processing | FloatingMiniBar + ProcessingSpinner | Keep width/position stable; only internal state changes. |
| 09 Mini Bar / Pasted | FloatingMiniBar + CheckIndicator | Check replaces processing; label becomes Pasted. |
| 10 Mini Bar / Back to Idle | FloatingMiniBar | Returns to exact Idle geometry; visually identical to 06. |
| 11 History | AppShell + SearchInput + TranscriptList + Timestamp + PreviewText | List cards are quiet and compact; active nav remains consistent. |
| 12 Settings / General | AppShell + SettingRows + Switch + HotkeyField + Select | Use a clean two-column label/control rhythm. |
| 13 Settings / Audio | AppShell + Select + Meter + Switch + TestButton | Audio meter and controls should feel like the reference, not a generic dashboard. |
| 14 About | AppShell + BrandMark + Version + LinkRows | Minimal, centered brand block with quiet utility rows. |

## 7. The exact workflow I recommend with Claude Code

1. Freeze the existing functionality first. Tell Claude: do not rewrite business logic, IPC, hotkeys, transcription, persistence, audio capture, history storage or settings behavior. The job is visual reconstruction plus wiring.
2. Create a UI-only inventory. Ask Claude to inspect the repository and produce a list of existing functionality and the components/routes/files that already own it. Do not let it modify anything in this step.
3. Create a design system file before screens. Put colors, radii, shadows, typography, spacing, icon sizes, window chrome, glass recipe and background blob positions in one place.
4. Build the reusable primitives first: WindowFrame, SoftBlobBackground, SayItMark, SayItWordmark, GlassButton, IconOrb, SidebarItem, MiniBar, StatusPill, SettingRow.
5. Implement one screen at a time in this order: Home → Mini Bar states → History → Settings General → Settings Audio → About → onboarding sequence. This makes the core shell stable before the lower-priority screens.
6. Use 21st MCP for component discovery, not as the visual source of truth. Search for primitives and copy their code only where it saves time.
7. Run the application after every screen. Capture screenshots at the same viewport size as the reference and compare side-by-side.
8. Use a correction loop with measurable instructions: position, width, height, radius, opacity, font size, line height, gap, shadow, icon size. Avoid vague instructions like 'make it prettier'.
9. Only after pixel-level alignment, wire the final UI to the existing functions and run the existing test suite. Then perform a functional regression pass.

## 8. Master prompt for Claude Code

> You are implementing the UI of an existing desktop voice-to-text application named "Say It".

**SOURCE OF TRUTH**
- The supplied reference image is the visual source of truth.
- Do not redesign it.
- Do not substitute a generic SaaS dashboard aesthetic.
- Do not invent alternate layouts.
- Match geometry, spacing, hierarchy, color, opacity, radius, shadows, icon stroke, typography and state transitions as closely as the reference permits.
- Treat the reference as a specification, not inspiration.

**FUNCTIONALITY SAFETY**
- The existing repository already contains working functionality.
- First inspect the codebase and identify all existing business logic, IPC calls, hotkeys, audio capture, transcription, clipboard/autopaste, history, settings and persistence.
- Do NOT rewrite or replace working functionality merely to make the UI easier to build.
- Keep the existing functionality intact and replace only the presentation layer and the minimum wiring required to connect the new UI.
- Before editing, create a screen/functionality inventory.

**DESIGN SYSTEM** — Create CSS variables/tokens for: background whites; deep navy text; muted blue-gray text; violet/indigo primary; pastel purple/pink/cyan/green blobs; glass background; glass border; soft shadow; corner radii; typography scale; spacing scale; icon sizes. Do not scatter arbitrary hex values throughout the code.

**VISUAL LANGUAGE**
- Soft white desktop-app canvas.
- Very subtle pastel organic blobs around edges/corners.
- Premium light glassmorphism, not heavy frosted glass.
- Thin borders.
- Diffuse blue-violet shadows.
- Deep navy typography.
- Violet/indigo accents.
- Rounded controls.
- Compact, restrained Lucide-style outline icons.
- Handwritten accent copy uses a handwriting font.
- No neon, no excessive gradients, no black dashboard panels, no generic Tailwind/shadcn look.

**CUSTOM ASSETS** — Build the Say It logo as a reusable SVG component: three overlapping rounded organic vertical forms; soft blue/violet/pink gradient; slight translucency; same mark reused in onboarding, app shell, mini bar and About. Do not replace it with a random microphone/logo icon.

**CORE COMPONENTS** — Build these reusable components before individual screens: 1. SoftBlobBackground 2. SayItMark 3. SayItWordmark 4. WindowFrame 5. GlassButton 6. IconOrb 7. SidebarItem 8. StatusPill 9. MiniBar 10. SettingRow 11. SearchField 12. PaginationDots

**MINI BAR STATES** — The mini bar is a single stable component with four visual states: idle, listening, processing, pasted. After pasted it returns to idle. Keep the outer pill geometry and position stable.
- Idle: Say It mark + small dotted/quiet indicator.
- Listening: Say It mark + animated blue waveform + stop control.
- Processing: Say It mark + restrained spinner.
- Pasted: Say It mark + check indicator.
Do not create four unrelated components.

**SCREEN ORDER** — Implement: 1 Splash / Loading; 2 Welcome / Onboarding; 3 Permissions; 4 Ready; 5 Home; 6 Mini Bar / Idle; 7 Mini Bar / Listening; 8 Mini Bar / Processing; 9 Mini Bar / Pasted; 10 Mini Bar / Back to Idle; 11 History; 12 Settings / General; 13 Settings / Audio; 14 About.

**DESIGN VALIDATION** — After each screen: run the app; capture at the target viewport; compare against the reference; correct the largest visual mismatch first; never compensate for one screen by breaking another; keep shared tokens centralized.

**DO NOT:** rewrite existing business logic; add a new state-management library unless absolutely required; replace working audio/transcription code; add unnecessary animation libraries; use random stock illustrations; use random generated blobs; use excessive glass effects; use generic dashboard cards; change copy unless the reference requires it; change keyboard shortcuts; make the mini bar resize between states.

**DELIVERABLE** — The final result must feel like the exact Say It design shown in the supplied reference, while preserving the existing application's functionality.

## 9. Visual QA checklist for every screen

- Viewport: render at the same dimensions/aspect ratio as the reference capture before judging alignment.
- Outer geometry: compare left/right/top/bottom bounds before adjusting internal components.
- Typography: compare font family, weight, size, line-height and letter spacing separately.
- Spacing: measure gaps between heading → description → control, not just overall centering.
- Glass: compare opacity and border contrast; the reference uses subtle glass, not obvious frosted panels.
- Background blobs: compare their centers, scale, blur and opacity; these are part of the composition.
- Iconography: use one icon family and consistent stroke width.
- State continuity: idle/listening/processing/pasted must share the same shell geometry.
- Active navigation: active Home/History/Settings item has a quiet tinted pill, not a loud filled button.
- Window chrome: keep the three small colored dots and the top-right controls understated.
- Responsive behavior: for the desktop app, preserve the reference at the intended minimum window size rather than turning it into a mobile dashboard.
- Regression: after visual changes, verify the hotkey, transcription, paste, history and settings functionality still work.

## 10. Practical resource-selection rules

- Use shadcn for boring infrastructure. It is composable and themeable; it should disappear visually after your theme is applied.
- Use 21st for discovery. The current 21st MCP can search, preview and install components in Claude Code, which is valuable for avoiding invented UI.
- Use Lucide for icons. Do not mix five icon packs.
- Use Motion only where the screenshot implies movement: state transitions, active indicators, subtle entrance/exit and mini-bar changes.
- Use React Bits/Aceternity sparingly. Their libraries contain much stronger visual effects than this reference; importing them wholesale will push the product away from the target.
- Use Figma MCP if you can turn the flattened reference into editable Figma frames. Structured Figma data is much more precise than asking Claude to infer every token from one raster.
- Use screenshot-to-code only as a measurement/starting-point tool, not as the final architecture. Its output must be refactored into your existing app and design-token system.

## 11. Bottom line

For this particular reference, the highest-fidelity setup is not "21st.dev generates the whole app." It is: screenshot/Figma source of truth → explicit design tokens → small custom component system → 21st/shadcn primitives → Lucide icons → Motion for state transitions → screenshot comparison loop.

The single most important change to your Claude Code workflow is to stop asking for the UI screen-by-screen as an open-ended design task. Give the model a frozen visual specification, reusable primitives, exact state definitions, and a strict 'do not touch functionality' boundary. That turns the model from a designer into an implementation agent.

## 12. Resource URLs at a glance

- 21st MCP for Claude Code: https://docs.21st.dev/mcp
- 21st: component catalogue: https://21st.dev/
- 21st: Liquid Glass / Glassmorphism: https://21st.dev/community/components/explore/liquid-glass-components
- 21st: Liquid Glass Buttons: https://21st.dev/community/components/explore/liquid-glass-button
- 21st: Modern Sidebars: https://21st.dev/community/components/explore/modern-sidebar
- 21st: macOS Components: https://21st.dev/community/components/explore/macos-components
- 21st: Progress components: https://21st.dev/community/components/explore/progress-bar-react-js
- 21st: Select components: https://21st.dev/community/components/s/select
- 21st: Toggle/Switch components: https://21st.dev/community/components/s/toggle-switch
- shadcn/ui component catalogue: https://ui.shadcn.com/docs/components
- shadcn Sidebar: https://ui.shadcn.com/docs/components/base/sidebar
- Tailwind sidebar layouts: https://tailwindcss.com/plus/ui-blocks/application-ui/application-shells/sidebar
- Lucide: https://lucide.dev/
- Motion for React: https://motion.dev/docs/react
- Motion layout animation: https://motion.dev/docs/react-layout-animations
- React Bits: https://reactbits.dev/get-started/index
- React Bits creative tools: https://www.reactbits.dev/tools
- Aceternity UI: https://ui.aceternity.com/explore
- Claude Code CLI: https://docs.anthropic.com/en/docs/claude-code/cli-usage
- Claude Code prompt guidance: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables
- Figma MCP — remote server: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/
- Figma MCP — tools/prompts: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/
- Figma MCP — code-to-canvas: https://developers.figma.com/docs/figma-mcp-server/code-to-canvas/
- Screenshot-to-Code: https://github.com/abi/screenshot-to-code

*Prepared from the supplied Say It reference image and current web research (September 2026).*
