// Sound recipes by Otohiroi (MIT). Synthesised with Web Audio: no audio files, nothing to license.
let A = null;
let OUT = null;
let white = null;
let brown = null;
const rnd = (a, b) => a + Math.random() * (b - a);

function tn(f, f2, at, len, type = "sine", vol = 0.12, out = OUT) {
  const s = A.currentTime + at, o = A.createOscillator(), g = A.createGain();
  o.type = type;
  o.frequency.setValueAtTime(f, s);
  o.frequency.exponentialRampToValueAtTime(f2, s + len);
  g.gain.setValueAtTime(vol, s);
  g.gain.exponentialRampToValueAtTime(0.001, s + len);
  o.connect(g).connect(out);
  o.start(s);
  o.stop(s + len);
}

function makeNoise() {
  if (white && white.sampleRate === A.sampleRate) return;
  const n = A.sampleRate * 3;
  white = A.createBuffer(1, n, A.sampleRate);
  brown = A.createBuffer(1, n, A.sampleRate);
  const w = white.getChannelData(0), b = brown.getChannelData(0);
  let last = 0;
  for (let i = 0; i < n; i++) {
    w[i] = Math.random() * 2 - 1;
    last = (last + 0.02 * w[i]) / 1.02;
    b[i] = last * 3.5;
  }
}

// Filtered noise. pts is [[seconds, level], ...] for a shaped envelope; otherwise it decays from vol.
function nz(at, len, { type = "bandpass", f = 2000, f2, q = 1, vol = 0.2, pts, deep, out = OUT } = {}) {
  makeNoise();
  const s = A.currentTime + at, src = A.createBufferSource(), fl = A.createBiquadFilter(), g = A.createGain();
  src.buffer = deep ? brown : white;
  fl.type = type;
  fl.frequency.setValueAtTime(f, s);
  if (f2) fl.frequency.exponentialRampToValueAtTime(f2, s + len);
  fl.Q.value = q;
  if (pts) {
    g.gain.setValueAtTime(pts[0][1], s);
    for (const [t, v] of pts.slice(1)) g.gain.linearRampToValueAtTime(v, s + t);
  } else {
    g.gain.setValueAtTime(vol, s);
    g.gain.exponentialRampToValueAtTime(0.001, s + len);
  }
  src.connect(fl).connect(g).connect(out);
  src.start(s, Math.random());
  src.stop(s + len + 0.01);
}

function panned(from, to, len) {
  const p = A.createStereoPanner(), t = A.currentTime;
  p.pan.setValueAtTime(from, t);
  p.pan.linearRampToValueAtTime(to, t + len);
  p.connect(OUT);
  return p;
}

function shake(at, f, vol, len = 0.26) {
  [1, 1.51, 2.27, 3.02].forEach((p, i) => tn(f * p, f * p, at, len / (1 + i * 0.35), "sine", vol / (1 + i * 0.6)));
}

function brass(f, at, len, vol, top = 2600) {
  const s = A.currentTime + at, fl = A.createBiquadFilter(), g = A.createGain();
  fl.type = "lowpass";
  fl.Q.value = 1;
  fl.frequency.setValueAtTime(450, s);
  fl.frequency.exponentialRampToValueAtTime(top, s + 0.06);
  fl.frequency.exponentialRampToValueAtTime(top * 0.5, s + len);
  g.gain.setValueAtTime(0.0001, s);
  g.gain.exponentialRampToValueAtTime(vol, s + 0.02);
  g.gain.setValueAtTime(vol * 0.85, s + len * 0.75);
  g.gain.exponentialRampToValueAtTime(0.001, s + len);
  fl.connect(g).connect(OUT);
  const lfo = A.createOscillator(), depth = A.createGain();
  lfo.frequency.value = 5.5;
  depth.gain.setValueAtTime(0, s);
  depth.gain.linearRampToValueAtTime(f * 0.006, s + 0.18);
  lfo.connect(depth);
  lfo.start(s);
  lfo.stop(s + len);
  for (const c of [-7, 0, 7]) {
    const o = A.createOscillator();
    o.type = "sawtooth";
    o.frequency.value = f;
    o.detune.value = c;
    depth.connect(o.frequency);
    o.connect(fl);
    o.start(s);
    o.stop(s + len);
  }
}

