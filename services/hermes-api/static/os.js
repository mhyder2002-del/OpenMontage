const NAV = [
  ["overview", "Overview"],
  ["discovery", "Discovery"],
  ["knowledge", "Knowledge Graph"],
  ["campaigns", "Campaigns"],
  ["orchestra", "Agent Orchestra"],
  ["debugger", "AI Debugger"],
  ["studio", "Studio"],
  ["evolution", "Evolution Lab"],
  ["analytics", "Analytics"],
  ["memory", "Memory"],
  ["command", "Command Center"],
  ["publishing", "Publishing"],
  ["uploads", "Uploads"],
  ["settings", "Settings"],
];

const SUB = {
  overview: "Research · Create · Optimize · Scale",
  discovery: "Cross-platform opportunity intelligence",
  knowledge: "Living memory of what works",
  campaigns: "Launch autonomous media campaigns",
  orchestra: "Live organization · event stream",
  debugger: "Replayable inferences · cost · latency",
  studio: "Compose scenes, captions, and cuts",
  evolution: "Experiments that crown winners",
  analytics: "What moved after each publish",
  memory: "Learned hooks, formats, and gates",
  command: "Health, keys, and inference",
  publishing: "Queue, schedule, and ship",
  uploads: "Source footage and references",
  settings: "Domain, auth, and defaults",
};

const API_KEY_STORAGE = "hermes-api-key";

