/* VoiceCast · 声学实验室 —— 前端逻辑 */
"use strict";

const $ = (id) => document.getElementById(id);

/* ---------- 等化器装饰条 ---------- */
const eqBar = $("eqBar");
for (let i = 0; i < 72; i++) {
  const bar = document.createElement("i");
  bar.style.height = (4 + Math.random() * 26) + "px";
  bar.style.animationDelay = (Math.random() * 0.8) + "s";
  bar.style.animationDuration = (0.5 + Math.random() * 0.5) + "s";
  eqBar.appendChild(bar);
}
const eqLive = (on) => eqBar.classList.toggle("live", on);

/* ---------- 开屏 ---------- */
window.addEventListener("load", () => {
  setTimeout(() => document.getElementById("boot").remove(), 2300);
});

/* ---------- 引擎状态 ---------- */
async function loadEngines() {
  try {
    const res = await fetch("/api/engines");
    const list = await res.json();
    const dots = $("engineDots");
    dots.innerHTML = "";
    for (const e of list) {
      const dot = document.createElement("i");
      dot.className = e.available ? (e.name === "gpt_sovits" ? "on gpt" : "on") : "off";
      dot.title = `${e.display}: ${e.available ? "可用" : "不可用"} — ${e.explain}`;
      dots.appendChild(dot);
    }
  } catch (_) { /* 静默 */ }
}

/* ---------- 导航 ---------- */
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $("view-" + btn.dataset.view).classList.add("active");
  });
});

/* ---------- 波形绘制 ---------- */
function drawWave(canvas, points, playing = false) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  const mid = h / 2;
  const n = points.length;
  if (n === 0) return;
  const step = w / n;

  // 中心参考线
  ctx.strokeStyle = "rgba(139,148,167,0.15)";
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(w, mid); ctx.stroke();

  // 琥珀波形（渐变）
  const grad = ctx.createLinearGradient(0, 0, w, 0);
  grad.addColorStop(0, "rgba(245,166,35,0.45)");
  grad.addColorStop(0.5, "rgba(245,166,35,0.95)");
  grad.addColorStop(1, "rgba(255,192,77,0.55)");

  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = i * step;
    const amp = Math.max(2, points[i] * (h * 0.44));
    if (i === 0) ctx.moveTo(x, mid - amp);
    else ctx.lineTo(x, mid - amp);
  }
  for (let i = n - 1; i >= 0; i--) {
    const x = i * step;
    const amp = Math.max(2, points[i] * (h * 0.44));
    ctx.lineTo(x, mid + amp);
  }
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // 播放中的扫光
  if (playing) {
    ctx.fillStyle = "rgba(255,255,255,0.18)";
    ctx.fillRect(0, 0, w, h);
  }
}

/* ---------- 结果卡片渲染（设计/混合共用） ---------- */
let designAudioUrl = null, blendAudioUrl = null;
let playing = null;

function bindPlayer(btnId, audioId, canvasId, getUrl) {
  const btn = $(btnId), audio = $(audioId), canvas = $(canvasId);
  btn.addEventListener("click", () => {
    const url = getUrl();
    if (!url) return;
    if (playing === audio) { audio.pause(); audio.currentTime = 0; btn.classList.remove("playing"); playing = null; return; }
    if (playing) { playing.pause(); document.querySelectorAll(".play-btn").forEach((b) => b.classList.remove("playing")); }
    audio.src = url;
    audio.play();
    playing = audio;
    btn.classList.add("playing");
    audio.onended = () => { btn.classList.remove("playing"); playing = null; };
    // 播放时波形扫光
    audio.ontimeupdate = () => {
      if (canvas.__pts) drawWave(canvas, canvas.__pts, true);
    };
    audio.onpause = () => { if (canvas.__pts) drawWave(canvas, canvas.__pts, false); };
  });
}

function showResult(prefix, payload) {
  $(prefix + "ProfileId").textContent = payload.profile || "—";
  $(prefix + "Meta").textContent =
    `${payload.name || ""} · ${payload.engine || ""}${payload.reason ? " · " + payload.reason : ""}`;
  const canvas = $(prefix + "Wave");
  canvas.__pts = payload.waveform || [];
  drawWave(canvas, canvas.__pts);
  if (payload.audio_url) {
    if (prefix === "design") designAudioUrl = payload.audio_url;
    else blendAudioUrl = payload.audio_url;
  }
  const paramsEl = $(prefix + "Params");
  if (paramsEl && payload.params) {
    const p = payload.params;
    paramsEl.textContent = `参数: pitch=${p.pitch ?? 0}  speed=${p.speed ?? 1.0}` +
      (p.ref_file ? `  ·  参考: ${p.ref_file.split("/").pop()}` : "");
  }
  $(prefix + "Result").classList.remove("hidden");
}

