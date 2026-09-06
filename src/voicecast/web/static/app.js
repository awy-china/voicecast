/* VoiceCast · 声波幻境 —— 波形粒子引擎 + Motion 动效 + 全功能 */
"use strict";
const $ = (id) => document.getElementById(id);

/* ══════════ 开屏仪式：字母逐个浮出 ══════════ */
(function boot() {
  const word = $("bootWord");
  const txt = word.textContent.trim();
  word.textContent = "";
  [...txt].forEach((ch, i) => {
    const s = document.createElement("span");
    s.textContent = ch;
    s.style.animationDelay = (0.15 + i * 0.07) + "s";
    word.appendChild(s);
  });
  setTimeout(() => {
    $("boot").classList.add("gone");
    $("app").classList.add("entered");
    setTimeout(() => $("boot").remove(), 600);
  }, 2300);
})();

/* ══════════ 全屏波形粒子场引擎 ══════════ */
const field = $("wavefield");
const ctx = field.getContext("2d");
let W = 0, H = 0, storm = 0, mouseX = -9999;
let lines = [];
const LINE_N = 8;
const AMBER = [245, 166, 35], CYAN = [53, 224, 192];

function resize() {
  const dpr = window.devicePixelRatio || 1;
  W = window.innerWidth; H = window.innerHeight;
  field.width = W * dpr; field.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  lines = [];
  for (let i = 0; i < LINE_N; i++) {
    lines.push({
      y: (H / (LINE_N + 1)) * (i + 1) + (Math.random() - 0.5) * 60,
      amp: 8 + Math.random() * 22,
      speed: 0.25 + Math.random() * 0.45,
      phase: Math.random() * Math.PI * 2,
      freq: 0.008 + Math.random() * 0.012,
      mix: i % 2 === 0 ? AMBER : CYAN,
      alpha: 0.16 + Math.random() * 0.16,
    });
  }
}
window.addEventListener("resize", resize);
resize();

function drawWaveField(now) {
  const t = now / 1000;
  ctx.clearRect(0, 0, W, H);
  const ampBoost = storm > 0.01 ? 1 + storm * 2.6 : 1;

  for (const ln of lines) {
    const pts = [];
    for (let x = 0; x <= W; x += 6) {
      const dMouse = mouseX >= 0 ? Math.max(0, 1 - Math.abs(x - mouseX) / 380) : 0;
      const v =
        Math.sin(x * ln.freq + t * ln.speed * 2 + ln.phase) * 0.65 +
        Math.sin(x * ln.freq * 2.7 - t * ln.speed * 1.3) * 0.35;
      const n = Math.sin(x * 0.004 + ln.phase * 3) * 0.5;
      let y = ln.y + v * (ln.amp * (1 + dMouse * 1.4) * ampBoost) + n * 6;
      if (storm > 0.01) y += (Math.random() - 0.5) * storm * 26;
      pts.push([x, y]);
    }
    // 渐变线
    const g = ctx.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0, `rgba(${ln.mix},${ln.alpha * (1 + storm)})`);
    g.addColorStop(1, `rgba(${ln.mix},${ln.alpha * (1 + storm)})`);
    ctx.beginPath();
    pts.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
    ctx.strokeStyle = g;
    ctx.lineWidth = 1 + storm * 0.6;
    ctx.shadowColor = `rgba(${ln.mix},${0.25 + storm * 0.4})`;
    ctx.shadowBlur = 6 + storm * 12;
    ctx.stroke();
    ctx.shadowBlur = 0;
    // 第二遍细线（光晕）
    ctx.beginPath();
    pts.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
    ctx.strokeStyle = `rgba(${ln.mix},${(ln.alpha + 0.12) * (1 + storm)})`;
    ctx.lineWidth = 0.6;
    ctx.stroke();
  }
  if (storm > 0.01) storm *= 0.985;
  requestAnimationFrame(drawWaveField);
}
requestAnimationFrame(drawWaveField);

document.addEventListener("mousemove", (e) => {
  mouseX = e.clientX;
  const sp = $("spotlight");
  sp.style.setProperty("--spot-x", e.clientX + "px");
  sp.style.setProperty("--spot-y", e.clientY + "px");
});
function stormUp() { storm = 1; }
document.addEventListener("visibilitychange", () => { if (document.hidden) { /* 自动暂停由 rAF 处理 */ } });

