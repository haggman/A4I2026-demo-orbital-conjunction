// Flight dynamics console: polls the backend's state and draws it. All the physics and all the decisions live
// on the server (sim.py, the agent); this file only draws and sends button presses.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const post = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
const control = (action, value) => post("/api/control", { action, value });
const R_MAX = 4000, PX = 200;                  // encounter picture: 4 km to the edge
let S = null, EVENTS = [], lastCards = "", lastChat = "", lastModes = "";

try { const t = localStorage.getItem("console-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
$("theme").onclick = () => {
  const d = document.documentElement;
  d.dataset.theme = d.dataset.theme === "light" ? "dark" : "light";
  try { localStorage.setItem("console-theme", d.dataset.theme); } catch (e) {}
};
$("play").onclick = () => control(S && S.playing ? "pause" : "play");
$("skip").onclick = () => control("skip");
document.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => control(b.dataset.act)));
$("modesel").onchange = (e) => control("mode", e.target.value);
$("chat").onsubmit = (e) => {
  e.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  $("q").value = "";
  post("/api/chat", { text: q });
};

function fmtKm(km) {
  if (km < 10) return km.toFixed(3) + " km";
  if (km < 1000) return km.toFixed(1) + " km";
  return Math.round(km).toLocaleString() + " km";
}
function span(s) {
  const a = Math.abs(s), sign = s < 0 ? "ago" : "";
  let t;
  if (a < 90) t = a.toFixed(1) + " s";
  else if (a < 5400) t = Math.floor(a / 60) + " min " + String(Math.floor(a % 60)).padStart(2, "0") + " s";
  else if (a < 172800) t = Math.floor(a / 3600) + " h " + String(Math.floor((a % 3600) / 60)).padStart(2, "0") + " min";
  else t = (a / 86400).toFixed(1) + " days";
  return sign ? t + " ago" : "in " + t;
}

function drawHeader() {
  $("clock").textContent = S.now;
  $("next").textContent = S.waiting ? "Paused: the agent is on it" : S.next ? `next: ${S.next.kind} ${S.next.at} (${S.next.in})` : "end of the week";
  $("play").textContent = S.playing ? "⏸" : "▶";
  $("play").disabled = !!S.waiting;
  $("speeds").innerHTML = S.speeds.map((s, i) => `<button class="${i === S.speed_i ? "on" : ""}" data-i="${i}">${esc(s.label)}</button>`).join("");
  $("speeds").querySelectorAll("button").forEach((b) => (b.onclick = () => control("speed", +b.dataset.i)));
  const m = $("mode");
  m.textContent = S.mode === "replay" ? "REPLAY" : "LIVE AGENT";
  m.className = "chip" + (S.mode === "replay" ? " replay" : "");
  if (S.agent_error) { m.textContent = "NO AGENT"; m.className = "chip err"; }
  m.title = S.agent_error ? S.agent_error : S.mode === "replay" ? `Playing back ${S.recording}.json, recorded from a real run` : `Live Gemini; recording to ${S.recording}.json`;
  $("snap").textContent = `fixed snapshot ${S.snapshot}`;
  const modes = JSON.stringify([S.mode, S.recording, S.recordings]);
  if (modes !== lastModes) {
    lastModes = modes;
    const cur = S.mode === "live" ? "live" : `replay:${S.recording}`;
    const opts = ["live"].concat(S.recordings.map((r) => `replay:${r}`));
    $("modesel").innerHTML = opts.map((o) => `<option value="${esc(o)}" ${o === cur ? "selected" : ""}>${o === "live" ? "live Gemini" : "replay · " + esc(o.slice(7))}</option>`).join("");
  }
}

function drawFleet() {
  const f = S.focus ? S.focus.fleet_sat : null;
  $("fleet").innerHTML = S.fleet.map((s) => `<div class="sat ${s.triage} ${s.sat === f ? "focus" : ""}" data-ev="${esc(s.event || "")}">
    <b>${esc(s.sat)}</b> ${s.triage === "CLEAR" ? "" : `<span class="tag ${s.triage}">${s.triage}</span>`}<div>${esc(s.next)}</div></div>`).join("");
  $("fleet").querySelectorAll(".sat").forEach((d) => (d.onclick = () => d.dataset.ev && control("focus", d.dataset.ev)));
}