function chirp(at, f, len, vol, pan = 0) {
  const s = A.currentTime + at, out = A.createStereoPanner();
  out.pan.value = pan;
  out.connect(OUT);
  [[1, 1], [2, 0.14]].forEach(([m, v]) => {
    const o = A.createOscillator(), g = A.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(f * 0.82 * m, s);
    o.frequency.exponentialRampToValueAtTime(f * 1.22 * m, s + len * 0.4);
    o.frequency.exponentialRampToValueAtTime(f * 0.9 * m, s + len);
    g.gain.setValueAtTime(0.0001, s);
    g.gain.exponentialRampToValueAtTime(vol * v, s + 0.008);
    g.gain.setValueAtTime(vol * v, s + len * 0.6);
    g.gain.exponentialRampToValueAtTime(0.001, s + len);
    o.connect(g).connect(out);
    o.start(s);
    o.stop(s + len);
  });
}

function car(p, len, peak, low, voices, wind = 0.9) {
  const near = p.near ?? 1, out = panned(p.fromPan ?? -0.8, p.toPan ?? 0.8, len), s = A.currentTime;
  const fl = A.createBiquadFilter(), g = A.createGain();
  fl.type = "lowpass";
  fl.frequency.value = 720;
  g.gain.setValueAtTime(0.001, s);
  g.gain.exponentialRampToValueAtTime(Math.max(0.002, 0.16 * near), s + len * peak);
  g.gain.exponentialRampToValueAtTime(0.001, s + len);
  fl.connect(g).connect(out);
  for (const c of voices) {
    const o = A.createOscillator();
    o.type = "sawtooth";
    o.detune.value = c;
    o.frequency.setValueAtTime(low, s);
    o.frequency.linearRampToValueAtTime(low * 1.08, s + len * peak);
    o.frequency.exponentialRampToValueAtTime(low * 0.7, s + len * (peak + 0.14));
    o.connect(fl);
    o.start(s);
    o.stop(s + len);
  }
  nz(0, len, { f: 520, f2: 1250, q: 0.6, out, pts: [[0, 0], [len * peak, wind * near], [len * (peak + 0.2), 0.14 * near], [len, 0]] });
}

function shaky(len, floor, ceil) {
  const pts = [[0, 0]];
  for (let t = 0.06; t < len - 0.1; t += 0.05) pts.push([t, rnd(floor, ceil)]);
  pts.push([len, 0]);
  return pts;
}

function moan(top, end, len, vol, detunes) {
  const s = A.currentTime, mix = A.createGain(), delay = A.createDelay(1), fb = A.createGain();
  delay.delayTime.value = 0.26;
  fb.gain.value = 0.34;
  mix.connect(OUT);
  mix.connect(delay);
  delay.connect(fb).connect(delay);
  delay.connect(OUT);
  for (const d of detunes) {
    const o = A.createOscillator(), g = A.createGain(), lfo = A.createOscillator(), depth = A.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(top + d, s);
    o.frequency.exponentialRampToValueAtTime(end + d, s + len);
    lfo.frequency.value = rnd(3.6, 5);
    depth.gain.value = top * 0.05;
    lfo.connect(depth).connect(o.frequency);
    g.gain.setValueAtTime(0.001, s);
    g.gain.exponentialRampToValueAtTime(vol, s + len * 0.25);
    g.gain.exponentialRampToValueAtTime(0.001, s + len);
    o.connect(g).connect(mix);
    o.start(s);
    lfo.start(s);
    o.stop(s + len);
    lfo.stop(s + len);
  }
}