function getApiKey() {
  try {
    return sessionStorage.getItem(API_KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

function setApiKey(value) {
  try {
    const trimmed = String(value || "").trim();
    if (trimmed) sessionStorage.setItem(API_KEY_STORAGE, trimmed);
    else sessionStorage.removeItem(API_KEY_STORAGE);
  } catch {
    /* private mode */
  }
}

function authHeaders(extra) {
  const headers = { ...(extra || {}) };
  const key = getApiKey();
  if (key) headers.Authorization = `Bearer ${key}`;
  return headers;
}

function apiFetch(url, options) {
  const opts = options || {};
  const method = String(opts.method || "GET").toUpperCase();
  const mutating = method !== "GET" && method !== "HEAD";
  const locked = mutating || String(url).startsWith("/v1/");
  const headers = { ...(opts.headers || {}) };
  if (locked) Object.assign(headers, authHeaders(headers));
  return fetch(url, { ...opts, headers });
}

const TOPICS = [
  ["Automation", "0.51", "0.82", "0.70", "0.82"],
  ["Claude", "0.44", "0.79", "0.74", "0.86"],
  ["UGC Product", "0.39", "0.71", "0.66", "0.80"],
  ["Everyday Carry", "0.50", "0.82", "0.70", "0.82"],
];

const WALK_PLACEHOLDER = "/static/placeholders/walking-skeleton.svg";

function walkPanelHtml() {
  return `
      <article class="card" style="margin-top:0.75rem" id="walk-panel">
        <strong>Campaigns / Studio · walking skeleton</strong>
        <p class="hint">POST /api/v1/scripts → /api/v1/storyboards → /api/v1/thumbnails. Save a Bearer key under Settings first.</p>
        <form id="walk-form">
          <div class="field"><label for="walk-topic">TOPIC</label><input id="walk-topic" value="AI education" /></div>
          <div class="field"><label for="walk-audience">AUDIENCE</label><input id="walk-audience" value="founders" /></div>
          <button type="submit" class="primary" id="walk-run">Generate script → storyboard → thumbnail</button>
        </form>
        <p class="hint" id="walk-status" style="margin-top:0.6rem">Ready. Thumbnail shows ${WALK_PLACEHOLDER} until the chain returns thumbnail_url.</p>
        <pre class="hint" id="walk-script" style="margin-top:0.7rem;white-space:pre-wrap" hidden></pre>
        <div id="walk-scenes"></div>
        <img id="walk-thumb" class="walk-thumb" alt="Walking skeleton thumbnail" src="${WALK_PLACEHOLDER}" width="320" height="180" />
      </article>`;
}

function card(label, value, hint, glow, mint) {
  return `<article class="card${glow ? " glow" : ""}"><div class="label">${label}</div><div class="value${mint ? " mint" : ""}">${value}</div><div class="hint">${hint}</div></article>`;
}

const PAGES = {
  overview() {
    return `
      <p class="hint" id="agent-feed">Loading /api/agents/overview…</p>
      <article class="card os-hero">
        <div class="label">Product walkthrough</div>
        <video class="os-hero-video" src="/static/media/hermes-os.mp4" muted loop playsinline autoplay controls preload="metadata"></video>
        <p class="hint" style="margin:0.7rem 0 0">Muted autoplay — use controls if you want sound.</p>
      </article>
      <article class="card" style="margin-top:0.75rem">
        <strong>Plans</strong>
        <p class="hint">Stripe Checkout for campaign packs and Autonomous v0.4.0. Mode comes from GET /api/billing/config.</p>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.7rem">
          <button type="button" class="primary" data-pay="campaign_launch">Pay campaign launch</button>
          <button type="button" class="ghost" data-subscribe>Subscribe console</button>
        </div>
        <p class="hint" id="billing-status" style="margin-top:0.6rem"></p>
        <p class="hint" id="billing-copy" style="margin-top:0.4rem"></p>
      </article>
      <div class="grid cols-4" style="margin-top:0.75rem">
        ${card("Revenue", "$12.4k", "30d · +18%", true, true)}
        ${card("Views", "2.1M", "Across channels")}
        ${card("CTR", "6.8%", "+11% vs baseline")}
        ${card("Retention", "54%", "+18% evolved")}
        ${card("RPM", "$4.20", "+9%")}
        ${card("Publishing queue", "14", "Scheduled")}
        ${card("AI confidence", "0.91", "Prediction gate")}
        ${card("Opportunities", "37", "High velocity")}
        ${card("Knowledge nodes", "<span id=\"kg-node-count\">—</span>", "Living graph")}
        ${card("Flywheel cycles", "<span id=\"flywheel-cycles\">—</span>", "Live /api/flywheel", true, true)}
        ${card("Agents online", "14", "Orchestra ready")}
        ${card("Channel health", "Strong", "Growth forecast ↑")}
      </div>
      <div class="grid cols-2" style="margin-top:0.75rem">
        <article class="card">
          <div class="label">AI activity</div>
          <div class="feed" style="margin-top:0.7rem">
            <div class="feed-item"><span>Research Agent: Found 6 high-velocity AI education topics</span><time>now</time></div>
            <div class="feed-item"><span>Evolution Lab: Experiment #129 crowned thumbnail B winner</span><time>2m</time></div>
            <div class="feed-item"><span>Publishing Agent: Queued 4 Shorts — YouTube + TikTok</span><time>8m</time></div>
            <div class="feed-item"><span>Analytics Agent: Retention lift +18% after hook rewrite</span><time>14m</time></div>
            <div class="feed-item muted"><span>Memory: Learned: money hooks +23% CTR</span><time>1h</time></div>
          </div>
        </article>
        <article class="card">
          <div class="label">Operating loop</div>
          <div class="pills" style="margin:0.8rem 0">
            <span class="pill">Discover</span><span class="pill">Create</span><span class="pill">Publish</span><span class="pill">Learn</span><span class="pill on">Improve</span>
          </div>
          <p class="hint">Every publish updates the knowledge graph and evolution weights for the next campaign.</p>
          <p class="hint" id="flywheel-status" style="margin-top:0.7rem">Flywheel: loading…</p>
        </article>
      </div>`;
  },
  discovery() {
    return `
      <p class="hint" id="agent-feed">Loading /api/agents/discovery…</p>
      <article class="card">
        <strong>AI opportunity scan</strong>
        <div class="pills" style="margin:0.7rem 0">
          ${["YouTube","Reddit","TikTok","Google Trends","X","News","Competitors"].map((c, i) =>
            `<button type="button" class="pill${i < 4 ? " on" : ""}" data-research="${c}">${c}</button>`
          ).join("")}
        </div>
        <p class="hint" id="research-status">Chip a source to POST /api/agent/research.</p>
      </article>
      <div class="grid cols-4" style="margin-top:0.75rem">
        ${card("Trending", "<span id=\"disc-trending\">—</span>", "Stored nodes")}
        ${card("Emerging", "<span id=\"disc-emerging\">—</span>", "Research source")}
        ${card("Low competition", "<span id=\"disc-open\">—</span>", "Whitespace")}
        ${card("Avg virality", "<span id=\"disc-viral\">—</span>", "From graph", true, true)}
      </div>
      <article class="card" style="margin-top:0.75rem">
        <strong>High-opportunity topics</strong>
        <div id="discovery-nodes"><p class="hint">Loading stored knowledge nodes…</p></div>
      </article>`;
  },
  knowledge() {
    return `
      <p class="hint" id="agent-feed">Loading /api/agents/knowledge…</p>
      <div class="grid cols-3">
        ${card("Nodes", "<span id=\"kg-node-count\">—</span>", "GET /api/knowledge/nodes")}
        ${card("Relations", "<span id=\"kg-rel-count\">—</span>", "Distinct sources")}
        ${card("Feedback loops", "<span id=\"kg-loops\">—</span>", "Analytics → Memory", true, true)}
      </div>
      <article class="card" style="margin-top:0.75rem">
        <strong>Living knowledge graph</strong>
        <div class="chain" style="margin:0.85rem 0">
          <span>Topic</span><i class="arrow">→</i><span>Audience</span><i class="arrow">→</i>
          <span>Hooks</span><i class="arrow">→</i><span>Scripts</span><i class="arrow">→</i>
          <span>Videos</span><i class="arrow">→</i><span>Analytics</span><i class="arrow">→</i>
          <span class="end">Updated Graph</span>
        </div>
        <p class="hint">Every publish strengthens the graph. Hermes doesn’t store files — it stores causal media intelligence.</p>
      </article>
      <article class="card" style="margin-top:0.75rem">
        <strong>Stored nodes</strong>
        <div class="pills" id="kg-nodes" style="margin-top:0.8rem">
          <span class="pill">Loading…</span>
        </div>
      </article>`;
  },
  campaigns() {
    return `
      <p class="hint" id="agent-feed">Loading /api/agents/campaigns…</p>
      <div class="grid cols-2">
        <article class="card">
          <strong>Campaign builder</strong>
          ${[["niche","NICHE","AI education"],["goal","GOAL","Grow subscribers"],["brief","BRIEF","Vertical shorts that teach one AI workflow per cut."],["platforms","PLATFORMS","YouTube Shorts, TikTok, Reels"],["budget","BUDGET","$2,000 / mo"],["freq","FREQUENCY","2 / day"]].map(([id,l,v]) => `
            <div class="field"><label for="${id}">${l}</label><input id="${id}" value="${v}" /></div>`).join("")}
          <button type="button" class="primary" style="width:100%" data-launch>Launch campaign</button>
          <button type="button" class="ghost" style="width:100%;margin-top:0.5rem" data-pay="campaign_launch">Pay launch pack</button>
          <p class="hint" id="launch-status" style="margin-top:0.6rem"></p>
        </article>
        <article class="card">
          <strong>Active cuts</strong>
          <div id="active-cuts"><p class="hint">Launch the video-campaign agent to plan cuts.</p></div>
        </article>
      </div>
      ${walkPanelHtml()}`;
  },
  orchestra() {
    return `
      <p class="hint" id="agent-feed">Loading /api/agents/orchestra…</p>
      <div class="grid cols-4">
        ${card("CEO", "Hermes OS Orchestrator", "Orchestrator")}
        ${card("Agents", "14", "OS + kernel")}
        ${card("Healthy", "98%", "Runtime health", true, true)}
        ${card("Platform", "hermestudios.com", "Reliability layer")}
      </div>
      <article class="card" style="margin-top:0.75rem">
        <strong>Organization</strong>
        <p class="hint" style="margin:0.6rem 0 0">Research · Writer · Editor · Publisher · Analyst — reporting to the orchestrator.</p>
      </article>
      <article class="card" style="margin-top:0.75rem">
        <strong>Live event stream</strong>
        <p class="hint" id="events">Waiting for workflow events…</p>
        <div style="display:flex;gap:0.5rem;margin-top:0.8rem;flex-wrap:wrap">
          <button type="button" class="primary" id="dry-run">Run dry-run campaign</button>
          <button type="button" class="ghost" data-go="debugger">AI Debugger</button>
        </div>
      </article>`;
  },
  debugger() {
    return `
      <p class="hint" id="agent-feed">Loading /api/agents/debugger…</p>
      <div class="grid cols-4">
        ${card("Inferences", "0", "Recorded")}
        ${card("Total cost", "$0.0000", "USD")}
        ${card("Avg latency", "0ms", "p50-ish avg")}
        ${card("Fallback rate", "0", "Provider failover")}
      </div>
      <article class="card" style="margin-top:0.75rem">
        <strong>Probe inference</strong>
        <div style="display:flex;gap:0.5rem;margin-top:0.8rem;flex-wrap:wrap">
          <button type="button" class="primary" id="probe">Run debugger probe</button>
          <button type="button" class="ghost" id="refresh-health">Refresh</button>
        </div>
        <pre class="hint" id="probe-out" style="margin-top:0.8rem;white-space:pre-wrap"></pre>
      </article>
      <article class="card" style="margin-top:0.75rem">
        <strong>Recent inferences</strong>
        <p class="hint" style="margin:0.7rem 0 0">No inferences yet — run a probe or campaign.</p>
      </article>`;
  },
  studio() {
    return `<article class="card"><strong>Studio</strong><p class="hint" id="agent-feed">Loading /api/agents/studio…</p><p class="hint">Scene stack for Hermes OS — Platform Promo and Everyday Carry.</p></article>${walkPanelHtml()}`;
  },
  evolution() {
    return `<p class="hint" id="agent-feed">Loading /api/agents/evolution…</p>
      <div class="grid cols-3">${card("Flywheel cycles","—","Live ticks",true,true)}${card("Crowned","#129","Thumbnail B")}${card("Lift","+18%","Retention")}</div>
      <article class="card" style="margin-top:0.75rem">
        <strong>Perpetual flywheel</strong>
        <p class="hint" id="flywheel-status">Loading /api/flywheel…</p>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.7rem">
          <button type="button" class="primary" id="flywheel-start">Start flywheel</button>
          <button type="button" class="ghost" id="flywheel-stop">Stop</button>
        </div>
      </article>`;
  },
  analytics() {
    return `<p class="hint" id="agent-feed">Loading /api/agents/analytics…</p>
      <div class="grid cols-4">${card("Views","2.1M","Across channels")}${card("CTR","6.8%","+11%")}${card("Retention","54%","+18% evolved")}${card("RPM","$4.20","+9%")}</div>`;
  },
  memory() {
    return `<article class="card"><strong>Memory agent</strong><p class="hint" id="agent-feed">Loading /api/agents/memory…</p><p class="hint">Money hooks +23% CTR. Graph stores causal media intelligence.</p></article>`;
  },
  command() {
    return `<p class="hint" id="agent-feed">Loading /api/agents/command…</p>
      <article class="card"><strong>/readyz</strong><pre class="hint" id="readyz-pre" style="white-space:pre-wrap">checking…</pre></article>
      <article class="card" style="margin-top:0.75rem"><strong>/health</strong><p class="hint" id="cmd-health">Loading /health…</p><p class="hint">GET /health stays public without a key. Bearer HERMES_API_KEY on locked /v1.</p></article>`;
  },
  publishing() {
    return `<article class="card"><strong>Publishing agent</strong><p class="hint" id="agent-feed">Loading /api/agents/publishing…</p><p class="hint">14 scheduled. Last: 4 Shorts — YouTube + TikTok.</p></article>`;
  },
  uploads() {
    return `<article class="card"><strong>Uploads agent</strong><p class="hint" id="agent-feed">Loading /api/agents/uploads…</p><p class="hint">Drop references here. Binary YouTube upload stays on the studio Mac CLI.</p></article>`;
  },
  settings() {
    return `<article class="card"><strong>Settings</strong><p class="hint" id="agent-feed">Loading /api/agents/settings…</p>
      <p class="hint">API key lives in sessionStorage (<code>hermes-api-key</code>) only. Sent as Authorization Bearer on mutating and locked /v1 fetches.</p>
      <form id="api-key-form">
        <div class="field"><label for="api-key-input">HERMES_API_KEY</label><input id="api-key-input" type="password" autocomplete="off" placeholder="Paste key for this tab" /></div>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
          <button type="submit" class="primary">Save for this session</button>
          <button type="button" class="ghost" id="api-key-clear">Clear</button>
        </div>
      </form>
      <p class="hint" id="api-key-status" style="margin-top:0.6rem"></p>
      <p class="hint" id="billing-status" style="margin-top:0.7rem">Loading Stripe…</p>
      <p class="hint" id="billing-copy"></p>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.7rem">
        <button type="button" class="primary" data-pay="campaign_launch">Pay campaign launch</button>
        <button type="button" class="ghost" data-pay="credit_pack">Credit pack</button>
        <button type="button" class="ghost" data-subscribe>Subscribe Autonomous</button>
      </div>
    </article>`;
  },
};

function pageId() {
  const raw = (location.hash || "#overview").slice(1);
  return NAV.some(([id]) => id === raw) ? raw : "overview";
}

function render() {
  const id = pageId();
  document.getElementById("title").textContent = NAV.find(([k]) => k === id)[1];
  document.getElementById("sub").textContent = SUB[id];
  document.getElementById("workspace").innerHTML = PAGES[id]();
  document.querySelectorAll("#nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.id === id);
  });
  wire(id);
}

function wire(id) {
  document.querySelectorAll("[data-launch]").forEach((b) => {
    b.addEventListener("click", async () => {
      const el = document.getElementById("launch-status");
      if (el) el.textContent = "Launching video-campaign agent…";
      const fields = {};
      ["niche", "goal", "brief", "platforms", "budget", "freq"].forEach((id) => {
        const input = document.getElementById(id);
        if (input) fields[id] = input.value;
      });
      try {
        const r = await apiFetch("/api/campaigns", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...fields, launch: true, agent: "video-campaign" }),
        });
        const campaign = await r.json();
        sessionStorage.setItem("hermes-active-campaign", campaign.id);
        if (el) el.textContent = `${campaign.status} · ${campaign.id}`;
        const cuts = document.getElementById("active-cuts");
        const poll = async () => {
          const c = await (await fetch(`/api/campaigns/${campaign.id}`)).json();
          if (el) el.textContent = `${c.status} · ${c.mode} · ${c.stage || ""}`;
          if (cuts && c.cuts && c.cuts.length) {
            cuts.innerHTML = c.cuts.map((cut) => `
              <div class="row">
                <div><strong>${cut.title}</strong><div class="hint">${cut.slug} · ${cut.scenes} scenes · ${cut.duration_s}s · ${cut.label || cut.status}</div></div>
              </div>`).join("");
          }
          const stream = document.getElementById("events");
          if (stream && c.events && c.events.length) {
            stream.textContent = c.events.slice(-1)[0].message || "running";
          }
          if (!["completed", "completed_healed", "failed"].includes(c.status)) {
            setTimeout(poll, 700);
          }
        };
        poll();
      } catch (err) {
        if (el) el.textContent = String(err);
      }
    });
  });
  document.querySelectorAll("[data-go]").forEach((b) => {
    b.addEventListener("click", () => { location.hash = b.dataset.go; });
  });
  const dry = document.getElementById("dry-run");
  if (dry) {
    dry.addEventListener("click", async () => {
      const stream = document.getElementById("events");
      if (stream) stream.textContent = "Launching labeled dry-run orchestra…";
      try {
        const r = await apiFetch("/api/campaigns", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            niche: "AI education",
            goal: "Grow subscribers",
            brief: "Labeled dry-run video campaign from Orchestra.",
            launch: true,
            agent: "video-campaign",
          }),
        });
        const campaign = await r.json();
        if (stream) stream.textContent = `${campaign.status || r.status} · ${campaign.id || ""}`;
        if (campaign.id) sessionStorage.setItem("hermes-active-campaign", campaign.id);
      } catch (err) {
        if (stream) stream.textContent = String(err);
      }
    });
  }
  const probe = document.getElementById("probe");
  if (probe) {
    probe.addEventListener("click", runProbe);
  }
  const refresh = document.getElementById("refresh-health");
  if (refresh) refresh.addEventListener("click", runProbe);
  if (id === "command") loadHealth();
  if (id === "settings") paintApiKeyStatus();
  if (id === "settings" || id === "overview" || id === "evolution") loadBilling();
  if (id === "overview" || id === "evolution") loadFlywheel();
  if (id === "overview" || id === "discovery" || id === "knowledge") loadKnowledge();
  loadAgent(id);
  bindBilling();
  bindSettings();
  bindResearch();
  bindWalking();
  const fwStart = document.getElementById("flywheel-start");
  if (fwStart) fwStart.addEventListener("click", async () => {
    await apiFetch("/api/flywheel/start", { method: "POST" });
    loadFlywheel();
  });
  const fwStop = document.getElementById("flywheel-stop");
  if (fwStop) fwStop.addEventListener("click", async () => {
    await apiFetch("/api/flywheel/stop", { method: "POST" });
    loadFlywheel();
  });
}