function pt(p) {                             // encounter-plane metres -> SVG: sideways to the right, radial up
  let x = p[1], y = -p[0];
  const r = Math.hypot(x, y), k = r > R_MAX ? R_MAX / r : 1;
  return [(x * k * PX) / R_MAX, (y * k * PX) / R_MAX, r > R_MAX];
}
function drawPlane() {
  const e = S.focus, r = S.rules;
  if (!e) { $("plane").innerHTML = ""; return; }
  const hbr = r.hbr_m, lines = [
    { m: hbr / Math.sqrt(Math.E * r.escalate_pc), c: "var(--escalate)", t: "escalate" },
    { m: r.watch_m, c: "var(--watch)", t: "watch" },
    { m: hbr / Math.sqrt(Math.E * r.clear_pc), c: "var(--ok)", t: "clear" }];
  let g = `<circle r="${PX}" fill="none" stroke="var(--line)"/>`;
  g += `<line x1="-${PX}" y1="0" x2="${PX}" y2="0" stroke="var(--line)"/><line x1="0" y1="-${PX}" x2="0" y2="${PX}" stroke="var(--line)"/>`;
  for (const l of lines) {
    const rr = (l.m * PX) / R_MAX;
    g += `<circle r="${rr}" fill="none" stroke="${l.c}" stroke-width="2" stroke-dasharray="${l.t === "clear" ? "0" : "5 4"}"/>`;
    g += `<text x="0" y="${rr + 14}" text-anchor="middle" class="halo" style="fill:${l.c}">${l.t} ${Math.round(l.m).toLocaleString()} m</text>`;
  }
  g += `<text x="${PX - 4}" y="16" text-anchor="end" class="muted halo">sideways →</text><text x="6" y="${-PX + 14}" class="muted">↑ up (radial)</text>`;
  g += `<rect x="-6" y="-6" width="12" height="12" fill="var(--info)"/><text x="10" y="18" class="muted">${esc(e.fleet_sat)}</text>`;
  if (e.plane_before_m) {
    const [bx, by] = pt(e.plane_before_m), [ax, ay] = pt(e.plane_m);
    g += `<circle cx="${bx}" cy="${by}" r="6" fill="none" stroke="var(--muted)" stroke-width="2"/><text x="${bx + 9}" y="${by + 4}" class="muted halo">before</text>`;
    g += `<line x1="${bx}" y1="${by}" x2="${ax}" y2="${ay}" stroke="var(--ok)" stroke-width="2" stroke-dasharray="4 3"/>`;
  }
  if (e.burn && e.burn.status === "scheduled" && e.burn.plane_after_m) {
    const [px, py] = pt(e.burn.plane_after_m);
    g += `<circle cx="${px}" cy="${py}" r="8" fill="none" stroke="var(--ok)" stroke-width="2" stroke-dasharray="3 3"/><text x="${px + 11}" y="${py + 4}" style="fill:var(--ok)">after the burn (scheduled)</text>`;
  }
  if (e.plane_m) {
    const [x, y, out] = pt(e.plane_m);
    const col = e.triage === "ESCALATE" ? "var(--escalate)" : e.triage === "WATCH" ? "var(--watch)" : e.triage === "NOISE" ? "var(--noise)" : "var(--ok)";
    const below = y < -PX + 30;
    g += `<circle cx="${x}" cy="${y}" r="9" fill="${col}"/><text x="${Math.max(-PX + 100, Math.min(PX - 100, x))}" y="${below ? y + 26 : y - 15}" text-anchor="middle" class="halo" style="font-weight:700;font-size:14px">${esc(e.object_name)} ${Math.round(e.miss_m).toLocaleString()} m${out ? " (off scale)" : ""}</text>`;
  }
  $("plane").setAttribute("viewBox", `-${PX + 24} -${PX + 12} ${2 * PX + 48} ${2 * PX + 48}`);
  $("plane").innerHTML = g;
}

