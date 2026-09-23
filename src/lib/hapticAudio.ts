// Web Audio API tactile haptic acoustic synthesizer
// Emulates soothing mechanical switch & taptic engine auditory feedback.
// Zero external assets required — ultra low latency (<2ms).

let audioCtx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

/** 1. Activation: Gentle, soothing low-frequency mechanical bottom-out pulse (~75Hz -> 42Hz) */
export function playHapticActivation() {
  const ctx = getContext();
  if (!ctx) return;
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "sine";
  osc.frequency.setValueAtTime(80, now);
  osc.frequency.exponentialRampToValueAtTime(42, now + 0.06);

  gain.gain.setValueAtTime(0.001, now);
  gain.gain.linearRampToValueAtTime(0.35, now + 0.004);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(now);
  osc.stop(now + 0.075);
}

/** 2. Deactivation: Soft, tactile switch release tick (~110Hz -> 65Hz) */
export function playHapticDeactivation() {
  const ctx = getContext();
  if (!ctx) return;
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "sine";
  osc.frequency.setValueAtTime(115, now);
  osc.frequency.exponentialRampToValueAtTime(65, now + 0.05);

  gain.gain.setValueAtTime(0.001, now);
  gain.gain.linearRampToValueAtTime(0.28, now + 0.003);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.055);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(now);
  osc.stop(now + 0.06);
}

/** 3. Success / Paste: Harmonious warm sub-bass resolution chime (dual bloom) */
export function playHapticSuccess() {
  const ctx = getContext();
  if (!ctx) return;
  const now = ctx.currentTime;

  [
    { freq: 95, end: 50, delay: 0, vol: 0.32, dur: 0.12 },
    { freq: 142, end: 72, delay: 0.02, vol: 0.22, dur: 0.14 },
  ].forEach((tone) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    const start = now + tone.delay;
    osc.frequency.setValueAtTime(tone.freq, start);
    osc.frequency.exponentialRampToValueAtTime(tone.end, start + tone.dur);

    gain.gain.setValueAtTime(0.001, start);
    gain.gain.linearRampToValueAtTime(tone.vol, start + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.001, start + tone.dur);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(start);
    osc.stop(start + tone.dur + 0.01);
  });
}

/** 4. Failure: Distinct contrasting descending double-bump reject haptic cue */
export function playHapticFailure() {
  const ctx = getContext();
  if (!ctx) return;
  const now = ctx.currentTime;

  [
    { freq: 140, end: 58, delay: 0, vol: 0.35, dur: 0.07 },
    { freq: 108, end: 46, delay: 0.08, vol: 0.40, dur: 0.09 },
  ].forEach((pulse) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "triangle"; // Slightly richer/dissonant texture for failure
    const start = now + pulse.delay;
    osc.frequency.setValueAtTime(pulse.freq, start);
    osc.frequency.exponentialRampToValueAtTime(pulse.end, start + pulse.dur);

    gain.gain.setValueAtTime(0.001, start);
    gain.gain.linearRampToValueAtTime(pulse.vol, start + 0.004);
    gain.gain.exponentialRampToValueAtTime(0.001, start + pulse.dur);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(start);
    osc.stop(start + pulse.dur + 0.01);
  });
}