/* ══════════ 拆字标题（词级 stagger） ══════════ */
function splitTitle(el) {
  const text = el.textContent.trim();
  el.textContent = "";
  // 中文按 3-4 字句读切词；英文/数字按空格
  const hasCJK = /[\u4e00-\u9fff]/.test(text);
  let toks;
  if (hasCJK) {
    toks = [];
    for (let i = 0; i < text.length; i += 3) toks.push(text.slice(i, i + 3));
  } else {
    toks = text.split(/\s+/).filter(Boolean);
  }
  toks.forEach((tok, i) => {
    const w = document.createElement("span");
    w.className = "w";
    const inner = document.createElement("span");
    inner.textContent = tok;
    inner.style.animationDelay = (0.1 + i * 0.08) + "s";
    w.appendChild(inner);
    el.appendChild(w);
  });
}
document.querySelectorAll(".big-title[data-split]").forEach((el, idx) => {
  el.dataset.done = "0";
  el._split = () => { if (el.dataset.done === "1") return; el.dataset.done = "1"; splitTitle(el); };
});
function activeScene() { return document.querySelector(".scene.active"); }
function splitActiveTitles() {
  activeScene().querySelectorAll(".big-title[data-split]").forEach((el) => el._split());
}

/* ══════════ 导航 ══════════ */
document.querySelectorAll(".rail-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".rail-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".scene").forEach((s) => s.classList.remove("active"));
    btn.classList.add("active");
    const sc = $("scene-" + btn.dataset.view);
    sc.classList.remove("active");
    void sc.offsetWidth; // 重启动画
    sc.classList.add("active");
    splitActiveTitles();
    const grid = $("assetGrid");
    if (grid) renderAssets();
  });
});

/* ══════════ 引擎灯 ══════════ */
async function loadEngines() {
  try {
    const res = await fetch("/api/engines");
    const list = await res.json();
    const box = $("engineLights");
    box.innerHTML = "";
    for (const e of list) {
      const i = document.createElement("i");
      i.className = e.available ? (e.name === "gpt_sovits" ? "on gpt" : "on") : "off";
      i.title = `${e.display}: ${e.available ? "ON" : "OFF"}`;
      box.appendChild(i);
    }
  } catch (_) { /* 静默 */ }
}

