import { useState, useEffect, useRef, useMemo } from "react";

/* ============================================================
   VoxCPM2-Khmer · Speech Studio
   A control-panel dashboard for the sumnim/VoxCPM2-Khmer model
   Modes: Speak · Voice Design · Clone · Model
   ============================================================ */

const T = {
  bg: "#14161C",
  bgDeep: "#0F1116",
  surface: "#1C1F27",
  surfaceHi: "#232735",
  line: "#2A2E38",
  gold: "#E3A83B",
  goldHi: "#F0BE5C",
  jade: "#57B99A",
  text: "#EDE8DC",
  muted: "#8B8FA0",
  mutedDeep: "#5C6070",
};

const KHMER_SAMPLES = [
  { label: "Greeting", km: "សួស្តី! សូមស្វាគមន៍មកកាន់ប្រព័ន្ធបំលែងអត្ថបទទៅជាសំឡេងភាសាខ្មែរ។" },
  { label: "News", km: "ថ្ងៃនេះ អាកាសធាតុនៅរាជធានីភ្នំពេញ មានភ្លៀងធ្លាក់ខ្លាំងនៅពេលរសៀល។" },
  { label: "Story", km: "កាលពីព្រេងនាយ មានព្រះរាជាមួយអង្គ គង់នៅក្នុងនគរដ៏រុងរឿងមួយ។" },
  { label: "Numbers", km: "តម្លៃសរុបគឺ មួយពាន់ប្រាំរយហុកសិបប្រាំ រៀល។" },
];

const LANGUAGES = [
  "Arabic","Burmese","Chinese","Danish","Dutch","English","Finnish","French","German","Greek",
  "Hebrew","Hindi","Indonesian","Italian","Japanese","Khmer","Korean","Lao","Malay","Norwegian",
  "Polish","Portuguese","Russian","Spanish","Swahili","Swedish","Tagalog","Thai","Turkish","Vietnamese",
];

const DESIGN_CHIPS = {
  Voice: ["A young woman", "A young man", "An elderly man", "An elderly woman", "A child"],
  Tone: ["gentle and sweet voice", "deep calm voice", "bright energetic voice", "warm storytelling voice"],
  Pace: ["slow pace", "natural pace", "slightly faster"],
  Emotion: ["cheerful tone", "serious tone", "soothing tone", "excited tone"],
};

const GEN_STEPS = ["Normalizing text", "TSLM context pass", "LocDiT diffusion sampling", "AudioVAE 48kHz decode"];

/* ---------- tiny UI atoms ---------- */

function Slider({ label, value, min, max, step, onChange, hint }) {
  return (
    <div className="ctl">
      <div className="ctl-head">
        <label>{label}</label>
        <span className="mono val">{value}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))} />
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

function Toggle({ label, on, onChange, hint }) {
  return (
    <button className={"toggle" + (on ? " on" : "")} onClick={() => onChange(!on)} aria-pressed={on}>
      <span className="knob-track"><span className="knob" /></span>
      <span className="toggle-body">
        <span className="toggle-label">{label}</span>
        {hint && <span className="hint">{hint}</span>}
      </span>
    </button>
  );
}

/* ---------- waveform signature ---------- */

function Waveform({ playing, seed, live, liveLevels }) {
  const ref = useRef(null);
  const raf = useRef(null);
  const levelsRef = useRef([]);
  useEffect(() => { levelsRef.current = liveLevels || []; }, [liveLevels]);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    let t = 0;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const draw = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const bars = Math.floor(w / 7);
      const levels = levelsRef.current;
      for (let i = 0; i < bars; i++) {
        const x = i * 7 + 3;
        let amp, color;
        if (live && levels.length) {
          const lv = levels[(i + Math.floor(t / 3)) % levels.length] || 0;
          amp = 0.08 + lv * 0.92;
          color = i % 9 === 0 ? T.gold : T.jade;
        } else {
          const ph = Math.sin(i * 0.55 + seed) * 0.5 + 0.5;
          const anim = playing ? (Math.sin(t * 0.11 + i * 0.5) * 0.5 + 0.5) : 0.18 + ph * 0.12;
          amp = playing ? (0.15 + 0.85 * ph * anim) : anim;
          color = playing ? (i % 9 === 0 ? T.jade : T.gold) : "rgba(227,168,59,0.28)";
        }
        const bh = Math.max(2, amp * h * 0.9);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(x, (h - bh) / 2, 3.4, bh, 2);
        ctx.fill();
      }
      t += 1;
      if ((playing || live) && !reduced) raf.current = requestAnimationFrame(draw);
    };
    draw();
    if ((playing || live) && !reduced) raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, seed, live]);
  return <canvas ref={ref} className="wave" aria-hidden="true" />;
}

