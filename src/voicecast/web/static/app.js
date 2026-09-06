/* VoiceCast · 超现实录音棚 —— 前端逻辑 */
"use strict";
const $ = (id) => document.getElementById(id);

/* ============ 开屏 ============ */
window.addEventListener("load", () => setTimeout(() => {
  const b = document.getElementById("boot");
  if (b) b.remove();
}, 2100));

/* ============ VU 电平表 ============ */
function makeVu(el) {
  for (let i = 0; i < 26; i++) {
    const l = document.createElement("i");
    l.dataset.zone = i < 6 ? "hot" : i < 16 ? "mid" : "low";
    l.style.height = (8 + (i / 26) * 34) + "px";
    el.appendChild(l);
  }
}
function vuLive(el, on) {
  if (!el) return;
  el.classList.toggle("live", on);
  if (on) {
    if (el.__t) return;
    el.__t = setInterval(() => {
      [...el.children].forEach((c) => {
        const z = c.dataset.zone;
        const r = Math.random();
        c.classList.toggle("hot", z === "hot" && r > 0.35);
        c.classList.toggle("mid", z === "mid" && r > 0.5);
      });
    }, 90);
  } else if (el.__t) {
    clearInterval(el.__t); el.__t = null;
    [...el.children].forEach((c) => c.classList.remove("hot", "mid"));
  }
}

/* ============ 引擎电源灯 ============ */
async function loadEngines() {
  try {
    const res = await fetch("/api/engines");
    const list = await res.json();
    const box = $("engineLeds");
    box.innerHTML = "";
    for (const e of list) {
      const i = document.createElement("i");
      i.className = e.available ? (e.name === "gpt_sovits" ? "on gpt" : "on") : "off";
      i.title = `${e.display}: ${e.available ? "ON" : "OFF"} — ${e.explain}`;
      box.appendChild(i);
    }
  } catch (_) { /* 静默 */ }
}

/* ============ 台面切换 ============ */
document.querySelectorAll(".deck-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".deck-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".deckview").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $("deck-" + btn.dataset.deck).classList.add("active");
  });
});