function loadAgent(id) {
  const el = document.getElementById("agent-feed");
  fetch(`/api/agents/${id}`)
    .then((r) => r.json())
    .then((d) => {
      const row = d.result || {};
      const line = `${d.title || id} · ${row.label || row.mode || "idle"} · ${row.summary || d.goal || ""}`;
      if (el) el.textContent = line;
      const stream = document.getElementById("events");
      if (id === "orchestra" && stream && (d.events || []).length) {
        stream.textContent = d.events.slice(-1)[0].message || line;
      }
    })
    .catch((e) => { if (el) el.textContent = String(e); });
}

function paintApiKeyStatus() {
  const el = document.getElementById("api-key-status");
  if (!el) return;
  el.textContent = getApiKey()
    ? "Key in sessionStorage (this tab only). Bearer sent on mutating / locked fetches."
    : "No key stored. GET /health and console remain public.";
}

function bindSettings() {
  const form = document.getElementById("api-key-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = document.getElementById("api-key-input");
      setApiKey(input && input.value);
      if (input) input.value = "";
      paintApiKeyStatus();
    });
  }
  const clear = document.getElementById("api-key-clear");
  if (clear) {
    clear.addEventListener("click", () => {
      setApiKey("");
      const input = document.getElementById("api-key-input");
      if (input) input.value = "";
      paintApiKeyStatus();
    });
  }
}