/* ---------- reference-audio upload zone ---------- */

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function UploadZone({ refInfo, uploading, progress, error, onFile, onRemove }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  if (refInfo) {
    return (
      <div className="upload-done">
        <div className="upload-done-info">
          <span className="upload-name mono">{refInfo.filename}</span>
          <span className="upload-meta mono">{refInfo.duration_s.toFixed(1)}s</span>
        </div>
        <button className="upload-remove" onClick={onRemove} aria-label="Remove reference audio">Remove</button>
      </div>
    );
  }

  return (
    <div>
      <div
        className={"dropzone" + (dragOver ? " over" : "")}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault(); setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) onFile(f);
        }}
        role="button" tabIndex={0}
      >
        {uploading ? (
          <>
            <div className="upload-bar"><div className="upload-bar-fill" style={{ width: `${progress}%` }} /></div>
            <p className="hint">Uploading… {progress}%</p>
          </>
        ) : (
          <>
            <p className="dropzone-label">Drop a reference clip here, or click to browse</p>
            <p className="hint">WAV, MP3, FLAC, M4A, or OGG — up to 20 MB, 60s</p>
          </>
        )}
      </div>
      <input ref={inputRef} type="file" accept=".wav,.mp3,.flac,.m4a,.ogg" style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      {error && <div className="note err">{error}</div>}
    </div>
  );
}

/* ---------- pcm16 -> wav (client-side, for streamed playback download) ---------- */

function pcm16ToWavBlob(pcmBytes, sampleRate) {
  const header = new ArrayBuffer(44);
  const v = new DataView(header);
  const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i)); };
  writeStr(0, "RIFF"); v.setUint32(4, 36 + pcmBytes.length, true); writeStr(8, "WAVE");
  writeStr(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  writeStr(36, "data"); v.setUint32(40, pcmBytes.length, true);
  return new Blob([header, pcmBytes], { type: "audio/wav" });
}

/* ---------- python snippet builder ---------- */

