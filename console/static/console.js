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
  $("next").textContent = S.waiting ? "clock paused" : S.playing ? `running at ${S.speeds[S.speed_i].label}` : "paused: press ▶ or Skip to next";
  $("play").textContent = S.playing ? "⏸" : "▶";
  $("play").disabled = !!S.waiting;
  $("skip").disabled = !!S.waiting;                   // no skipping while the agent works or waits for you
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
  $("fleet").innerHTML = S.fleet.map((s) => `<div class="sat ${s.triage} ${s.sat === f ? "sel" : ""}" data-ev="${esc(s.event || "")}">
    <b>${esc(s.sat)}</b> ${s.triage === "CLEAR" ? "" : `<span class="tag ${s.triage}">${s.triage}</span>`}<div>${esc(s.next)}</div></div>`).join("");
  $("fleet").querySelectorAll(".sat").forEach((d) => (d.onclick = () => d.dataset.ev && control("focus", d.dataset.ev)));
}

// ---------- the pictures share one distance scale: square root, so 303 m, 1 km and 3 km are spread evenly
const D_MAX = 4200;
const SC = (m) => Math.sqrt(Math.min(Math.max(m, 0), D_MAX) / D_MAX);
const zoneCol = (m) => m < 303.3 ? "var(--escalate)" : m < 1000 ? "var(--watch)" : m < 3033 ? "var(--muted)" : "var(--ok)";
const fmtM = (m) => `${Math.round(m).toLocaleString()} m`;

function drawFlyby() {
  const e = S.focus, svg = $("flyby");
  if (!e) { svg.innerHTML = ""; return; }
  const box = svg.getBoundingClientRect();                      // draw in real pixels, so text stays text-sized
  const W = Math.max(420, Math.round(box.width)), H = Math.max(260, Math.round(box.height));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const L = 120, R = 16, T = 12, B = 40, pw = W - L - R, ph = H - T - B;
  const TW = 600, K = 15;                                         // ±10 minutes shown; stretched near closest approach
  const y = (m) => T + ph * (1 - SC(m));
  const X = (dt) => L + pw * (0.5 + 0.5 * Math.asinh(Math.max(-TW, Math.min(TW, dt)) / K) / Math.asinh(TW / K));
  let g = "";
  // the zones, named in the left margin so nothing in the picture can land on top of them
  const bands = [[0, 303.3, "var(--escalate)", "ESCALATE", "risk > 1 in 10,000", .16],
                 [303.3, 1000, "var(--watch)", "WATCH", "under 1 km", .16],
                 [1000, 3033, "var(--line)", "", "", .25],
                 [3033, D_MAX, "var(--ok)", "CLEAR", "risk < 1 in a million", .16]];
  for (const [a, b, c, t, t2, o] of bands) {
    g += `<rect x="${L}" y="${y(b)}" width="${pw}" height="${y(a) - y(b)}" fill="${c}" opacity="${o}"/>`;
    if (t) {
      const cy = (y(a) + y(b)) / 2;
      g += `<text x="4" y="${cy}" style="fill:${c};font-weight:800;font-size:14px">${t}</text>`;
      g += `<text x="4" y="${cy + 15}" style="fill:${c};font-size:11px">${t2}</text>`;
    }
  }
  for (const m of [303, 1000, 3033]) g += `<line x1="${L}" x2="${L + pw}" y1="${y(m)}" y2="${y(m)}" stroke="var(--muted)" stroke-dasharray="3 4" opacity=".5"/><text x="${L - 6}" y="${y(m) + 4}" text-anchor="end" class="muted" style="font-size:11px">${m.toLocaleString()}</text>`;
  g += `<text x="${L - 6}" y="${y(0) + 4}" text-anchor="end" class="muted" style="font-size:11px">0 m</text>`;
  for (const [dt, l] of [[-600, "−10 min"], [-60, "−1 min"], [0, "closest approach"], [60, "+1 min"], [600, "+10 min"]])
    g += `<line x1="${X(dt)}" x2="${X(dt)}" y1="${T}" y2="${T + ph}" stroke="var(--line)"/><text x="${X(dt)}" y="${T + ph + 18}" text-anchor="middle" class="muted">${l}</text>`;
  // the other tracks: what it would have been, or what it will be
  const ghost = (m, txt, col, dash) => {
    g += `<line x1="${L}" x2="${L + pw}" y1="${y(m)}" y2="${y(m)}" stroke="${col}" stroke-width="3" stroke-dasharray="${dash}" opacity=".85"/>`;
    g += `<text x="${L + pw - 8}" y="${y(m) + (m < 600 ? 18 : -8)}" text-anchor="end" class="halo" style="fill:${col};font-weight:700;font-size:14px">${txt}</text>`;
  };
  if (e.before_burn) ghost(e.before_burn.miss_m, `without the burn: ${fmtM(e.before_burn.miss_m)}`, zoneCol(e.before_burn.miss_m), "8 6");
  if (e.before) ghost(e.before.miss_m, `on the old tracking: ${fmtM(e.before.miss_m)}`, zoneCol(e.before.miss_m), "8 6");
  if (e.burn && e.burn.status === "scheduled") ghost(e.burn.miss_after_m, `after the burn (scheduled): ${fmtM(e.burn.miss_after_m)}`, "var(--ok)", "2 5");
  // us
  g += `<rect x="${X(0) - 9}" y="${y(0) - 9}" width="18" height="18" fill="var(--info)"/><text x="${X(0) + 14}" y="${y(0) - 6}" style="font-weight:700">${esc(e.fleet_sat)} (us)</text>`;
  // the object, on its current track
  const dt = -e.to_tca_s, col = zoneCol(e.miss_m), oy = y(e.miss_m), ox = X(dt);
  g += `<line x1="${L}" x2="${ox}" y1="${oy}" y2="${oy}" stroke="${col}" stroke-width="3"/><line x1="${ox}" x2="${L + pw}" y1="${oy}" y2="${oy}" stroke="${col}" stroke-width="2" stroke-dasharray="2 5"/>`;
  g += `<line x1="${X(0)}" x2="${X(0)}" y1="${oy}" y2="${y(0) - 12}" stroke="${col}" stroke-width="2"/>`;
  const below = oy <= T + 40;                    // near the top, the object's label goes under its line: put the miss under that
  g += `<text x="${X(0) + 10}" y="${below ? oy + 58 : Math.min(y(0) - 24, oy + 26)}" class="halo" style="fill:${col};font-weight:700;font-size:17px">${dt < 0 ? "will miss by" : "missed by"} ${fmtM(e.miss_m)}</text>`;
  const far = Math.abs(dt) > TW;
  g += `<circle cx="${ox}" cy="${oy}" r="11" fill="${col}"/>`;
  const where = far ? (dt < 0 ? `closest approach ${span(e.to_tca_s)}` : "passed") : `${fmtKm(e.range_km)} away · ${e.rel_speed_km_s.toFixed(1)} km/s`;
  const lx = Math.max(L + 8, Math.min(L + pw - 8, ox)), anchor = ox > L + pw * .6 ? "end" : ox < L + pw * .25 ? "start" : "middle";
  g += `<text x="${lx}" y="${below ? oy + 30 : oy - 18}" text-anchor="${anchor}" class="halo" style="font-weight:700;font-size:15px">${esc(e.object_name)} · ${where}</text>`;
  svg.innerHTML = g;
}