function bindResearch() {
  document.querySelectorAll("[data-research]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const topic = btn.getAttribute("data-research") || btn.textContent.trim();
      const status = document.getElementById("research-status");
      if (status) status.textContent = `POST /api/agent/research · ${topic}…`;
      try {
        const r = await apiFetch("/api/agent/research", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ topic }),
        });
        const data = await r.json();
        if (status) {
          status.textContent = r.ok
            ? `Researched ${data.topic || topic} · ${data.trend || r.status}`
            : `Research ${r.status}`;
        }
        loadKnowledge();
      } catch (e) {
        if (status) status.textContent = String(e);
      }
    });
  });
}

function loadKnowledge() {
  fetch("/api/knowledge/nodes")
    .then((r) => r.json())
    .then((d) => {
      const nodes = d.nodes || [];
      const count = d.count != null ? d.count : nodes.length;
      const sources = new Set(nodes.map((n) => n.source).filter(Boolean));
      document.querySelectorAll("#kg-node-count").forEach((el) => { el.textContent = String(count); });
      const rel = document.getElementById("kg-rel-count");
      if (rel) rel.textContent = String(sources.size);
      const loops = document.getElementById("kg-loops");
      if (loops) loops.textContent = count ? "Active" : "Idle";
      const trending = document.getElementById("disc-trending");
      if (trending) trending.textContent = String(count);
      const emerging = document.getElementById("disc-emerging");
      if (emerging) emerging.textContent = String(nodes.filter((n) => n.source === "research").length);
      const open = document.getElementById("disc-open");
      if (open) open.textContent = String(nodes.filter((n) => /low|open|white/i.test(String(n.trend || ""))).length);
      const viral = document.getElementById("disc-viral");
      if (viral) viral.textContent = count ? String(Math.min(0.99, 0.5 + count * 0.04).toFixed(2)) : "—";
      const list = document.getElementById("discovery-nodes");
      if (list) {
        if (!nodes.length) {
          list.innerHTML = `<p class="hint">No stored nodes yet. POST /api/agent/research to upsert one.</p>`;
        } else {
          list.innerHTML = nodes.map((n) => `
            <div class="row">
              <div>
                <strong>${n.topic}</strong>
                <div class="hint">${n.trend || ""}</div>
              </div>
              <div class="hint">${n.updated_at || ""}</div>
            </div>`).join("");
        }
      }
      const pills = document.getElementById("kg-nodes");
      if (pills) {
        pills.innerHTML = nodes.length
          ? nodes.map((n) => `<span class="pill">${n.topic}</span>`).join("")
          : `<span class="pill">Empty</span>`;
      }
    })
    .catch((e) => {
      const list = document.getElementById("discovery-nodes");
      if (list) list.textContent = String(e);
    });
}