const SCALE = [1046.5, 1318.51, 1567.98];
const NOTES = [523.25, 587.33, 659.25, 783.99, 880, 1046.5, 1174.66, 1318.51, 1567.98];
const up = (p) => 1 + (p.index ?? 0) * 0.06;
const v3 = () => rnd(0.97, 1.03);

// Each variant is [Japanese description, level, play].
const FAMILIES = {
  ui_tap: {
    A: ["泡のポン", 0.35, () => { const v = v3(); tn(480 * v, 1150 * v, 0, 0.03, "sine", 0.34); nz(0, 0.006, { f: 2600, q: 2, vol: 0.9 }); }],
    B: ["カチッ。押す音と戻る音", 0.8, () => { nz(0, 0.007, { f: 3400 * v3(), q: 4, vol: 2.2 }); tn(1900, 1500, 0, 0.012, "triangle", 0.07); nz(0.075, 0.006, { f: 2300 * v3(), q: 4, vol: 1.4 }); }],
    C: ["コトッ。小さな木の玉", 0.44, () => { const v = v3(); tn(880 * v, 760 * v, 0, 0.035, "triangle", 0.26); tn(1370 * v, 1290 * v, 0, 0.02, "sine", 0.1); nz(0, 0.012, { type: "lowpass", f: 1800, q: 0.7, vol: 0.5 }); }],
  },
  rumble: {
    A: ["水の中の雷。細かく揺れ続ける", 0.42, () => nz(0, 1.5, { type: "lowpass", f: 130, deep: true, pts: shaky(1.5, 0.5, 1) })],
    B: ["短くゴゴッ", 0.42, () => { nz(0, 0.75, { type: "lowpass", f: 240, deep: true, vol: 0.9 }); tn(58, 38, 0, 0.7, "sine", 0.32); }],
    C: ["岩が転がる", 0.58, () => { nz(0, 1.1, { type: "lowpass", f: 150, deep: true, pts: shaky(1.1, 0.4, 0.8) }); for (let k = 0; k < 12; k++) nz(rnd(0, 1), 0.04, { f: rnd(260, 620), q: 3, vol: 0.5 }); }],
  },
  water_drop: {
    A: ["ちゃぽん。水音としぶき", 0.78, (p) => { const u = up(p); tn(330 * u, 980 * u, 0, 0.075, "sine", 0.3); nz(0.01, 0.035, { f: 1900, vol: 0.6 }); nz(0.03, 0.2, { type: "highpass", f: 2600, vol: 0.06 }); }],
    B: ["ばしゃ。助走、しぶき、水滴", 0.86, (p) => { const u = up(p); nz(0, 0.075, { f: 900, pts: [[0, 0], [0.07, 0.16], [0.075, 0]] }); nz(0.07, 0.13, { f: 1400, q: 0.7, vol: 0.8 }); tn(260 * u, 760 * u, 0.08, 0.08, "sine", 0.24); for (let k = 0; k < 5; k++) { const f = rnd(1200, 2400); tn(f, f * 1.35, rnd(0.14, 0.55), 0.035, "sine", 0.06); } }],
    C: ["ぽとん。泡がひとつ", 0.71, (p) => { const u = up(p); tn(300 * u, 760 * u, 0, 0.1, "sine", 0.3); tn(620 * u, 1240 * u, 0.09, 0.06, "sine", 0.13); }],
  },
  reward_star: {
    A: ["鈴ひとふり", 0.41, (p) => { const u = 1 + (p.index ?? 0) * 0.08; for (let k = 0; k < 7; k++) shake(rnd(0, 0.07), rnd(2900, 4100) * u, 0.07); nz(0, 0.35, { type: "highpass", f: 6500, vol: 0.14 }); }],
    B: ["鈴と音階", 0.44, (p) => { const f = SCALE[(p.index ?? 0) % 3]; tn(f, f, 0, 0.6, "sine", 0.2); tn(f * 2.76, f * 2.76, 0, 0.25, "sine", 0.05); for (let k = 0; k < 4; k++) shake(rnd(0, 0.05), rnd(3000, 4000), 0.04); }],
    C: ["ガラスのキラッ", 0.62, (p) => { const f = [2093, 2637, 3136][(p.index ?? 0) % 3]; [[1, 0.16], [2.32, 0.07], [4.25, 0.03], [6.63, 0.012]].forEach(([m, v], k) => tn(f * m, f * m, k * 0.004, 0.8 / (1 + k * 0.5), "sine", v)); }],
  },
  jingle_win: {
    A: ["タダーン。短い音と伸ばす和音", 0.37, () => { brass(523.25, 0, 0.11, 0.09); for (const f of [261.63, 329.63, 392, 523.25]) brass(f, 0.14, 0.95, 0.07); }],
    B: ["上がっていく金管の旋律", 0.51, () => { [[523.25, 0], [659.25, 0.12], [783.99, 0.24], [1046.5, 0.38], [783.99, 0.56], [1046.5, 0.68]].forEach(([f, a]) => { const l = a === 0.68 ? 1 : 0.17; brass(f, a, l, 0.1); brass(f / 2, a, l, 0.05); }); }],
    C: ["おもちゃのラッパ", 0.49, () => { brass(783.99, 0, 0.09, 0.1, 3500); brass(1046.5, 0.11, 0.45, 0.11, 3500); brass(523.25, 0.11, 0.45, 0.05, 3000); }],
  },
  jingle_fail: {
    A: ["しょんぼりトロンボーン", 0.42, () => { [[392, 0], [370, 0.2], [349.23, 0.4]].forEach(([f, a]) => brass(f, a, 0.18, 0.1, 1500)); brass(329.63, 0.6, 0.6, 0.1, 1200); }],
    B: ["ひゅーんと落ちる", 0.5, () => { tn(700, 130, 0, 0.5, "triangle", 0.22); nz(0, 0.5, { f: 1200, f2: 220, q: 2, vol: 0.25 }); }],
    C: ["ぼてっ。短く転ぶ", 0.55, () => { tn(240, 70, 0, 0.16, "sine", 0.4); nz(0, 0.08, { type: "lowpass", f: 700, vol: 0.5 }); tn(110, 60, 0.18, 0.12, "sine", 0.25); }],
  },
  chime_note: {
    A: ["鉄琴のひと粒", 0.6, (p) => { const f = NOTES[Math.max(0, (p.index ?? 1) - 1) % NOTES.length]; tn(f, f, 0, 0.45, "sine", 0.2); tn(f * 3.9, f * 3.9, 0, 0.08, "sine", 0.05); }],
    B: ["木琴のコロン", 0.7, (p) => { const f = NOTES[Math.max(0, (p.index ?? 1) - 1) % NOTES.length]; tn(f, f, 0, 0.14, "triangle", 0.25); nz(0, 0.01, { f: f * 3, q: 2, vol: 0.4 }); }],
    C: ["オルゴール", 0.65, (p) => { const f = NOTES[Math.max(0, (p.index ?? 1) - 1) % NOTES.length] * 2; tn(f, f, 0, 0.7, "sine", 0.1); tn(f * 2.01, f * 2.01, 0, 0.3, "sine", 0.03); }],
  },
  car_pass: {
    A: ["風を切る音", 0.31, (p) => car(p, p.big ? 1.5 : 1.1, 0.4, 95, [], 1.2)],
    B: ["エンジンと音程の下がり", 0.4, (p) => car(p, p.big ? 1.5 : 1.1, 0.4, p.big ? 62 : 95, [-9, 9])],
    C: ["低くて長い大型車", 0.36, (p) => { car(p, 1.6, 0.42, 58, [-11, 0, 11]); for (let k = 0; k < 7; k++) nz(rnd(0.3, 1), 0.05, { f: rnd(300, 700), q: 3, vol: 0.25 * (p.near ?? 1) + 0.001 }); }],
  },
  chick_chirp: {
    A: ["ぴよぴよ。不規則な間で1羽", 0.87, () => { let t = 0; for (let k = 0; k < 4; k++) { chirp(t, rnd(3000, 3900), 0.085, 0.12); t += rnd(0.11, 0.16); } }],
    B: ["群れで重なって鳴く", 0.86, () => { for (let k = 0; k < 14; k++) chirp(rnd(0, 0.85), rnd(2600, 4200), rnd(0.05, 0.09), 0.06, rnd(-0.5, 0.5)); }],
    C: ["ピッピッ。やわらかい1羽", 0.8, () => { chirp(0, 2500, 0.12, 0.13); chirp(0.17, 2700, 0.12, 0.12); }],
  },
  chick_peep: {
    A: ["ピィ…。下がって消える1声", 0.8, () => { const s = rnd(3100, 3500); tn(s, s * 0.62, 0, 0.32, "sine", 0.12); tn(s * 2, s * 1.2, 0, 0.2, "sine", 0.015); }],
    B: ["ピッ！と驚く", 0.8, () => chirp(0, 3700, 0.09, 0.14)],
    C: ["小さく2回", 0.8, () => { chirp(0, 2800, 0.1, 0.1); chirp(0.22, 2400, 0.14, 0.08); }],
  },
  ghost: {
    A: ["ふたりで揺れる声", 0.75, () => moan(720, 360, 1.7, 0.09, [0, 9])],
    B: ["低いうなり", 0.8, () => { moan(330, 190, 1.9, 0.14, [0, 5]); nz(0, 1.8, { f: 700, q: 3, pts: [[0, 0], [0.5, 0.05], [1.8, 0]] }); }],
    C: ["かすれた息", 0.8, () => { nz(0, 1.5, { f: 1400, f2: 600, q: 5, pts: [[0, 0], [0.5, 0.3], [1.5, 0]] }); moan(560, 420, 1.4, 0.03, [0]); }],
  },
  foot_generic: {
    A: ["土の上の小さな足", 0.7, (p) => { const near = p.near ?? 1, out = panned(p.pan ?? 0, p.pan ?? 0, 0.1), f = rnd(180, 240); tn(f, f * 0.6, 0, 0.05, "sine", (p.run ? 0.26 : 0.18) * near, out); nz(0, 0.03, { type: "lowpass", f: 1500, vol: (p.run ? 0.34 : 0.22) * near + 0.001, out }); }],
    B: ["草をふむ", 0.7, (p) => { const near = p.near ?? 1, out = panned(p.pan ?? 0, p.pan ?? 0, 0.1); nz(0, 0.08, { type: "highpass", f: 2400 * v3(), vol: (p.run ? 0.14 : 0.1) * near + 0.001, out }); tn(150, 90, 0, 0.04, "sine", 0.12 * near + 0.001, out); }],
    C: ["ぺたぺた水かき", 0.7, (p) => { const near = p.near ?? 1, out = panned(p.pan ?? 0, p.pan ?? 0, 0.1); tn(420 * v3(), 240, 0, 0.035, "sine", (p.run ? 0.2 : 0.14) * near + 0.001, out); nz(0, 0.02, { f: 1200, vol: 0.25 * near + 0.001, out }); }],
  },
  reward_coin: {
    A: ["チャリン", 0.5, () => { shake(0, 2600, 0.14, 0.3); shake(0.07, 3400, 0.14, 0.4); }],
    B: ["コインを拾う軽い音", 0.5, () => { tn(1300, 1300, 0, 0.06, "sine", 0.18); tn(1950, 1950, 0.06, 0.28, "sine", 0.18); }],
  },
  pop_small: {
    A: ["ぽん", 0.6, () => tn(320 * v3(), 900, 0, 0.06, "sine", 0.32)],
    B: ["コルクのぽん", 0.6, () => { tn(600, 240, 0, 0.05, "triangle", 0.3); nz(0, 0.015, { f: 1800, q: 1, vol: 0.7 }); }],
  },
  swoosh: {
    A: ["シュッ", 0.6, () => nz(0, 0.22, { f: 800, f2: 3200, q: 1.2, pts: [[0, 0], [0.12, 0.8], [0.22, 0]] })],
    B: ["ヒュン。重い振り", 0.6, () => nz(0, 0.36, { f: 320, f2: 1300, q: 2, pts: [[0, 0], [0.22, 1.1], [0.36, 0]] })],
  },
  punch_hit: {
    A: ["ボコッ", 0.6, () => { tn(150, 55, 0, 0.13, "sine", 0.5); nz(0, 0.05, { type: "lowpass", f: 1500, vol: 0.8 }); }],
    B: ["バシッ", 0.55, () => { nz(0, 0.08, { f: 2200, q: 0.7, vol: 1 }); tn(240, 100, 0, 0.07, "triangle", 0.3); }],
  },
  explosion: {
    A: ["ドカン", 0.55, () => { nz(0, 1.1, { type: "lowpass", f: 1400, f2: 90, deep: true, vol: 1.6 }); nz(0, 0.25, { f: 1800, q: 0.5, vol: 0.5 }); tn(90, 32, 0, 0.6, "sine", 0.5); }],
    B: ["ボンッ。小さめ", 0.55, () => { nz(0, 0.4, { type: "lowpass", f: 1000, f2: 160, deep: true, vol: 1.4 }); tn(130, 45, 0, 0.3, "sine", 0.4); }],
  },
  jump: {
    A: ["ぽよん", 0.6, () => { const s = A.currentTime, o = A.createOscillator(), g = A.createGain(); o.frequency.setValueAtTime(190, s); o.frequency.exponentialRampToValueAtTime(620, s + 0.16); g.gain.setValueAtTime(0.28, s); g.gain.exponentialRampToValueAtTime(0.001, s + 0.2); o.connect(g).connect(OUT); o.start(s); o.stop(s + 0.2); }],
    B: ["軽い跳ね", 0.6, () => { nz(0, 0.05, { type: "lowpass", f: 900, vol: 0.5 }); tn(260, 480, 0, 0.09, "triangle", 0.22); }],
  },
  ui_error: {
    A: ["コンコン。やさしい否定", 0.6, () => { tn(320, 250, 0, 0.06, "triangle", 0.3); tn(250, 200, 0.12, 0.08, "triangle", 0.3); }],
    B: ["ぶぶっ", 0.55, () => { tn(150, 120, 0, 0.12, "sawtooth", 0.12); tn(140, 110, 0.15, 0.16, "sawtooth", 0.12); }],
  },
  magic_spell: {
    A: ["きらめきが立ち上がる", 0.5, () => { [0, 0.07, 0.14, 0.21, 0.28].forEach((a, i) => shake(a, 1800 + i * 500, 0.05, 0.5)); nz(0, 0.6, { type: "highpass", f: 5000, pts: [[0, 0], [0.4, 0.12], [0.6, 0]] }); }],
    B: ["やわらかい癒やし", 0.5, () => { [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tn(f, f, i * 0.09, 0.7, "sine", 0.1)); }],
  },
};

function context(given) {
  if (given) return given;
  if (!play.own) play.own = new AudioContext();
  if (play.own.state === "suspended") play.own.resume();
  return play.own;
}

export function play(family, variant, params, level, given) {
  A = context(given);
  const [, base, run] = FAMILIES[family][variant];
  const bus = A.createGain();
  bus.gain.value = base * level;
  bus.connect(A.destination);
  OUT = bus;
  run(params || {});
}

export function catalog() {
  return Object.fromEntries(Object.entries(FAMILIES).map(([id, set]) => [id, Object.fromEntries(Object.entries(set).map(([k, v]) => [k, v[0]]))]));
}