function drawFacts() {
  const e = S.focus;
  if (!e) return;
  $("ftitle").innerHTML = `${esc(e.fleet_sat)} vs ${esc(e.object_name)} <span class="sub">(${e.norad_cat_id}, ${esc(e.object_type || "")})</span> <span class="tag ${e.triage}">${e.triage}</span>` +
    (e.source.includes("SIMULATED") ? ` <span class="tag SIM">SIMULATED TRACKING</span>` : "");
  $("range").textContent = fmtKm(e.range_km);
  const frac = Math.max(0, Math.min(1, 1 - Math.log10(Math.max(e.range_km, 0.1) / 0.1) / 5));   // 0.1 km full, 10,000 km empty
  $("rangebar").style.width = (frac * 100).toFixed(1) + "%";
  $("rangebar").style.background = e.to_tca_s > 0 && e.to_tca_s < 600 ? "var(--escalate)" : "var(--info)";
  $("countdown").textContent = e.to_tca_s < 0 && e.to_tca_s > -900
    ? `closest approach was ${Math.round(e.miss_m).toLocaleString()} m, ${span(e.to_tca_s)} · ${e.tca}`
    : `closest approach ${span(e.to_tca_s)} · ${e.tca}`;
  const b = e.burn;
  const rows = [
    ["predicted miss", `${e.miss_m.toLocaleString(undefined, { maximumFractionDigits: 1 })} m`],
    ["worst-case Pc", e.max_pc.toExponential(2)],
    ["R / I / C", `${Math.round(e.radial_m)} / ${Math.round(e.in_track_m)} / ${Math.round(e.cross_track_m)} m`],
    ["closing speed", `${e.rel_speed_km_s.toFixed(1)} km/s`],
    ["tracking age at TCA", `${e.age_days.toFixed(2)} days${e.stale ? " (stale)" : ""}`],
    ["elements", e.source],
  ];
  if (b) rows.push(["burn", `${b.delta_v_m_s} m/s ${b.direction} at ${b.burn_utc.slice(11, 16)} UTC · ${b.status}`]);
  $("facts").innerHTML = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
}