/* ---------- 设计器 ---------- */
$("designBtn").addEventListener("click", async () => {
  const desc = $("designDesc").value.trim();
  const hint = $("designHint"), btn = $("designBtn");
  if (!desc) { hint.textContent = "请输入角色声音描述"; hint.className = "design-hint error"; return; }
  hint.textContent = "正在生成…（本地引擎首次加载约需 1 分钟）";
  hint.className = "design-hint";
  btn.disabled = true; eqLive(true);
  try {
    const res = await fetch("/api/design", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: desc }),
    });
    const data = await res.json();
    if (!res.ok) { hint.textContent = "❌ " + (data.detail || "生成失败"); hint.className = "design-hint error"; return; }
    hint.textContent = "✅ 生成成功";
    hint.className = "design-hint";
    showResult("design", data);
  } catch (e) {
    hint.textContent = "❌ 网络错误: " + e.message; hint.className = "design-hint error";
  } finally { btn.disabled = false; eqLive(false); }
});
$("designDesc").addEventListener("keydown", (e) => { if (e.key === "Enter") $("designBtn").click(); });
bindPlayer("designPlay", "designAudio", "designWave", () => designAudioUrl);

/* ---------- 混合器 ---------- */
async function loadSamples() {
  try {
    const res = await fetch("/api/samples");
    const list = await res.json();
    const opt = (v, label) => { const o = document.createElement("option"); o.value = v; o.textContent = label; return o; };
    const main = $("blendMain"), aux = $("blendAux");
    main.innerHTML = ""; aux.innerHTML = "";
    for (const s of list) {
      main.appendChild(opt(s.id, `${s.name}（${s.id}）`));
      aux.appendChild(opt(s.id, `${s.name}（${s.id}）`));
    }
    if (list.length > 1) { aux.options[1].selected = true; }
  } catch (_) { /* 静默 */ }
}

$("blendBtn").addEventListener("click", async () => {
  const main = $("blendMain").value;
  const aux = [...$("blendAux").selectedOptions].map((o) => o.value);
  const hint = $("blendHint"), btn = $("blendBtn");
  if (!main || aux.length === 0) { hint.textContent = "请选择主参考与至少一个辅助参考"; hint.className = "design-hint error"; return; }
  hint.textContent = "融合中…（GPT-SoVITS 多说话人融合，约 1 分钟）";
  hint.className = "design-hint";
  btn.disabled = true; eqLive(true);
  try {
    const res = await fetch("/api/blend", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ main, aux }),
    });
    const data = await res.json();
    if (!res.ok) { hint.textContent = "❌ " + (data.detail || "融合失败"); hint.className = "design-hint error"; return; }
    hint.textContent = "✅ 融合成功";
    hint.className = "design-hint";
    showResult("blend", data);
  } catch (e) {
    hint.textContent = "❌ 网络错误: " + e.message; hint.className = "design-hint error";
  } finally { btn.disabled = false; eqLive(false); }
});
bindPlayer("blendPlay", "blendAudio", "blendWave", () => blendAudioUrl);

/* ---------- 批量配音（SSE 流式） ---------- */
$("batchBtn").addEventListener("click", async () => {
  const btn = $("batchBtn"), logCard = $("batchLogCard"), list = $("logList"), count = $("logCount");
  list.innerHTML = "";
  logCard.classList.remove("hidden");
  $("batchSummary").classList.add("hidden");
  btn.disabled = true; eqLive(true);

  const body = {
    script: $("batchScript").value.trim(),
    cast: $("batchCast").value.trim(),
    out_dir: $("batchOut").value.trim() || "outputs/web",
    dry: $("batchDry").checked,
  };

  try {
    const res = await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok || !res.body) throw new Error("HTTP " + res.status);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let done = 0, total = 0;

    const addLine = (rec) => {
      done = rec.line_no || done;
      if (rec.total) total = rec.total;
      const icons = { ok: "✅", error: "❌", blocked: "🚫", budget_skipped: "⏭", planned: "📋" };
      const icon = icons[rec.status] || "•";
      const line = document.createElement("div");
      line.className = "log-line " + (rec.status === "ok" ? "ok" : rec.status === "error" ? "error" : "");
      line.innerHTML = `<span class="n">${String(rec.line_no || "").padStart(3, " ")}</span>` +
        `<span class="st">${icon} ${rec.status || ""}</span>` +
        `<span class="detail">${esc(rec.role || "")} · ${esc(rec.engine || "—")}${rec.error ? " · " + esc(rec.error) : ""}</span>`;
      list.appendChild(line);
      list.scrollTop = list.scrollHeight;
      count.textContent = `${done}/${total}`;
    };

    while (true) {
      const { value, done: streamDone } = await reader.read();
      if (streamDone) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const part of parts) {
        const line = part.replace(/^data: /, "").trim();
        if (!line) continue;
        const evt = JSON.parse(line);
        if (evt.type === "line") addLine(evt);
        else if (evt.type === "summary") {
          total = evt.ok + evt.error + (evt.blocked || 0);
          count.textContent = "完成";
          $("batchSummaryText").textContent =
            `成功 ${evt.ok} / 失败 ${evt.error} / 拦截 ${evt.blocked || 0} / 成本 ${evt.total_cost} 元`;
          $("batchSummary").classList.remove("hidden");
        } else if (evt.type === "error") {
          const line = document.createElement("div");
          line.className = "log-line error";
          line.textContent = "❌ 运行失败: " + evt.error;
          list.appendChild(line);
        }
      }
    }
  } catch (e) {
    const line = document.createElement("div");
    line.className = "log-line error";
    line.textContent = "❌ " + e.message;
    list.appendChild(line);
  } finally { btn.disabled = false; eqLive(false); }
});

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

/* ---------- 启动 ---------- */
loadEngines();
loadSamples();