/* ══════════ 波形绘制（结果卡） ══════════ */
function drawWave(canvas, points, playing = false) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const c2 = canvas.getContext("2d");
  c2.setTransform(dpr, 0, 0, dpr, 0, 0);
  c2.clearRect(0, 0, w, h);
  const mid = h / 2, n = points.length;
  if (!n) {
    c2.strokeStyle = "rgba(255,255,255,0.1)";
    c2.beginPath(); c2.moveTo(0, mid); c2.lineTo(w, mid); c2.stroke();
    return;
  }
  const step = w / n;
  const grad = c2.createLinearGradient(0, 0, w, 0);
  grad.addColorStop(0, "rgba(245,166,35,0.4)");
  grad.addColorStop(0.5, "rgba(245,166,35,0.95)");
  grad.addColorStop(1, "rgba(255,192,77,0.5)");
  c2.beginPath();
  for (let i = 0; i < n; i++) {
    const x = i * step, amp = Math.max(2, points[i] * h * 0.4);
    i === 0 ? c2.moveTo(x, mid - amp) : c2.lineTo(x, mid - amp);
  }
  for (let i = n - 1; i >= 0; i--) {
    const x = i * step, amp = Math.max(2, points[i] * h * 0.4);
    c2.lineTo(x, mid + amp);
  }
  c2.closePath();
  c2.fillStyle = grad;
  c2.fill();
  if (playing) {
    c2.fillStyle = "rgba(255,255,255,0.07)";
    c2.fillRect(0, 0, w, h);
  }
}
function fmtTime(s) {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${(s % 60).toFixed(1).padStart(4, "0")}`;
}
function bindPlayer(btnId, audioId, waveId, timeId, getUrl) {
  const btn = $(btnId), audio = $(audioId), canvas = $(waveId), tc = $(timeId);
  let raf = null;
  btn.addEventListener("click", () => {
    const url = getUrl();
    if (!url) return;
    if (window.__play === audio) {
      audio.pause(); audio.currentTime = 0; window.__play = null;
      cancelAnimationFrame(raf);
      if (canvas.__pts) drawWave(canvas, canvas.__pts);
      return;
    }
    if (window.__play) { window.__play.pause(); window.__play = null; }
    audio.src = url; audio.play(); window.__play = audio;
    const tick = () => {
      if (tc) tc.textContent = fmtTime(audio.currentTime);
      if (canvas.__pts) drawWave(canvas, canvas.__pts, true);
      raf = requestAnimationFrame(tick);
    };
    tick();
    audio.onended = () => {
      window.__play = null; cancelAnimationFrame(raf);
      if (canvas.__pts) drawWave(canvas, canvas.__pts);
      if (tc) tc.textContent = "00:00.0";
    };
  });
}
function showVoice(prefix, payload) {
  $(prefix + "ProfileId").textContent = payload.profile || "—";
  $(prefix + "Meta").textContent = `${payload.name || ""}${payload.engine ? " · " + payload.engine : ""}`;
  const canvas = $(prefix + "Wave");
  if (canvas) {
    canvas.__pts = payload.waveform || [];
    setTimeout(() => drawWave(canvas, canvas.__pts), 80);
  }
  if (payload.audio_url) window["__" + prefix + "Url"] = payload.audio_url;
  const pe = $(prefix + "Params");
  if (pe && payload.params) {
    const p = payload.params;
    pe.textContent = `pitch=${p.pitch ?? 0}  speed=${p.speed ?? 1.0}` +
      (p.ref_file ? `  ·  ${String(p.ref_file).split("/").pop()}` : "");
  }
  const rp = $(prefix + "Result");
  rp.classList.remove("hidden");
  rp.style.animation = "none";
  void rp.offsetWidth;
  rp.style.animation = "";
}
function setStatus(msg, ok) {
  const sb = document.querySelector(".statusbar");
  sb.textContent = msg;
  sb.className = "statusbar" + (ok === true ? " ok" : ok === false ? " err" : "");
}

/* ══════════ 01 音色设计 ══════════ */
$("designBtn").addEventListener("click", async () => {
  const desc = $("designDesc").value.trim();
  const st = $("designStatus"), btn = $("designBtn");
  if (!desc) { st.textContent = "❌ 请输入角色声音描述"; st.className = "status-line show err"; return; }
  st.textContent = "⏳ 正在生成… 让声波动起来";
  st.className = "status-line show";
  btn.disabled = true;
  stormUp();
  try {
    const res = await fetch("/api/design", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: desc }),
    });
    const data = await res.json();
    if (!res.ok) { st.textContent = "❌ " + (data.detail || "生成失败"); st.className = "status-line show err"; setStatus("DESIGN ERR", false); return; }
    showVoice("design", data);
    st.textContent = "✅ 音色已锁定 · " + (data.profile || "");
    st.className = "status-line show ok";
    setStatus("VOICE READY · " + (data.engine || ""), true);
  } catch (e) {
    st.textContent = "❌ 网络错误: " + e.message; st.className = "status-line show err";
  } finally { btn.disabled = false; }
});
$("designDesc").addEventListener("keydown", (e) => { if (e.key === "Enter") $("designBtn").click(); });
bindPlayer("designPlay", "designAudio", "designWave", "designTime", () => window.__designUrl);

/* ══════════ 02 音色混合 ══════════ */
async function loadSamples() {
  try {
    const res = await fetch("/api/samples");
    const list = await res.json();
    const opt = (v, t) => { const o = document.createElement("option"); o.value = v; o.textContent = t; return o; };
    const main = $("blendMain"), aux = $("blendAux");
    main.innerHTML = ""; aux.innerHTML = "";
    for (const s of list) {
      main.appendChild(opt(s.id, `${s.name}（${s.id}）`));
      aux.appendChild(opt(s.id, `${s.name}（${s.id}）`));
    }
    if (list.length > 1) aux.options[1].selected = true;
  } catch (_) { /* 静默 */ }
}
$("blendBtn").addEventListener("click", async () => {
  const main = $("blendMain").value;
  const aux = [...$("blendAux").selectedOptions].map((o) => o.value);
  const st = $("blendStatus");
  if (!main || !aux.length) { st.textContent = "❌ 请选 SOURCE A 与至少一个 SOURCE B"; st.className = "status-line show err"; return; }
  st.textContent = "⏳ 融合中… 两路声波汇合";
  st.className = "status-line show";
  $("blendBtn").disabled = true;
  stormUp();
  try {
    const res = await fetch("/api/blend", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ main, aux }),
    });
    const data = await res.json();
    if (!res.ok) { st.textContent = "❌ " + (data.detail || "融合失败"); st.className = "status-line show err"; setStatus("BLEND ERR", false); return; }
    showVoice("blend", data);
    st.textContent = "✅ 新音色诞生 · " + (data.profile || "");
    st.className = "status-line show ok";
    setStatus("BLEND READY", true);
  } catch (e) {
    st.textContent = "❌ " + e.message; st.className = "status-line show err";
  } finally { $("blendBtn").disabled = false; }
});
bindPlayer("blendPlay", "blendAudio", "blendWave", "blendTime", () => window.__blendUrl);

/* ══════════ 03 批量配音 ══════════ */
$("batchBtn").addEventListener("click", async () => {
  const btn = $("batchBtn"), mon = $("batchMonitor"), log = $("bmLog"),
    count = $("tapeCount"), bar = $("bmBar");
  log.innerHTML = "";
  mon.classList.remove("hidden");
  btn.disabled = true;
  let done = 0, total = 0;
  const addLine = (rec, cls) => {
    const d = document.createElement("div");
    d.className = "log-line " + (cls || "");
    d.innerHTML = `<span class="n">${String(rec.line_no || "").padStart(3, " ")}</span>` +
      `<span class="st">${rec.role || ""}</span>` +
      `<span class="detail">${esc(rec.engine || "—")}${rec.error ? " · " + esc(rec.error) : ""}</span>`;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    done = rec.line_no || done;
    if (rec.total) total = rec.total;
    count.textContent = `${done}/${total}`;
    if (total) bar.style.width = Math.round((done / total) * 100) + "%";
  };
  try {
    const res = await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        script: $("batchScript").value.trim(), cast: $("batchCast").value.trim(),
        out_dir: $("batchOut").value.trim() || "outputs/web", dry: $("batchDry").checked,
      }),
    });
    if (!res.ok || !res.body) throw new Error("HTTP " + res.status);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done: sd } = await reader.read();
      if (sd) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const p of parts) {
        const raw = p.replace(/^data: /, "").trim();
        if (!raw) continue;
        const evt = JSON.parse(raw);
        if (evt.type === "line") addLine(evt, evt.status === "error" ? "err" : evt.status === "ok" ? "ok" : "");
        else if (evt.type === "summary") {
          count.textContent = "DONE";
          bar.style.width = "100%";
          addLine({ line_no: "•", role: "汇总" }, "ok");
          addLine({ line_no: "", role: "", detail: "", engine: "" }, "ok");
          addResult(`成功 ${evt.ok} / 失败 ${evt.error} / 拦截 ${evt.blocked || 0} / 成本 ¥${evt.total_cost}`);
          setStatus("BATCH COMPLETE · 可导出剪映包", true);
          renderTapeTable(evt.rows || []);
        } else if (evt.type === "error") {
          addResult("❌ 运行失败: " + evt.error);
          setStatus("BATCH ERR", false);
        }
      }
    }
  } catch (e) { addResult("❌ " + e.message); setStatus("BATCH ERR", false); }
  finally { btn.disabled = false; }
});
function addResult(t) {
  const d = document.createElement("div");
  d.className = "log-line ok";
  d.innerHTML = `<span class="n"></span><span class="st"></span><span class="detail" style="color:var(--green)">${esc(t)}</span>`;
  $("bmLog").appendChild(d);
  $("bmLog").scrollTop = $("bmLog").scrollHeight;
}
let rerunAudio = null;
function renderTapeTable(rows) {
  const outDir = $("batchOut").value.trim() || "outputs/web";
  const wrap = document.createElement("div");
  wrap.style.cssText = "margin-top:8px;font-size:12px;display:flex;flex-direction:column;gap:3px";
  for (const r of rows) {
    if (r[3] !== "ok") continue;
    const [lineNo, , role, , engine, file] = r;
    const url = `/api/audio?path=${encodeURIComponent(outDir + "/" + file)}`;
    const row = document.createElement("div");
    row.className = "log-line ok";
    row.innerHTML = `<span class="n">${lineNo}</span><span class="st">${esc(role)}</span>` +
      `<span class="detail">${esc(engine)} · ${esc(String(file).split("/").pop())}</span>` +
      `<span><button class="mini-op" title="试听">▶</button> <button class="mini-op" title="重生成该句">↻</button></span>`;
    row.querySelector(".mini-op").addEventListener("click", () => {
      if (rerunAudio) rerunAudio.pause();
      rerunAudio = new Audio(url); rerunAudio.play();
    });
    row.querySelectorAll(".mini-op")[1].addEventListener("click", async (e) => {
      const b = e.target; b.textContent = "…"; b.disabled = true;
      try {
        const res = await fetch("/api/rerun", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ script: $("batchScript").value.trim(), cast: $("batchCast").value.trim(),
            out_dir: outDir, line_no: Number(lineNo) }),
        });
        const data = await res.json();
        b.textContent = data.ok ? "✓" : "✗";
      } catch (_) { b.textContent = "✗"; }
      finally { setTimeout(() => { b.textContent = "↻"; b.disabled = false; }, 1200); }
    });
    wrap.appendChild(row);
  }
  $("bmLog").appendChild(wrap);
}
$("batchExportBtn").addEventListener("click", async () => {
  const b = $("batchExportBtn");
  b.disabled = true;
  try {
    const res = await fetch("/api/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ out_dir: $("batchOut").value.trim() || "outputs/web" }),
    });
    const data = await res.json();
    if (!res.ok) { addResult("❌ " + (data.detail || "导出失败")); return; }
    addResult(`✅ 剪映包: ${data.deliver}（${(data.srt || []).join("、")}）`);
  } catch (e) { addResult("❌ " + e.message); }
  finally { b.disabled = false; }
});

/* ══════════ 04 音色资产 ══════════ */
let allAssets = [], assetFilter = "all", assetAudio = null;
async function loadAssets() {
  try {
    const res = await fetch("/api/recipes");
    allAssets = await res.json();
    renderAssets();
  } catch (_) { /* 静默 */ }
}
function renderAssets() {
  const grid = $("assetGrid");
  if (!grid) return;
  const q = ($("assetsSearch").value || "").toLowerCase();
  const list = allAssets.filter((a) => {
    if (assetFilter === "真人" && !a.tags.includes("真人参考")) return false;
    if (assetFilter === "融合" && !a.tags.includes("融合")) return false;
    if (assetFilter === "edge" && a.tags.includes("真人参考")) return false;
    if (q && !`${a.id} ${a.name} ${a.tags.join(" ")}`.toLowerCase().includes(q)) return false;
    return true;
  });
  grid.innerHTML = "";
  for (const a of list) {
    const c = document.createElement("div");
    c.className = "asset-card";
    const kind = a.tags.includes("真人参考") ? "HUMAN" : a.tags.includes("融合") ? "BLEND" : "SYNTH";
    const kcls = a.tags.includes("真人参考") ? "real" : a.tags.includes("融合") ? "blend" : "";
    c.innerHTML =
      `<div class="ac-kind ${kcls}">${kind}</div>` +
      `<div class="ac-id">${esc(a.id)}</div>` +
      `<div class="ac-name">${esc(a.name)}</div>` +
      `<div class="ac-tags">${a.tags.slice(0, 4).map((t) => `<span class="ac-tag">${esc(t)}</span>`).join("")}</div>` +
      `<button class="ac-play" ${a.preview ? "" : "disabled"}>▶</button>`;
    if (a.preview) {
      c.querySelector(".ac-play").addEventListener("click", (e) => {
        e.stopPropagation();
        if (assetAudio) assetAudio.pause();
        assetAudio = new Audio(a.preview); assetAudio.play();
      });
    }
    c.addEventListener("click", () => {
      if (a.preview) { if (assetAudio) assetAudio.pause(); assetAudio = new Audio(a.preview); assetAudio.play(); }
    });
    grid.appendChild(c);
  }
  if (!list.length) grid.innerHTML = "<div style='color:#5A6472;padding:46px;text-align:center;grid-column:1/-1;font-family:var(--mono)'>NO UNITS MATCH</div>";
}
document.querySelectorAll("#filterChips .chip").forEach((ch) => {
  ch.addEventListener("click", () => {
    document.querySelectorAll("#filterChips .chip").forEach((x) => x.classList.remove("active"));
    ch.classList.add("active");
    assetFilter = ch.dataset.f;
    renderAssets();
  });
});
$("assetsSearch").addEventListener("input", renderAssets);

/* ══════════ 时钟 ══════════ */
setInterval(() => {
  const d = new Date();
  $("clock").textContent = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}, 1000);

/* 工具 */
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

/* ══════════ 启动 ══════════ */
splitActiveTitles();
loadEngines(); loadSamples(); loadAssets();