function md(s) {                              // just enough of the assessment's markdown
  return esc(s).replace(/^## (.*)$/gm, "<b>$1</b>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>");
}
function cardHtml(c) {
  const agent = c.who === "agent";
  let h = `<div class="card ${c.level} ${agent ? "agent" : ""}" data-ev="${esc(c.event || "")}">
    <div class="who">${agent ? "AGENT" : "WATCHER"} · ${esc(c.at)}${c.simulated ? ' · <span class="tag SIM">SIMULATED</span>' : ""}${c.replayed_from ? " · replay" : ""}</div>
    <h3>${esc(c.title)}</h3>${c.lines.map((l) => `<p>${esc(l)}</p>`).join("")}`;
  if (agent) {
    if (c.steps && c.steps.length) h += `<ul class="steps">${c.steps.map((s) => `<li>${esc(s.step)} <span class="sub">+${s.t}s</span></li>`).join("")}</ul>`;
    if (c.status === "thinking") h += `<p class="thinking">Agent working</p>`;
    if (c.text) h += `<div class="words">${esc(c.text)}</div>`;
    if (c.summary) h += `<div class="summary">${esc(c.summary)}</div>`;
    if (c.error) h += `<p class="err">${esc(c.error)}</p>`;
    if (c.assessment && c.assessment.markdown) h += `<details><summary>Conjunction Assessment &amp; Maneuver Recommendation</summary><div>${md(c.assessment.markdown)}</div></details>`;
    if (c.actions && c.actions.length) h += `<div class="acts"><button class="approve" data-card="${c.id}" data-choice="approve">Approve</button><button class="hold" data-card="${c.id}" data-choice="hold">Hold</button></div>`;
    if (c.decision) h += `<p class="decision ${c.decision}">${c.decision === "approve" ? "Approved" : "Held"} by the operator</p>`;
    if (c.seconds) h += `<p class="sub">agent turn ${c.seconds} s</p>`;
  }
  return h + "</div>";
}
function chatHtml(c) {
  return `<div class="card agent chat"><div class="who">CHAT · ${esc(c.at)}</div><p class="chatq">${esc(c.q)}</p>
    ${(c.steps || []).length ? `<ul class="steps">${c.steps.map((s) => `<li>${esc(s.step)}</li>`).join("")}</ul>` : ""}
    ${c.a === null ? '<p class="thinking">Agent working</p>' : `<div class="chata">${esc(c.a)}</div>`}${c.error ? `<p class="err">${esc(c.error)}</p>` : ""}</div>`;
}
function drawCards() {
  const k = JSON.stringify([S.cards, S.chat]);
  if (k === lastCards) return;
  lastCards = k;
  // newest first; chat questions sit in the feed at the moment they were asked
  const items = S.cards.map((c) => ({ t: c.at_utc, html: cardHtml(c) })).concat(S.chat.map((c, i) => ({ t: c.at_utc || "", i, html: chatHtml(c) })));
  items.sort((a, b) => (a.t < b.t ? 1 : a.t > b.t ? -1 : (b.i ?? -1) - (a.i ?? -1)));
  $("cards").innerHTML = items.map((x) => x.html).join("");
  $("cards").querySelectorAll("button[data-card]").forEach((b) => (b.onclick = () => {
    b.parentElement.querySelectorAll("button").forEach((x) => (x.disabled = true));
    post("/api/decide", { card_id: b.dataset.card, choice: b.dataset.choice });
  }));
  $("cards").querySelectorAll(".card[data-ev]").forEach((d) => (d.ondblclick = () => d.dataset.ev && control("focus", d.dataset.ev)));
}

function drawTimeline() {
  const W = 1200, end = S.end_s, x = (t) => 10 + (t / end) * (W - 20);
  let g = "";
  for (let d = 0; d <= 7; d++) {
    const t = d * 86400, X = x(t);
    g += `<line x1="${X}" y1="14" x2="${X}" y2="100" stroke="var(--line)"/>`;
    if (d < 7) {
      const day = new Date(Date.parse("2026-09-25T01:00:00Z") + t * 1000);
      g += `<text x="${X + 4}" y="12" class="muted">${day.toUTCString().slice(0, 11)}</text>`;
    }
  }
  const rowY = { ESCALATE: 36, WATCH: 60, CLEAR: 90, NOISE: 90 };
  for (const e of EVENTS) {
    const X = x(e.t_s), y = rowY[e.triage] || 90, tracked = e.tracked;
    const col = e.triage === "ESCALATE" ? "var(--escalate)" : e.triage === "WATCH" ? "var(--watch)" : tracked ? "var(--ok)" : "var(--noise)";
    g += tracked ? `<circle cx="${X}" cy="${y}" r="7" fill="${col}" data-ev="${esc(e.key)}" style="cursor:pointer"><title>${esc(e.fleet_sat)} vs ${esc(e.object_name)} ${esc(e.tca)} ${Math.round(e.miss_m)} m</title></circle>`
      : `<line x1="${X}" y1="${y - 5}" x2="${X}" y2="${y + 5}" stroke="${col}"/>`;
    if (e.burn) { const bx = x((Date.parse(e.burn.burn_utc) - Date.parse("2026-09-25T01:00:00Z")) / 1000); g += `<path d="M${bx - 6},${y + 14} L${bx + 6},${y + 14} L${bx},${y + 4} Z" fill="var(--ok)"><title>burn ${esc(e.burn.burn_utc)}</title></path>`; }
    if (S.focus && e.key === S.focus.key) g += `<circle cx="${X}" cy="${y}" r="11" fill="none" stroke="var(--info)" stroke-width="2"/>`;
  }
  g += `<text x="${W - 12}" y="${rowY.ESCALATE + 4}" text-anchor="end" class="muted">escalate</text><text x="${W - 12}" y="${rowY.WATCH + 4}" text-anchor="end" class="muted">watch</text><text x="${W - 12}" y="${rowY.NOISE + 4}" text-anchor="end" class="muted">noise</text>`;
  const N = x(S.t_s);
  g += `<line x1="${N}" y1="14" x2="${N}" y2="104" stroke="var(--info)" stroke-width="3"/>`;
  $("timeline").innerHTML = g;
  $("timeline").querySelectorAll("[data-ev]").forEach((c) => (c.onclick = () => control("focus", c.dataset.ev)));
}

async function poll() {
  try {
    S = await (await fetch("/api/state")).json();
    drawHeader(); drawFleet(); drawPlane(); drawFacts(); drawCards(); drawTimeline();
  } catch (e) { $("next").textContent = "lost the console backend: retrying"; }
  setTimeout(poll, 250);
}
async function pollEvents() {
  try { EVENTS = await (await fetch("/api/events")).json(); } catch (e) {}
  setTimeout(pollEvents, 2000);
}
pollEvents(); poll();