/* ============ 波形绘制 ============ */
function drawWave(canvas, points, playing = false) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  const mid = h / 2, n = points.length;
  if (!n) { ctx.fillStyle = "rgba(86,94,106,.25)"; ctx.fillRect(0, mid - .5, w, 1); return; }
  const step = w / n;
  ctx.strokeStyle = "rgba(53,224,192,.14)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(w, mid); ctx.stroke();
  const grad = ctx.createLinearGradient(0, 0, w, 0);
  grad.addColorStop(0, "rgba(245,166,35,.35)");
  grad.addColorStop(.5, "rgba(245,166,35,.95)");
  grad.addColorStop(1, "rgba(255,192,77,.5)");
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = i * step;
    const amp = Math.max(2, points[i] * h * .42);
    i === 0 ? ctx.moveTo(x, mid - amp) : ctx.lineTo(x, mid - amp);
  }
  for (let i = n - 1; i >= 0; i--) {
    const x = i * step, amp = Math.max(2, points[i] * h * .42);
    ctx.lineTo(x, mid + amp);
  }
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
  if (playing) { ctx.fillStyle = "rgba(255,255,255,.08)"; ctx.fillRect(0, 0, w, h); }
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(1).padStart(4, "0")}`;
}

/* 播放器绑定（含时间码 + 波形扫光） */
function bindPlayer(btnId, audioId, waveId, timeId, getUrl) {
  const btn = $(btnId), audio = $(audioId), canvas = $(waveId), tc = $(timeId);
  let raf = null;
  btn.addEventListener("click", () => {
    const url = getUrl();
    if (!url) return;
    if (audio === (window.__playing || null)) {
      audio.pause(); audio.currentTime = 0;
      window.__playing = null; btn.style.color = "";
      cancelAnimationFrame(raf);
      if (canvas.__pts) drawWave(canvas, canvas.__pts);
      return;
    }
    if (window.__playing) { window.__playing.pause(); window.__playing = null; }
    audio.src = url; audio.play(); window.__playing = audio;
    const tick = () => {
      if (tc) tc.textContent = fmtTime(audio.currentTime);
      if (canvas.__pts) drawWave(canvas, canvas.__pts, true);
      raf = requestAnimationFrame(tick);
    };
    tick();
    audio.onended = () => {
      window.__playing = null; cancelAnimationFrame(raf);
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
    setTimeout(() => drawWave(canvas, canvas.__pts), 60);
  }
  if (payload.audio_url) {
    window["__" + prefix + "Url"] = payload.audio_url;
  }
  const paramsEl = $(prefix + "Params");
  if (paramsEl && payload.params) {
    const p = payload.params;
    paramsEl.textContent = `pitch=${p.pitch ?? 0}  speed=${p.speed ?? 1.0}` +
      (p.ref_file ? `  ·  ${String(p.ref_file).split("/").pop()}` : "");
  }
}

/* ============ 状态条 ============ */
const sbMsg = $("sbMsg");
function status(msg, ok) {
  sbMsg.textContent = msg;
  sbMsg.className = "sb-left " + (ok ? "ok" : ok === false ? "err" : "");
}

/* ============ 话放台：音色设计 ============ */
$("designKnob").addEventListener("click", async () => {
  const desc = $("designDesc").value.trim();
  if (!desc) { status("INPUT REQUIRED — 请输入角色描述", false); return; }
  const knob = $("designKnob"), vu = $("designVuLeds");
  knob.classList.add("go");
  vuLive(vu, true);
  status("SYNTHESIZING — " + desc.slice(0, 18) + "…");
  try {
    const res = await fetch("/api/design", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: desc }),
    });
    const data = await res.json();
    if (!res.ok) {
      status("ERR " + (data.detail || "生成失败"), false);
      $("designStatus").textContent = "❌ " + (data.detail || "生成失败");
      $("designStatus").className = "ch-status err";
      return;
    }
    showVoice("design", data);
    $("designStatus").textContent = "✅ VOICE LOCKED — " + (data.profile || "");
    $("designStatus").className = "ch-status ok";
    status("VOICE READY · " + (data.engine || ""), true);
    setTimeout(() => knob.classList.remove("go"), 800);
  } catch (e) {
    status("NETWORK ERR", false);
    $("designStatus").textContent = "❌ " + e.message;
    $("designStatus").className = "ch-status err";
  } finally { vuLive(vu, false); }
});
$("designDesc").addEventListener("keydown", (e) => { if (e.key === "Enter") $("designKnob").click(); });
bindPlayer("designPlay", "designAudio", "designWave", "designTime", () => window.__designUrl);

/* ============ 路由台：音色混合 ============ */
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
  const lamp = $("blendLamp");
  if (!main || !aux.length) { $("blendStatus").textContent = "需要 SOURCE A 与至少一个 SOURCE B"; $("blendStatus").className = "r-status err"; return; }
  lamp.classList.add("live");
  $("blendStatus").textContent = "ROUTING… 双路融合中";
  $("blendStatus").className = "r-status";
  status("BLENDING — " + main + " × " + aux[0], true);
  try {
    const res = await fetch("/api/blend", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ main, aux }),
    });
    const data = await res.json();
    if (!res.ok) { $("blendStatus").textContent = "❌ " + (data.detail || "融合失败"); $("blendStatus").className = "r-status err"; status("BLEND ERR", false); return; }
    showVoice("blend", data);
    $("blendStatus").textContent = "✅ NEW VOICE — " + (data.profile || "");
    $("blendStatus").className = "r-status ok";
    status("BLEND READY · 新音色已生成", true);
  } catch (e) {
    $("blendStatus").textContent = "❌ " + e.message; $("blendStatus").className = "r-status err";
  } finally { lamp.classList.remove("live"); }
});
bindPlayer("blendPlay", "blendAudio", "blendWave", "blendTime", () => window.__blendUrl);

/* ============ 走带台：批量配音 ============ */
$("batchBtn").addEventListener("click", async () => {
  const btn = $("batchBtn"), logWrap = $("tapeLogWrap"), log = $("tapeLog"),
    count = $("tapeCount"), bar = $("tapeProgressBar"), counter = $("tapeCounter");
  log.innerHTML = "";
  logWrap.classList.remove("hidden");
  btn.disabled = true;
  let done = 0, total = 0, t0 = Date.now();

  const addLine = (rec) => {
    done = rec.line_no || done;
    if (rec.total) total = rec.total;
    const icons = { ok: "✅", error: "❌", blocked: "🚫", planned: "📋" };
    const line = document.createElement("div");
    line.className = "log-line " + (rec.status === "ok" ? "ok" : rec.status === "error" ? "error" : "");
    line.innerHTML = `<span class="n">${String(rec.line_no || "").padStart(3, " ")}</span>` +
      `<span class="st">${icons[rec.status] || "•"} ${rec.status || ""}</span>` +
      `<span class="detail">${esc(rec.role || "")} · ${esc(rec.engine || "—")}${rec.error ? " · " + esc(rec.error) : ""}</span>`;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
    count.textContent = `${done}/${total}`;
    if (total) bar.style.width = Math.round((done / total) * 100) + "%";
    counter.textContent = new Date(Date.now() - t0).toISOString().substr(11, 8);
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
        if (evt.type === "line") addLine(evt);
        else if (evt.type === "summary") {
          count.textContent = "DONE";
          bar.style.width = "100%";
          addResultLine(`成功 ${evt.ok} / 失败 ${evt.error} / 拦截 ${evt.blocked || 0} / 成本 ¥${evt.total_cost}`);
          status("BATCH COMPLETE · 可导出剪映包", true);
          renderTapeTable(evt.rows || []);
        } else if (evt.type === "error") {
          addResultLine("❌ 运行失败: " + evt.error);
          status("BATCH ERR", false);
        }
      }
    }
  } catch (e) {
    addResultLine("❌ " + e.message);
    status("BATCH ERR", false);
  } finally { btn.disabled = false; }
});

function addResultLine(txt) {
  const el = document.createElement("div");
  el.className = "tape-result";
  el.textContent = txt;
  document.getElementById("tapeLog").appendChild(el);
}

/* 走带结果：可试听/重生成 */
let rerunAudio = null;
function renderTapeTable(rows) {
  const wrap = document.createElement("div");
  wrap.className = "tape-table";
  const outDir = $("batchOut").value.trim() || "outputs/web";
  const oks = rows.filter((r) => r[3] === "ok");
  const table = document.createElement("table");
  table.style.cssText = "width:100%;border-collapse:collapse;margin-top:10px;font-size:12px";
  table.innerHTML = "<tr style='color:#565E6A'><td style='padding:4px 8px'>行</td><td>角色</td><td>引擎</td><td>文件</td><td style='text-align:right'>操作</td></tr>";
  for (const r of oks) {
    const [lineNo, , role, , engine, file] = r;
    const tr = document.createElement("tr");
    const url = `/api/audio?path=${encodeURIComponent(outDir + "/" + file)}`;
    tr.style.cssText = "border-top:1px solid #23272E";
    tr.innerHTML =
      `<td style='padding:5px 8px;color:#565E6A;font-family:var(--mono)'>${lineNo}</td>` +
      `<td style='color:#8A93A0'>${esc(role)}</td>` +
      `<td style='color:#F5A623;font-family:var(--mono)'>${esc(engine)}</td>` +
      `<td style='color:#565E6A;font-family:var(--mono);font-size:10.5px'>${esc(file)}</td>` +
      `<td style='text-align:right;white-space:nowrap'>` +
      `<button class="tbtn" style="min-width:26px;height:24px;font-size:10px;border-radius:50%" title="试听">▶</button> ` +
      `<button class="tbtn" style="min-width:26px;height:24px;font-size:10px;border-radius:50%" title="重生成该句">↻</button></td>`;
    tr.querySelector("button").addEventListener("click", () => {
      if (rerunAudio) rerunAudio.pause();
      rerunAudio = new Audio(url); rerunAudio.play();
    });
    tr.querySelectorAll("button")[1].addEventListener("click", async (e) => {
      const b = e.target; b.textContent = "…"; b.disabled = true;
      try {
        const res = await fetch("/api/rerun", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ script: $("batchScript").value.trim(), cast: $("batchCast").value.trim(),
            out_dir: outDir, line_no: Number(lineNo) }),
        });
        const data = await res.json();
        b.textContent = data.ok ? "✓" : "✗";
        if (!data.ok && data.detail) addResultLine("重生成失败: " + data.detail);
      } catch (err) { b.textContent = "✗"; }
      finally { setTimeout(() => { b.textContent = "↻"; b.disabled = false; }, 1200); }
    });
    table.appendChild(tr);
  }
  wrap.appendChild(table);
  document.getElementById("tapeLog").appendChild(wrap);
}

/* 导出剪映包 */
$("batchExportBtn").addEventListener("click", async () => {
  const btn = $("batchExportBtn");
  btn.disabled = true; status("EXPORTING… 生成剪映包", true);
  try {
    const res = await fetch("/api/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ out_dir: $("batchOut").value.trim() || "outputs/web" }),
    });
    const data = await res.json();
    if (!res.ok) { addResultLine("❌ " + (data.detail || "导出失败")); status("EXPORT ERR", false); return; }
    addResultLine(`✅ 剪映包: ${data.deliver}（字幕 ${(data.srt || []).join("、")}）`);
    status("EXPORT DONE · 可导入剪映", true);
  } catch (e) { addResultLine("❌ " + e.message); status("EXPORT ERR", false); }
  finally { btn.disabled = false; }
});

/* ============ 设备架：音色资产 ============ */
let allAssets = [], assetFilter = "all", assetAudio = null;

async function loadAssets() {
  try {
    const res = await fetch("/api/recipes");
    allAssets = await res.json();
    renderRackUnits();
    renderPatchGrid();
  } catch (_) { /* 静默 */ }
}
function renderRackUnits() {
  const rack = $("rackUnits");
  rack.innerHTML = "";
  for (const a of allAssets.slice(0, 40)) {
    const u = document.createElement("div");
    u.className = "rack-unit";
    u.title = a.name;
    u.innerHTML = `<div class="ru-light"></div><div class="ru-id">${esc(a.id)}</div><div class="ru-name">${esc(a.name.slice(0, 8))}</div>`;
    u.addEventListener("click", () => {
      if (a.preview) { if (assetAudio) assetAudio.pause(); assetAudio = new Audio(a.preview); assetAudio.play(); }
    });
    rack.appendChild(u);
  }
}
function renderPatchGrid() {
  const grid = $("patchGrid");
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
    const u = document.createElement("div");
    u.className = "patch-unit";
    const kind = a.tags.includes("真人参考") ? "HUMAN" : a.tags.includes("融合") ? "BLEND" : "SYNTH";
    const kcls = a.tags.includes("真人参考") ? "real" : a.tags.includes("融合") ? "blend" : "";
    u.innerHTML =
      `<div class="pu-led"></div>` +
      `<div class="pu-kind ${kcls}">${kind}</div>` +
      `<div class="pu-id">${esc(a.id)}</div>` +
      `<div class="pu-name">${esc(a.name)}</div>` +
      `<div class="pu-tags">${a.tags.slice(0, 4).map((t) => `<span class="pu-tag">${esc(t)}</span>`).join("")}</div>` +
      `<div class="pu-eng">${esc(a.engine)}</div>` +
      `<button class="pu-play" ${a.preview ? "" : "disabled"}>▶</button>`;
    if (a.preview) {
      u.querySelector(".pu-play").addEventListener("click", (e) => {
        e.stopPropagation();
        if (assetAudio) assetAudio.pause();
        assetAudio = new Audio(a.preview); assetAudio.play();
      });
    }
    u.addEventListener("click", () => {
      if (a.preview) { if (assetAudio) assetAudio.pause(); assetAudio = new Audio(a.preview); assetAudio.play(); }
    });
    grid.appendChild(u);
  }
  if (!list.length) grid.innerHTML = "<div style='color:#565E6A;padding:40px;text-align:center;grid-column:1/-1;font-family:var(--mono)'>NO UNITS MATCH</div>";
}
document.querySelectorAll("#patchFilters .chip").forEach((c) => {
  c.addEventListener("click", () => {
    document.querySelectorAll("#patchFilters .chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    assetFilter = c.dataset.f;
    renderPatchGrid();
  });
});
$("assetsSearch").addEventListener("input", renderPatchGrid);

/* ============ 时钟 ============ */
setInterval(() => {
  const d = new Date();
  $("sbClock").textContent = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}, 1000);

/* ============ 工具 ============ */
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

/* ============ 启动 ============ */
makeVu($("designVuLeds"));
loadEngines(); loadSamples(); loadAssets();