function loadFlywheel() {
  const el = document.getElementById("flywheel-status");
  fetch("/api/flywheel")
    .then((r) => r.json())
    .then((d) => {
      if (el) {
        el.textContent = `${d.cycle_count || 0} cycles · ${d.running ? "running" : "stopped"} · ${d.origin}${d.last_self_check && d.last_self_check.inference_down ? " · DRY-RUN" : ""}`;
      }
      document.querySelectorAll("#flywheel-cycles").forEach((n) => {
        n.textContent = String(d.cycle_count || 0);
      });
    })
    .catch((e) => { if (el) el.textContent = String(e); });
}

function loadBilling() {
  const el = document.getElementById("billing-status");
  const copy = document.getElementById("billing-copy");
  if (!el && !copy) return;
  fetch("/api/billing/config")
    .then((r) => r.json())
    .then((d) => {
      const skus = (d.products || []).map((p) => p.sku).join(", ");
      const live = Boolean(d.configured) && d.test_mode === false;
      if (el) {
        if (live) el.innerHTML = `Stripe <strong>live</strong> · ${skus}`;
        else if (d.configured) el.textContent = `Stripe test · ${skus}`;
        else el.textContent = d.hint || "Set STRIPE_SECRET_KEY (sk_test_… or sk_live_…).";
      }
      if (copy) {
        copy.textContent = live
          ? "Checkout is live (not test_mode)."
          : d.configured
            ? "Stripe Checkout is in test mode (sk_test_)."
            : "Checkout waits until a secret key is configured.";
      }
    })
    .catch((e) => { if (el) el.textContent = String(e); });
}