function drawBanner() {
  const b = $("banner"), c = S.coming_up;
  if (S.waiting) {
    const w = S.cards.find((x) => x.id === S.waiting);
    const ready = w && w.status !== "thinking";
    b.className = "banner agent";
    b.innerHTML = `<span class="k">${ready ? "YOUR CALL" : "THE AGENT IS ON IT"}</span><span class="what">${esc(w ? w.title : "")}</span>
      <span class="when">${ready ? "Approve or Hold on the agent's card. The clock waits for you." : "The clock is paused while the agent works."}</span>`;
    return;
  }
  if (!c) { b.className = "banner"; b.innerHTML = `<span class="k">END OF THE WEEK</span><span class="what">That's the pinned week.</span>`; return; }
  b.className = "banner " + c.kind;
  b.innerHTML = `<span class="k">COMING UP · ${esc(c.in.toUpperCase())} OF SIM TIME</span><span class="what">${esc(c.label)}${c.what ? ": " + esc(c.what) : ""}</span>
    <span class="when">${esc(c.at)}</span><button id="skip2">Skip to it ⏭</button>`;
  $("skip2").onclick = () => control("skip");
}

function drawFacts() {
  const e = S.focus;
  if (!e) return;
  $("ftitle").innerHTML = `${esc(e.fleet_sat)} vs ${esc(e.object_name)} <span class="sub">(${e.norad_cat_id}, ${esc(e.object_type || "")})</span> <span class="tag ${e.triage}">${e.triage}</span>` +
    (e.source.includes("SIMULATED") ? ` <span class="tag SIM">SIMULATED TRACKING</span>` : "");
  const passed = e.to_tca_s < -30;
  $("rlabel").textContent = passed ? "Closest approach was" : "Range now";
  $("range").textContent = passed ? `${Math.round(e.miss_m).toLocaleString()} m` : fmtKm(e.range_km);
  $("range").className = "range" + (passed ? " passed" + (e.max_pc >= S.rules.clear_pc ? " bad" : "") : "");
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
      : `<line x1="${X}" y1="${y - 5}" x2="${X}" y2="${y + 5}" stroke="${col}" opacity=".35"/>`;
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
    drawHeader(); drawBanner(); drawFleet(); drawFlyby(); drawFacts(); drawCards(); drawTimeline();
  } catch (e) { $("next").textContent = "lost the console backend: retrying"; }
  setTimeout(poll, 250);
}
async function pollEvents() {
  try { EVENTS = await (await fetch("/api/events")).json(); } catch (e) {}
  setTimeout(pollEvents, 2000);
}
pollEvents(); poll();