function buildSnippet({ mode, text, designPrefix, cfg, steps, normalize, denoise, retry, refPath, promptText }) {
  const fullText = mode === "design" && designPrefix ? `(${designPrefix})${text}` : text;
  const esc = (s) => (s || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const lines = [
    "import soundfile as sf",
    "from voxcpm import VoxCPM",
    "",
    'model = VoxCPM.from_pretrained("sumnim/VoxCPM2-Khmer")',
    "",
    "wav = model.generate(",
    `    text="${esc(fullText)}",`,
  ];
  if (mode === "clone" || mode === "ultimate") lines.push(`    reference_wav_path="${esc(refPath) || "speaker.wav"}",`);
  if (mode === "ultimate") {
    lines.push(`    prompt_wav_path="${esc(refPath) || "speaker.wav"}",`);
    lines.push(`    prompt_text="${esc(promptText)}",`);
  }
  lines.push(
    `    cfg_value=${cfg},`,
    `    inference_timesteps=${steps},`,
    `    normalize=${normalize ? "True" : "False"},`,
    `    denoise=${denoise ? "True" : "False"},`,
    `    retry_badcase=${retry ? "True" : "False"},`,
    ")",
    "",
    'sf.write("output.wav", wav, model.tts_model.sample_rate)',
  );
  return lines.join("\n");
}

/* ---------- main ---------- */

export default function VoxCPMKhmerStudio() {
  const [tab, setTab] = useState("speak");
  const [text, setText] = useState(KHMER_SAMPLES[0].km);
  const [cfg, setCfg] = useState(2.0);
  const [steps, setSteps] = useState(10);
  const [normalize, setNormalize] = useState(true);
  const [denoise, setDenoise] = useState(true);
  const [retry, setRetry] = useState(true);
  const [designSel, setDesignSel] = useState({ Voice: "A young woman", Tone: "gentle and sweet voice", Pace: null, Emotion: null });
  const [refPath, setRefPath] = useState("");
  const [showAdvancedPath, setShowAdvancedPath] = useState(false);
  const [refInfo, setRefInfo] = useState(null); // { ref_id, duration_s, filename }
  const [refUploading, setRefUploading] = useState(false);
  const [refUploadProgress, setRefUploadProgress] = useState(0);
  const [refUploadError, setRefUploadError] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [promptText, setPromptText] = useState("");
  const [ultimate, setUltimate] = useState(false);
  const [endpoint, setEndpoint] = useState("/api/tts");
  const [genState, setGenState] = useState({ status: "idle", step: 0, error: null, position: null });
  const [audioUrl, setAudioUrl] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [seed, setSeed] = useState(1);
  const [streamMode, setStreamMode] = useState(false);
  const [liveStreaming, setLiveStreaming] = useState(false);
  const [liveLevels, setLiveLevels] = useState([]);
  const audioRef = useRef(null);
  const timers = useRef([]);
  const audioCtxRef = useRef(null);
  const nextStartTimeRef = useRef(0);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  useEffect(() => {
    fetch("/api/model-info").then((r) => (r.ok ? r.json() : null)).then(setModelInfo).catch(() => setModelInfo(null));
  }, []);

  const uploadRef = (file) => {
    setRefUploadError(null);
    setRefUploading(true);
    setRefUploadProgress(0);
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload-ref");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setRefUploadProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      setRefUploading(false);
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        setRefInfo(body);
      } else {
        setRefUploadError(body?.detail || `Upload failed (server replied ${xhr.status})`);
      }
    };
    xhr.onerror = () => { setRefUploading(false); setRefUploadError("Upload failed — network error."); };
    xhr.send(form);
  };

  const removeRef = () => { setRefInfo(null); setRefUploadError(null); };

  const designPrefix = useMemo(
    () => Object.values(designSel).filter(Boolean).join(", "),
    [designSel]
  );

  const mode = tab === "speak" ? "speak" : tab === "design" ? "design" : ultimate ? "ultimate" : "clone";
  const needsRef = mode === "clone" || mode === "ultimate";
  const hasRef = Boolean(refInfo) || (showAdvancedPath && refPath.trim());
  const snippetRefPath = refPath || refInfo?.filename || "";
  const streamSupported = /\/api\/tts$/.test(endpoint.trim());

  const snippet = useMemo(
    () => buildSnippet({ mode, text, designPrefix, cfg, steps, normalize, denoise, retry, refPath: snippetRefPath, promptText }),
    [mode, text, designPrefix, cfg, steps, normalize, denoise, retry, snippetRefPath, promptText]
  );

  const copySnippet = async () => {
    try { await navigator.clipboard.writeText(snippet); } catch {
      const ta = document.createElement("textarea");
      ta.value = snippet; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); document.body.removeChild(ta);
    }
    setCopied(true); setTimeout(() => setCopied(false), 1600);
  };

  const buildRequestBody = () => {
    const isCloneMode = mode === "clone" || mode === "ultimate";
    const usingRawPath = isCloneMode && showAdvancedPath && refPath.trim();
    return {
      text: mode === "design" && designPrefix ? `(${designPrefix})${text}` : text,
      cfg_value: cfg, inference_timesteps: steps,
      normalize, denoise, retry_badcase: retry,
      reference_wav_path: usingRawPath ? refPath.trim() : null,
      prompt_wav_path: mode === "ultimate" && usingRawPath ? refPath.trim() : null,
      reference_ref_id: isCloneMode && !usingRawPath ? refInfo?.ref_id || null : null,
      prompt_ref_id: mode === "ultimate" && !usingRawPath ? refInfo?.ref_id || null : null,
      prompt_text: mode === "ultimate" ? promptText || null : null,
    };
  };

  const errorDetail = async (res, fallback) => {
    try { return (await res.json()).detail || fallback; } catch { return fallback; }
  };

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const POLL_INTERVAL_MS = 1500;

  const generateBuffered = async () => {
    const url = endpoint.trim();
    const useQueue = streamSupported; // same /api/tts pattern — our own backend's job-queue endpoints
    setGenState({ status: "running", step: useQueue ? 0 : 1, error: null, position: null });
    try {
      if (!useQueue) {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildRequestBody()),
        });
        if (!res.ok) throw new Error(await errorDetail(res, `Server replied ${res.status}`));
        const blob = await res.blob();
        setAudioUrl(URL.createObjectURL(blob));
        setGenState({ status: "done", step: GEN_STEPS.length, error: null, position: null });
        return;
      }

      const submitRes = await fetch(`${url}?async=1`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildRequestBody()),
      });
      if (!submitRes.ok) throw new Error(await errorDetail(submitRes, `Server replied ${submitRes.status}`));
      const { job_id } = await submitRes.json();

      for (;;) {
        const statusRes = await fetch(`/api/jobs/${job_id}`);
        if (!statusRes.ok) throw new Error(await errorDetail(statusRes, `Job status check failed (${statusRes.status})`));
        const s = await statusRes.json();
        if (s.status === "queued") {
          setGenState({ status: "queued", step: 0, error: null, position: s.position });
        } else if (s.status === "running") {
          setGenState({ status: "running", step: 1, error: null, position: null });
        } else if (s.status === "done") {
          const resultRes = await fetch(`/api/jobs/${job_id}/result`);
          if (!resultRes.ok) throw new Error(await errorDetail(resultRes, `Couldn't fetch the result (${resultRes.status})`));
          const blob = await resultRes.blob();
          setAudioUrl(URL.createObjectURL(blob));
          setGenState({ status: "done", step: GEN_STEPS.length, error: null, position: null });
          return;
        } else {
          throw new Error(s.error || "Synthesis failed.");
        }
        await sleep(POLL_INTERVAL_MS);
      }
    } catch (e) {
      const msg = e instanceof TypeError
        ? `Couldn't reach the endpoint (${e.message}). Check the URL and that the server allows CORS from this origin.`
        : e.message;
      setGenState({ status: "error", step: 0, error: msg, position: null });
    }
  };

  const generateStreaming = async () => {
    setGenState({ status: "running", step: 1, error: null });
    setLiveStreaming(true);
    setLiveLevels([]);
    if (audioCtxRef.current) { audioCtxRef.current.close().catch(() => {}); }
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) {
      setLiveStreaming(false);
      setGenState({ status: "error", step: 0, error: "This browser doesn't support the Web Audio API needed for streaming — turn off Stream and try again." });
      return;
    }
    const ctx = new AudioCtx();
    audioCtxRef.current = ctx;
    nextStartTimeRef.current = ctx.currentTime + 0.1;
    const streamUrl = endpoint.trim().replace(/\/tts$/, "/tts-stream");
    const pcmParts = [];
    let leftover = new Uint8Array(0);
    try {
      const res = await fetch(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildRequestBody()),
      });
      if (!res.ok || !res.body) throw new Error(await errorDetail(res, `Server replied ${res.status}`));
      const sampleRate = parseInt(res.headers.get("X-Sample-Rate"), 10) || 48000;
      const reader = res.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        pcmParts.push(value);
        let bytes = value;
        if (leftover.length) {
          const merged = new Uint8Array(leftover.length + bytes.length);
          merged.set(leftover, 0); merged.set(bytes, leftover.length);
          bytes = merged;
        }
        if (bytes.length % 2 !== 0) {
          leftover = bytes.slice(bytes.length - 1);
          bytes = bytes.slice(0, bytes.length - 1);
        } else {
          leftover = new Uint8Array(0);
        }
        const samples = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.length / 2);
        const floatData = new Float32Array(samples.length);
        let peak = 0;
        for (let i = 0; i < samples.length; i++) {
          floatData[i] = samples[i] / 32768;
          peak = Math.max(peak, Math.abs(floatData[i]));
        }
        const buffer = ctx.createBuffer(1, floatData.length, sampleRate);
        buffer.copyToChannel(floatData, 0);
        const src = ctx.createBufferSource();
        src.buffer = buffer;
        src.connect(ctx.destination);
        const startAt = Math.max(nextStartTimeRef.current, ctx.currentTime);
        src.start(startAt);
        nextStartTimeRef.current = startAt + buffer.duration;
        setLiveLevels((levels) => [...levels.slice(-39), peak]);
      }
      const total = pcmParts.reduce((n, p) => n + p.length, 0);
      const merged = new Uint8Array(total);
      let offset = 0;
      for (const p of pcmParts) { merged.set(p, offset); offset += p.length; }
      setAudioUrl(URL.createObjectURL(pcm16ToWavBlob(merged, sampleRate)));
      setGenState({ status: "done", step: GEN_STEPS.length, error: null });
    } catch (e) {
      setGenState({ status: "error", step: 0, error: `Streaming failed: ${e.message}. Turn off Stream and try again for standard playback.` });
      setStreamMode(false);
    } finally {
      setLiveStreaming(false);
    }
  };

  const generate = async () => {
    setAudioUrl(null); setPlaying(false); setSeed(Math.random() * 10);
    timers.current.forEach(clearTimeout); timers.current = [];
    if (endpoint.trim()) {
      if (streamMode && streamSupported) await generateStreaming();
      else await generateBuffered();
      return;
    }
    // Demo mode: walk through the real pipeline stages, no audio produced
    setGenState({ status: "running", step: 0, error: null });
    GEN_STEPS.forEach((_, i) => {
      timers.current.push(setTimeout(() => {
        setGenState({ status: i === GEN_STEPS.length - 1 ? "demo-done" : "running", step: i + 1, error: null });
      }, 550 * (i + 1)));
    });
  };

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) { a.play(); setPlaying(true); } else { a.pause(); setPlaying(false); }
  };

  return (
    <div className="root">
      <style>{css}</style>

      {/* ---------- header ---------- */}
      <header className="head">
        <div className="head-left">
          <div className="glyph" aria-hidden="true">ស</div>
          <div>
            <div className="eyebrow">sumnim / VoxCPM2-Khmer</div>
            <h1>Speech Studio <span className="kh-title">សំឡេង</span></h1>
          </div>
        </div>
        <div className="badges">
          <span className="badge">2B params</span>
          <span className="badge">30 languages</span>
          <span className="badge gold">48 kHz out</span>
          <span className="badge">Apache-2.0</span>
        </div>
      </header>

      <Waveform playing={genState.status === "running" || playing} seed={seed} live={liveStreaming} liveLevels={liveLevels} />

      {/* ---------- tabs ---------- */}
      <nav className="tabs" role="tablist">
        {[
          ["speak", "Speak"],
          ["design", "Voice design"],
          ["clone", "Clone a voice"],
          ["model", "Model"],
        ].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id}
            className={"tab" + (tab === id ? " active" : "")}
            onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>

      {tab !== "model" ? (
        <main className="grid">
          {/* ---------- left column: input ---------- */}
          <section className="col">
            {tab === "design" && (
              <div className="card">
                <h2>Describe the voice</h2>
                <p className="hint">Pick traits — they become the parenthesised prefix VoxCPM2 reads as a voice description. No reference audio needed.</p>
                {Object.entries(DESIGN_CHIPS).map(([group, chips]) => (
                  <div className="chip-row" key={group}>
                    <span className="chip-group">{group}</span>
                    <div className="chips">
                      {chips.map((c) => (
                        <button key={c}
                          className={"chip" + (designSel[group] === c ? " sel" : "")}
                          onClick={() => setDesignSel((s) => ({ ...s, [group]: s[group] === c ? null : c }))}>
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                {designPrefix && <div className="prefix mono">({designPrefix})</div>}
              </div>
            )}

            {tab === "clone" && (
              <div className="card">
                <h2>Reference voice</h2>
                <UploadZone refInfo={refInfo} uploading={refUploading} progress={refUploadProgress}
                  error={refUploadError} onFile={uploadRef} onRemove={removeRef} />
                {modelInfo?.allow_raw_paths && (
                  <>
                    <button className="disclosure" onClick={() => setShowAdvancedPath((v) => !v)}>
                      {showAdvancedPath ? "▾" : "▸"} Advanced: server path
                    </button>
                    {showAdvancedPath && (
                      <>
                        <label className="field-label" htmlFor="ref">Reference audio path on the server</label>
                        <input id="ref" className="field mono" placeholder="/data/speaker.wav" value={refPath}
                          onChange={(e) => setRefPath(e.target.value)} />
                      </>
                    )}
                  </>
                )}
                <Toggle label="Ultimate cloning" on={ultimate} onChange={setUltimate}
                  hint="Adds the reference transcript for audio-continuation cloning — highest fidelity." />
                {ultimate && (
                  <>
                    <label className="field-label" htmlFor="ptext">Reference transcript</label>
                    <textarea id="ptext" className="field" rows={2} value={promptText}
                      placeholder="Exact transcript of the reference clip"
                      onChange={(e) => setPromptText(e.target.value)} />
                  </>
                )}
              </div>
            )}

            <div className="card">
              <h2>{tab === "speak" ? "Text to speak" : "Content to synthesize"}</h2>
              <div className="samples">
                {KHMER_SAMPLES.map((s) => (
                  <button key={s.label} className="chip" onClick={() => setText(s.km)}>{s.label}</button>
                ))}
              </div>
              <textarea className="field kh" rows={4} value={text} onChange={(e) => setText(e.target.value)}
                placeholder="វាយអត្ថបទខ្មែរនៅទីនេះ… (or any of the 30 supported languages)" />
              <p className="hint">No language tag needed — the model detects Khmer (or any supported language) from the text itself.</p>
            </div>

            <div className="card">
              <h2>Sampling</h2>
              <Slider label="cfg_value" value={cfg} min={1} max={4} step={0.1} onChange={setCfg}
                hint="Guidance strength on LocDiT. Higher follows the prompt more closely; too high can degrade quality." />
              <Slider label="inference_timesteps" value={steps} min={4} max={32} step={1} onChange={setSteps}
                hint="Diffusion steps. Higher = better quality, lower = faster." />
              <div className="toggle-grid">
                <Toggle label="Normalize text" on={normalize} onChange={setNormalize} />
                <Toggle label="Denoise" on={denoise} onChange={setDenoise} />
                <Toggle label="Retry bad cases" on={retry} onChange={setRetry} />
              </div>
            </div>
          </section>

          {/* ---------- right column: output ---------- */}
          <section className="col">
            <div className="card">
              <div className="card-head-row">
                <h2>Generate</h2>
                <button className={"stream-toggle" + (streamMode ? " on" : "")}
                  onClick={() => setStreamMode((v) => !v)} disabled={!streamSupported}
                  title={streamSupported ? "Play audio as it's generated" : "Only available for the default /api/tts endpoint"}>
                  {streamMode ? "◉" : "○"} Stream
                </button>
              </div>
              <label className="field-label" htmlFor="ep">Inference endpoint <span className="opt">optional</span></label>
              <input id="ep" className="field mono" placeholder="https://your-server/tts  (POST, returns audio)"
                value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
              <p className="hint">Leave empty to preview the pipeline in demo mode. The model itself runs on a GPU server (~8 GB VRAM) — point this at your VoxCPM endpoint to get real audio back.</p>
              <button className="cta" onClick={generate}
                disabled={genState.status === "running" || genState.status === "queued" || !text.trim() || (needsRef && !hasRef)}>
                {genState.status === "queued" ? `Queued — position ${genState.position}…`
                  : genState.status === "running" ? (streamMode && streamSupported ? "Streaming…" : "Synthesizing…")
                  : "Generate speech"}
              </button>
              {needsRef && !hasRef && <p className="hint">Upload a reference clip (or set a server path) to generate.</p>}

              {genState.status === "queued" && (
                <div className="note">In queue — position {genState.position}. This updates automatically every {POLL_INTERVAL_MS / 1000}s.</div>
              )}

              <ol className="pipeline">
                {GEN_STEPS.map((s, i) => (
                  <li key={s} className={genState.step > i ? "done" : genState.status === "running" && genState.step === i ? "now" : ""}>
                    <span className="dot" />{s}
                  </li>
                ))}
              </ol>

              {genState.status === "demo-done" && (
                <div className="note">Demo run complete — no endpoint set, so no audio was produced. Copy the Python below to run the real thing, or connect an endpoint above.</div>
              )}
              {genState.status === "error" && (
                <div className="note err">{genState.error}</div>
              )}
              {audioUrl && (
                <div className="player">
                  <button className="play" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
                    {playing ? "❚❚" : "▶"}
                  </button>
                  <span>output.wav · 48 kHz</span>
                  <a className="dl" href={audioUrl} download="output.wav">Download</a>
                  <audio ref={audioRef} src={audioUrl} onEnded={() => setPlaying(false)} />
                </div>
              )}
            </div>

            <div className="card code-card">
              <div className="code-head">
                <h2>Python · voxcpm</h2>
                <button className="copy" onClick={copySnippet}>{copied ? "Copied ✓" : "Copy"}</button>
              </div>
              <pre className="mono code">{snippet}</pre>
              <p className="hint">Mirrors every control above. <span className="mono">pip install voxcpm</span> · Python ≥ 3.10 · PyTorch ≥ 2.5 · CUDA ≥ 12.</p>
            </div>
          </section>
        </main>
      ) : (
        /* ---------- model tab ---------- */
        <main className="grid">
          <section className="col">
            <div className="card">
              <h2>Architecture</h2>
              <table className="spec">
                <tbody>
                  {[
                    ["Pipeline", "LocEnc → TSLM → RALM → LocDiT (tokenizer-free diffusion AR)"],
                    ["Backbone", "MiniCPM-4 · 2B parameters · bfloat16"],
                    ["Audio VAE", "AudioVAE V2 — 16 kHz in, 48 kHz out (built-in super-resolution)"],
                    ["Training data", "2M+ hours multilingual speech"],
                    ["LM token rate", "6.25 Hz"],
                    ["Max sequence", "8192 tokens"],
                    ["VRAM", "~8 GB"],
                    ["RTF (RTX 4090)", "~0.30 standard · ~0.13 with Nano-vLLM"],
                    ["License", "Apache-2.0 — free for commercial use"],
                  ].map(([k, v]) => (
                    <tr key={k}><th>{k}</th><td>{v}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h2>Fine-tuning</h2>
              <p className="body">Supports full SFT and LoRA fine-tuning with as little as 5–10 minutes of audio — which is exactly how a Khmer-specialized checkpoint like this one comes about.</p>
              <pre className="mono code small">{`python scripts/train_voxcpm_finetune.py \\
    --config_path conf/voxcpm_v2/voxcpm_finetune_lora.yaml`}</pre>
            </div>
          </section>
          <section className="col">
            <div className="card">
              <h2>30 languages</h2>
              <div className="langs">
                {LANGUAGES.map((l) => (
                  <span key={l} className={"lang" + (l === "Khmer" ? " km-hl" : "")}>{l}</span>
                ))}
              </div>
              <p className="hint">Plus 9 Chinese dialects. Khmer is this checkpoint's specialty.</p>
            </div>
            <div className="card">
              <h2>Responsible use</h2>
              <p className="body">The model card strictly forbids use for impersonation, fraud, or disinformation. Label AI-generated speech clearly, and get consent before cloning anyone's voice.</p>
            </div>
            <div className="card">
              <h2>Links</h2>
              <ul className="links">
                <li><a href="https://huggingface.co/sumnim/VoxCPM2-Khmer" target="_blank" rel="noreferrer">Model card on Hugging Face</a></li>
                <li><a href="https://github.com/OpenBMB/VoxCPM" target="_blank" rel="noreferrer">VoxCPM on GitHub</a></li>
                <li><a href="https://voxcpm.readthedocs.io/en/latest/" target="_blank" rel="noreferrer">Documentation</a></li>
                <li><a href="https://huggingface.co/papers/2509.24650" target="_blank" rel="noreferrer">Paper · arXiv 2509.24650</a></li>
              </ul>
            </div>
          </section>
        </main>
      )}

      <footer className="foot">
        <span>VoxCPM2-Khmer · tokenizer-free diffusion TTS · fine-tuned checkpoint by sumnim on OpenBMB's VoxCPM2</span>
      </footer>
    </div>
  );
}

/* ---------- styles ---------- */

const css = `
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+Khmer:wght@400;600&display=swap');

.root {
  min-height: 100vh;
  background:
    radial-gradient(1100px 500px at 85% -10%, rgba(227,168,59,0.07), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, rgba(87,185,154,0.05), transparent 60%),
    ${T.bg};
  color: ${T.text};
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 14px;
  padding: 28px clamp(16px, 4vw, 48px) 40px;
}
.root * { box-sizing: border-box; }
.mono { font-family: 'JetBrains Mono', monospace; }
.kh, .kh-title { font-family: 'Noto Sans Khmer', 'Inter', sans-serif; }

.head { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.head-left { display: flex; gap: 16px; align-items: center; }
.glyph {
  width: 56px; height: 56px; border-radius: 14px; flex: none;
  display: grid; place-items: center;
  font-family: 'Noto Sans Khmer', sans-serif; font-size: 30px; font-weight: 600;
  color: ${T.bgDeep};
  background: linear-gradient(140deg, ${T.goldHi}, ${T.gold} 55%, #B87F1F);
  box-shadow: 0 6px 24px rgba(227,168,59,0.25);
}
.eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.08em; color: ${T.muted}; text-transform: uppercase; }
h1 { font-family: 'Space Grotesk', sans-serif; font-size: clamp(22px, 3.4vw, 30px); font-weight: 700; margin: 2px 0 0; letter-spacing: -0.01em; }
.kh-title { color: ${T.gold}; font-weight: 600; margin-left: 8px; }
.badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge { padding: 5px 11px; border: 1px solid ${T.line}; border-radius: 99px; font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: ${T.muted}; background: ${T.surface}; }
.badge.gold { color: ${T.gold}; border-color: rgba(227,168,59,0.4); }

.wave { width: 100%; height: 56px; display: block; margin-bottom: 20px; }

.tabs { display: flex; gap: 4px; border-bottom: 1px solid ${T.line}; margin-bottom: 22px; overflow-x: auto; }
.tab {
  appearance: none; background: none; border: none; cursor: pointer;
  font-family: 'Space Grotesk', sans-serif; font-size: 14px; font-weight: 500;
  color: ${T.muted}; padding: 10px 16px 12px;
  border-bottom: 2px solid transparent; margin-bottom: -1px; white-space: nowrap;
}
.tab:hover { color: ${T.text}; }
.tab.active { color: ${T.gold}; border-bottom-color: ${T.gold}; }
.tab:focus-visible, .chip:focus-visible, .cta:focus-visible, .toggle:focus-visible, .copy:focus-visible, .play:focus-visible {
  outline: 2px solid ${T.jade}; outline-offset: 2px; border-radius: 6px;
}

.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: start; }
@media (max-width: 880px) { .grid { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 18px; min-width: 0; }

.card { background: ${T.surface}; border: 1px solid ${T.line}; border-radius: 14px; padding: 18px 18px 16px; }
.card h2 { font-family: 'Space Grotesk', sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: ${T.text}; margin: 0 0 12px; }
.card-head-row { display: flex; justify-content: space-between; align-items: center; }
.card-head-row h2 { margin: 0 0 12px; }
.stream-toggle { appearance: none; cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: ${T.muted}; background: ${T.surfaceHi}; border: 1px solid ${T.line}; border-radius: 99px; padding: 5px 11px; margin-bottom: 10px; }
.stream-toggle:hover:not(:disabled) { color: ${T.text}; border-color: ${T.mutedDeep}; }
.stream-toggle.on { color: ${T.bgDeep}; background: ${T.jade}; border-color: ${T.jade}; font-weight: 600; }
.stream-toggle:disabled { opacity: .4; cursor: not-allowed; }
.hint { font-size: 12px; color: ${T.muted}; line-height: 1.5; margin: 6px 0 0; }
.body { font-size: 13.5px; line-height: 1.6; color: ${T.text}; margin: 0 0 10px; }

.samples { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  appearance: none; cursor: pointer; font: inherit; font-size: 12px;
  color: ${T.muted}; background: ${T.surfaceHi}; border: 1px solid ${T.line};
  border-radius: 99px; padding: 5px 12px; transition: all .12s ease;
}
.chip:hover { color: ${T.text}; border-color: ${T.mutedDeep}; }
.chip.sel { color: ${T.bgDeep}; background: ${T.gold}; border-color: ${T.gold}; font-weight: 600; }
.chip-row { display: flex; gap: 10px; align-items: baseline; margin-bottom: 10px; flex-wrap: wrap; }
.chip-group { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: ${T.mutedDeep}; text-transform: uppercase; letter-spacing: .06em; width: 62px; flex: none; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.prefix { margin-top: 8px; padding: 8px 12px; border-radius: 8px; background: ${T.bgDeep}; color: ${T.jade}; font-size: 12.5px; }

.dropzone {
  cursor: pointer; text-align: center; padding: 22px 14px;
  border: 1.5px dashed ${T.line}; border-radius: 12px; background: ${T.bgDeep};
  transition: border-color .12s, background .12s;
}
.dropzone:hover, .dropzone.over { border-color: ${T.gold}; background: rgba(227,168,59,0.06); }
.dropzone-label { font-size: 13.5px; color: ${T.text}; margin: 0 0 4px; }
.upload-bar { width: 100%; height: 6px; border-radius: 99px; background: ${T.line}; overflow: hidden; margin-bottom: 8px; }
.upload-bar-fill { height: 100%; background: ${T.gold}; transition: width .15s; }
.upload-done { display: flex; align-items: center; gap: 10px; padding: 10px 13px; background: ${T.bgDeep}; border: 1px solid ${T.line}; border-radius: 10px; }
.upload-done-info { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
.upload-name { font-size: 13px; color: ${T.text}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-meta { font-size: 11.5px; color: ${T.muted}; }
.upload-remove { appearance: none; cursor: pointer; font-size: 11.5px; color: ${T.muted}; background: ${T.surfaceHi}; border: 1px solid ${T.line}; border-radius: 7px; padding: 6px 11px; flex: none; }
.upload-remove:hover { color: #E06C5C; border-color: rgba(224,108,92,0.4); }
.disclosure { appearance: none; cursor: pointer; background: none; border: none; color: ${T.muted}; font-size: 12px; padding: 10px 0 2px; font-family: 'JetBrains Mono', monospace; }
.disclosure:hover { color: ${T.text}; }

.field {
  width: 100%; background: ${T.bgDeep}; color: ${T.text};
  border: 1px solid ${T.line}; border-radius: 10px;
  padding: 11px 13px; font: inherit; font-size: 14px; line-height: 1.6;
  resize: vertical;
}
.field:focus { outline: none; border-color: ${T.gold}; }
.field.kh { font-size: 16px; }
.field-label { display: block; font-size: 12px; color: ${T.muted}; margin: 10px 0 6px; }
.opt { color: ${T.mutedDeep}; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; margin-left: 6px; }

.ctl { margin-bottom: 14px; }
.ctl-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
.ctl-head label { font-family: 'JetBrains Mono', monospace; font-size: 12.5px; color: ${T.text}; }
.val { color: ${T.gold}; font-size: 13px; }
input[type=range] { width: 100%; accent-color: ${T.gold}; height: 22px; cursor: pointer; background: transparent; }

.toggle-grid { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }
.toggle { display: flex; gap: 10px; align-items: flex-start; appearance: none; background: none; border: none; cursor: pointer; padding: 7px 2px; text-align: left; color: ${T.text}; font: inherit; }
.knob-track { width: 34px; height: 19px; border-radius: 99px; background: ${T.line}; flex: none; position: relative; transition: background .15s; margin-top: 1px; }
.toggle.on .knob-track { background: ${T.jade}; }
.knob { position: absolute; top: 2.5px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: ${T.text}; transition: transform .15s; }
.toggle.on .knob { transform: translateX(14px); background: ${T.bgDeep}; }
.toggle-body { display: flex; flex-direction: column; gap: 1px; }
.toggle-label { font-size: 13.5px; }
.toggle .hint { margin: 1px 0 0; }

.cta {
  width: 100%; margin-top: 14px; padding: 13px;
  font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700;
  color: ${T.bgDeep}; background: linear-gradient(135deg, ${T.goldHi}, ${T.gold});
  border: none; border-radius: 11px; cursor: pointer; transition: filter .12s, transform .12s;
}
.cta:hover:not(:disabled) { filter: brightness(1.07); transform: translateY(-1px); }
.cta:disabled { opacity: .45; cursor: not-allowed; }

.pipeline { list-style: none; margin: 16px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.pipeline li { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: ${T.mutedDeep}; }
.pipeline .dot { width: 8px; height: 8px; border-radius: 50%; background: ${T.line}; flex: none; transition: background .2s; }
.pipeline li.now { color: ${T.gold}; }
.pipeline li.now .dot { background: ${T.gold}; animation: pulse 1s ease infinite; }
.pipeline li.done { color: ${T.jade}; }
.pipeline li.done .dot { background: ${T.jade}; }
@keyframes pulse { 50% { opacity: .4; } }
@media (prefers-reduced-motion: reduce) { .pipeline li.now .dot { animation: none; } .cta:hover { transform: none; } }

.note { margin-top: 14px; padding: 11px 13px; border-radius: 10px; font-size: 12.5px; line-height: 1.55; background: rgba(87,185,154,0.09); border: 1px solid rgba(87,185,154,0.3); color: ${T.text}; }
.note.err { background: rgba(224,108,92,0.09); border-color: rgba(224,108,92,0.4); }

.player { margin-top: 14px; display: flex; align-items: center; gap: 12px; padding: 10px 13px; background: ${T.bgDeep}; border: 1px solid ${T.line}; border-radius: 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: ${T.muted}; }
.play { width: 38px; height: 38px; border-radius: 50%; border: none; cursor: pointer; background: ${T.gold}; color: ${T.bgDeep}; font-size: 13px; flex: none; }
.dl { margin-left: auto; color: ${T.jade}; text-decoration: none; }
.dl:hover { text-decoration: underline; }

.code-card { position: sticky; top: 16px; }
.code-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.code-head h2 { margin: 0; }
.copy { appearance: none; cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: ${T.muted}; background: ${T.surfaceHi}; border: 1px solid ${T.line}; border-radius: 7px; padding: 5px 11px; }
.copy:hover { color: ${T.gold}; border-color: rgba(227,168,59,0.4); }
.code { background: ${T.bgDeep}; border: 1px solid ${T.line}; border-radius: 10px; padding: 14px; font-size: 12px; line-height: 1.65; color: #C9D2E3; overflow-x: auto; margin: 0; white-space: pre; }
.code.small { font-size: 11.5px; margin-top: 4px; }

.spec { width: 100%; border-collapse: collapse; font-size: 13px; }
.spec th { text-align: left; font-family: 'JetBrains Mono', monospace; font-weight: 500; font-size: 11.5px; color: ${T.muted}; padding: 8px 14px 8px 0; vertical-align: top; white-space: nowrap; }
.spec td { padding: 8px 0; color: ${T.text}; line-height: 1.5; border-bottom: 1px solid ${T.line}; }
.spec th { border-bottom: 1px solid ${T.line}; }
.spec tr:last-child th, .spec tr:last-child td { border-bottom: none; }

.langs { display: flex; flex-wrap: wrap; gap: 6px; }
.lang { padding: 5px 11px; border-radius: 99px; font-size: 12px; background: ${T.surfaceHi}; border: 1px solid ${T.line}; color: ${T.muted}; }
.lang.km-hl { background: ${T.gold}; color: ${T.bgDeep}; border-color: ${T.gold}; font-weight: 600; }

.links { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 9px; font-size: 13.5px; }
.links a { color: ${T.jade}; text-decoration: none; }
.links a:hover { text-decoration: underline; color: ${T.gold}; }

.foot { margin-top: 26px; padding-top: 14px; border-top: 1px solid ${T.line}; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: ${T.mutedDeep}; }
`;