function bindWalking() {
  const form = document.getElementById("walk-form");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("walk-status");
    const scriptEl = document.getElementById("walk-script");
    const scenesEl = document.getElementById("walk-scenes");
    const img = document.getElementById("walk-thumb");
    const topic = (document.getElementById("walk-topic") || {}).value || "AI";
    const audience = (document.getElementById("walk-audience") || {}).value || "";
    const fail = (step, r, body) => {
      const detail = body.detail || body.error || JSON.stringify(body);
      if (status) status.textContent = `${step} ${r.status} · ${detail}`;
    };
    try {
      if (status) status.textContent = "POST /api/v1/scripts…";
      const scriptRes = await apiFetch("/api/v1/scripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, audience }),
      });
      const script = await scriptRes.json().catch(() => ({}));
      if (!scriptRes.ok) return fail("scripts", scriptRes, script);
      if (scriptEl) {
        scriptEl.hidden = false;
        scriptEl.textContent = script.script || "";
      }
      if (status) status.textContent = `script ${script.script_id} · POST /api/v1/storyboards…`;
      const boardRes = await apiFetch("/api/v1/storyboards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script_id: script.script_id }),
      });
      const board = await boardRes.json().catch(() => ({}));
      if (!boardRes.ok) return fail("storyboards", boardRes, board);
      if (scenesEl) {
        const scenes = board.scenes || [];
        scenesEl.innerHTML = scenes.map((s) => `
          <div class="row">
            <div><strong>${s.title || `Scene ${s.index}`}</strong><div class="hint">${s.visual || ""} · ${s.duration_s || 6}s</div></div>
          </div>`).join("");
      }
      if (status) status.textContent = `storyboard ${board.storyboard_id} · POST /api/v1/thumbnails…`;
      const thumbRes = await apiFetch("/api/v1/thumbnails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          script_id: script.script_id,
          storyboard_id: board.storyboard_id,
        }),
      });
      const thumb = await thumbRes.json().catch(() => ({}));
      if (!thumbRes.ok) return fail("thumbnails", thumbRes, thumb);
      const url = thumb.thumbnail_url || WALK_PLACEHOLDER;
      if (img) img.src = url;
      if (status) status.textContent = `thumbnail_url ${url}`;
    } catch (err) {
      if (status) status.textContent = String(err);
    }
  });
}

function bindBilling() {
  document.querySelectorAll("[data-pay]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sku = btn.getAttribute("data-pay");
      const r = await apiFetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku }),
      });
      const data = await r.json();
      if (data.url) window.location.href = data.url;
      else {
        const el = document.getElementById("billing-status") || document.getElementById("launch-status");
        if (el) el.textContent = data.hint || data.error || JSON.stringify(data);
      }
    });
  });
  document.querySelectorAll("[data-subscribe]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const r = await apiFetch("/api/billing/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const data = await r.json();
      if (data.url) window.location.href = data.url;
      else {
        const el = document.getElementById("billing-status");
        if (el) el.textContent = data.hint || data.error || JSON.stringify(data);
      }
    });
  });
}

function runProbe() {
  const out = document.getElementById("probe-out");
  const key = getApiKey();
  if (out) out.textContent = key ? "Calling /v1/chat/completions…" : "Calling /health…";
  const req = key
    ? apiFetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: "ping" }], max_tokens: 8 }),
      })
    : fetch("/health");
  req
    .then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }))
    .then((d) => {
      if (out) out.textContent = JSON.stringify(d, null, 2);
    })
    .catch((e) => {
      if (out) out.textContent = String(e);
    });
}

function loadHealth() {
  async function paint(elId, path) {
    const el = document.getElementById(elId);
    if (!el) return;
    try {
      const r = await fetch(path);
      const body = await r.json().catch(async () => await r.text());
      el.textContent = typeof body === "string"
        ? `${path} ${r.status}\n${body}`
        : JSON.stringify({ path, status: r.status, ...body }, null, 2);
    } catch (e) {
      el.textContent = `${path} ${String(e)}`;
    }
  }
  paint("readyz-pre", "/readyz");
  paint("cmd-health", "/health");
}

function buildNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = NAV.map(
    ([id, label]) => `<a href="#${id}" data-id="${id}">${label}</a>`
  ).join("");
}

function openCmd() {
  const dlg = document.getElementById("cmd-dialog");
  const list = document.getElementById("cmd-list");
  const input = document.getElementById("cmd-input");
  list.innerHTML = NAV.map(
    ([id, label]) => `<li><button type="button" data-go="${id}">${label}</button></li>`
  ).join("");
  list.querySelectorAll("button").forEach((b) => {
    b.addEventListener("click", () => {
      location.hash = b.dataset.go;
      dlg.close();
    });
  });
  dlg.showModal();
  input.value = "";
  input.focus();
  input.oninput = () => {
    const q = input.value.toLowerCase();
    list.querySelectorAll("li").forEach((li) => {
      li.hidden = !li.textContent.toLowerCase().includes(q);
    });
  };
}

document.getElementById("cmd-btn").addEventListener("click", openCmd);
document.getElementById("launch-btn").addEventListener("click", () => {
  location.hash = "campaigns";
});
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openCmd();
  }
});
window.addEventListener("hashchange", render);
buildNav();
render();
