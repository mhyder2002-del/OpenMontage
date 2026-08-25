(() => {
  const PAGES = [
    { id: "overview", title: "Overview", sub: "Research · Create · Optimize · Scale" },
    { id: "discovery", title: "Discovery", sub: "Cross-platform opportunity intelligence" },
    { id: "knowledge", title: "Knowledge Graph", sub: "Living memory of what works" },
    { id: "campaigns", title: "Campaigns", sub: "Launch autonomous media campaigns" },
    { id: "orchestra", title: "Agent Orchestra", sub: "Live organization event stream" },
    { id: "debugger", title: "AI Debugger", sub: "Replayable inferences · cost · latency" },
    { id: "studio", title: "Studio", sub: "Compose scenes, hooks, and cuts" },
    { id: "evolution", title: "Evolution Lab", sub: "Crown winners. Retire losers." },
    { id: "analytics", title: "Analytics", sub: "Retention, RPM, and forecast" },
    { id: "memory", title: "Memory", sub: "Causal lessons from every publish" },
    { id: "command", title: "Command Center", sub: "Runtime, keys, and gateway health" },
    { id: "publishing", title: "Publishing", sub: "Queue across YouTube, TikTok, Reels" },
    { id: "uploads", title: "Uploads", sub: "Source footage, stills, and brand kits" },
    { id: "settings", title: "Settings", sub: "Studio identity and OpenAI-compatible /v1" },
  ];

  const main = document.getElementById("main");
  const titleEl = document.getElementById("page-title");
  const subEl = document.getElementById("page-sub");
  const splash = document.getElementById("splash");
  const app = document.getElementById("app");
  const outro = document.getElementById("outro");
  const palette = document.getElementById("palette");
  const cmdInput = document.getElementById("cmd-input");
  const cmdList = document.getElementById("cmd-list");
  const sidebar = document.getElementById("sidebar");
  let loopStep = "Improve";
  let launchMsg = "";
  let probeMsg = "No inferences yet — run a probe or campaign.";
  let inferences = 0;
  let pollTimer = 0;
  const CAMPAIGN_KEY = "hermes-active-campaign";
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

  function lockedHost() {
    const h = (location.hostname || "").toLowerCase();
    return h.endsWith("hermestudios.com") || h.endsWith("hermestudios.online") || h.endsWith("hermestudios.org");
  }

  function mutatingNeedsBearer() {
    return lockedHost() && !getApiKey();
  }

  function disableControl(el, reason) {
    if (!el || el.tagName === "A") return;
    el.disabled = true;
    el.setAttribute("title", reason);
  }

  function gateMutating() {
    if (!mutatingNeedsBearer()) return;
    const reason = "Needs Bearer HERMES_API_KEY in Settings (production host)";
    ["#walk-run", "#flywheel-start", "#flywheel-stop", "#agents-tick", "#dry-run"].forEach((sel) => {
      disableControl(document.querySelector(sel), reason);
    });
    document.querySelectorAll("#campaign-form button[type=submit]").forEach((b) => disableControl(b, reason));
    const header = document.getElementById("launch-campaign");
    if (header) header.setAttribute("title", reason);
    const badge = document.getElementById("auth-badge");
    if (badge) badge.innerHTML = "<i aria-hidden=\"true\"></i> Needs Bearer";
  }

  function gateStripe() {
    if (window.__stripeConfigured) return;
    document.querySelectorAll("[data-pay], [data-subscribe]").forEach((b) => {
      disableControl(b, "Stripe not configured");
    });
  }

  function setChip(id, text, ok) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("ok", !!ok);
    el.classList.toggle("warn", !ok);
  }

  async function loadLiveStrip() {
    try {
      const rz = await fetch("/readyz");
      const body = await rz.json().catch(() => ({}));
      setChip("pill-readyz", "/readyz " + rz.status, rz.ok && body.ok);
    } catch {
      setChip("pill-readyz", "readyz down", false);
    }
    try {
      const h = await fetch("/health");
      const data = await h.json();
      const inf = (data.inference || data.lm_studio || {});
      setChip("pill-health", inf.reachable ? "lm_studio" : "inference down", h.ok && inf.reachable);
    } catch {
      setChip("pill-health", "health down", false);
    }
    try {
      const f = await fetch("/api/flywheel");
      const data = await f.json();
      setChip(
        "pill-flywheel",
        "flywheel " + (data.running ? "running" : "stopped") + " · " + (data.label || data.tick_total || data.cycle_count || 0),
        f.ok && !data.inference_down
      );
    } catch {
      setChip("pill-flywheel", "flywheel n/a", false);
    }
    const badge = document.getElementById("auth-badge");
    if (badge && !mutatingNeedsBearer()) {
      badge.innerHTML = getApiKey()
        ? "<i aria-hidden=\"true\"></i> Bearer session"
        : "<i aria-hidden=\"true\"></i> Public GET";
    }
  }

  let analyticsTimer = 0;
  let kgSim = null;

  const WALK_PLACEHOLDER = "/static/placeholders/walking-skeleton.svg";
  const dash = (v) => (v == null || v === "" ? "—" : String(v));
  const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function metric(label, value, hint, accent) {
    return `<article class="card${accent ? " accent" : ""}"><span class="lbl">${label}</span><div class="val${accent ? " green" : ""}">${value}</div><div class="hint">${hint}</div></article>`;
  }

  function walkPanelHtml() {
    return `
        <section class="card" style="margin-top:0.75rem" id="walk-panel">
          <h2>Campaigns / Studio · walking skeleton</h2>
          <p class="muted">POST /api/v1/scripts → /api/v1/storyboards → /api/v1/thumbnails. Save a Bearer key under Settings first.</p>
          <form class="form" id="walk-form" style="margin-top:0.8rem">
            <label>Topic <input id="walk-topic" name="topic" value="AI education" autocomplete="off" /></label>
            <label>Audience <input id="walk-audience" name="audience" value="founders" autocomplete="off" /></label>
            <button class="btn primary" type="submit" id="walk-run">Generate script → storyboard → thumbnail</button>
          </form>
          <p class="muted" id="walk-status" style="margin-top:0.6rem">Ready. Thumbnail shows ${WALK_PLACEHOLDER} until the chain returns thumbnail_url.</p>
          <pre class="status" id="walk-script" style="margin-top:0.7rem;white-space:pre-wrap" hidden></pre>
          <div id="walk-scenes"></div>
          <img id="walk-thumb" alt="Walking skeleton thumbnail" src="${WALK_PLACEHOLDER}" width="320" height="180" style="display:block;margin-top:0.85rem;max-width:min(100%,20rem);border-radius:0.55rem;border:1px solid var(--line,#26262e);background:#08080c" />
        </section>`;
  }

  function views() {
    return {
      overview: `
        <section class="os-hero card">
          <h2 class="section-h" style="margin:0 0 0.75rem">Product walkthrough</h2>
          <video
            class="os-hero-video"
            src="/static/media/hermes-os.mp4"
            muted
            loop
            playsinline
            autoplay
            controls
            preload="metadata"
          ></video>
          <p class="muted" style="margin:0.7rem 0 0">Muted autoplay — use controls if you want sound.</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2 class="section-h" style="margin:0 0 0.6rem">Plans</h2>
          <p class="muted" id="billing-copy">Checkout mode comes from GET /api/billing/config (live when configured and not test_mode).</p>
          <p class="muted" id="billing-status">Loading Stripe…</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" data-pay="campaign_launch">Pay campaign launch</button>
            <button class="btn" type="button" data-subscribe>Subscribe console</button>
            <a class="btn" href="#/settings">Settings billing</a>
          </div>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("Campaigns", "<span id=\"ov-campaigns\">—</span>", "GET /api/campaigns")}
          ${metric("Engine", "<span id=\"ov-engine\">—</span>", "engine.flywheel_label")}
          ${metric("Inference", "<span id=\"ov-infer\">—</span>", "engine.inference_down")}
          ${metric("Knowledge", "<span id=\"kg-node-count\">—</span>", "GET /api/knowledge/nodes")}
          ${metric("Flywheel ticks", "<span id=\"flywheel-cycles\">—</span>", "GET /api/flywheel", true)}
          ${metric("Agents", "<span id=\"ov-agents\">—</span>", "GET /api/agents")}
          ${metric("Revenue", "—", "No live billing analytics")}
          ${metric("Views / CTR / RPM", "—", "Engine telemetry only")}
        </div>
        <p class="muted" id="agent-feed" style="margin-top:0.75rem">Loading /api/agents/overview…</p>
        <div class="grid split" style="margin-top:0.75rem">
          <section class="card">
            <h2 class="section-h" style="margin:0 0 0.85rem">Live feed</h2>
            <div class="feed" id="ov-feed"><p class="empty">—</p></div>
          </section>
          <section class="card">
            <h2 class="section-h" style="margin:0 0 0.85rem">Operating loop</h2>
            <div class="loop fly-loop" id="ov-loop" role="tablist">${["Discover","Create","Publish","Learn"].map((s) => `<button type="button" data-loop="${s}" class="${s===loopStep?"on":""}">${s}</button>`).join("")}</div>
            <p class="muted" id="flywheel-status" style="margin:0.9rem 0 0">Loading /api/flywheel…</p>
          </section>
        </div>`,
      discovery: `
        <p class="muted" id="agent-feed">Loading /api/agents/discovery…</p>
        <section class="card">
          <h2>AI opportunity scan</h2>
          <div class="chips" id="discovery-sources"></div>
          <p class="muted" id="research-status">GET /api/discovery sources · chip a source to POST /api/agent/research. Scan pulls unpaid YouTube Atom + Reddit JSON + News RSS (TikTok stand-in).</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" id="discovery-scan">Scan live feeds</button>
          </div>
          <div class="chips" id="discovery-topic-chips" style="margin-top:0.7rem"></div>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("Trending", "<span id=\"disc-trending\">—</span>", "Stored nodes")}
          ${metric("Emerging", "<span id=\"disc-emerging\">—</span>", "Research source")}
          ${metric("Low Competition", "<span id=\"disc-open\">—</span>", "Whitespace")}
          ${metric("Opportunities", "<span id=\"disc-viral\">—</span>", "GET /api/discovery", true)}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>High-opportunity topics</h2>
          <div id="discovery-nodes"><p class="muted">Loading GET /api/discovery opportunities…</p></div>
        </section>`
      knowledge: `
        <p class="muted" id="agent-feed">Loading /api/agents/knowledge…</p>
        <div class="grid metrics-3">
          ${metric("Nodes", "<span id=\"kg-node-count\">—</span>", "GET /api/knowledge/nodes")}
          ${metric("Relations", "<span id=\"kg-rel-count\">—</span>", "Distinct sources")}
          ${metric("Feedback Loops", "<span id=\"kg-loops\">—</span>", "Analytics → Memory", true)}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>Living knowledge graph</h2>
          <div class="kg-wrap">
            <svg id="kg-svg" class="kg-svg" role="img" aria-label="Knowledge graph"></svg>
            <div class="kg-tooltip" id="kg-tooltip" hidden></div>
          </div>
          <p class="muted" id="kg-empty">GET /api/knowledge/graph (nodes fallback if 404). Drag nodes · hover for trend.</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Stored nodes</h2>
          <div class="chips" id="kg-nodes"><span class="chip">Loading…</span></div>
        </section>`,
      campaigns: `
        <p class="muted" id="agent-feed">Loading /api/agents/campaigns…</p>
        <div class="grid split">
          <section class="card">
            <h2>Campaign builder</h2>
            <form class="form" id="campaign-form">
              <label>Niche <input name="niche" value="AI education" autocomplete="off" /></label>
              <label>Goal <input name="goal" value="Grow subscribers" autocomplete="off" /></label>
              <label>Brief <textarea name="brief" rows="3" placeholder="Angle, promise, CTA…">Vertical shorts that teach one AI workflow per cut.</textarea></label>
              <label>Platforms <input name="platforms" value="YouTube Shorts, TikTok, Reels" autocomplete="off" /></label>
              <label>Budget <input name="budget" value="$2,000 / mo" autocomplete="off" /></label>
              <label>Frequency <input name="freq" value="2 / day" autocomplete="off" /></label>
              <button class="btn primary" type="submit">Launch campaign</button>
              <button class="btn" type="button" data-pay="campaign_launch">Pay launch pack</button>
              <div class="toast" id="launch-toast" aria-live="polite">${launchMsg}</div>
            </form>
          </section>
          <section class="card">
            <h2>Active cuts</h2>
            <div id="active-cuts"><p class="empty">Launch a campaign to plan cuts.</p></div>
            <h2 style="margin-top:1rem">Campaigns</h2>
            <div id="active-campaigns"><p class="empty">Loading campaigns…</p></div>
          </section>
        </div>
        ${walkPanelHtml()}`,
      orchestra: `
        <section class="card">
          <h2>Agent orchestra</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/orchestra…</p>
          <div class="actions" style="margin-top:0.6rem">
            <button class="btn primary" type="button" id="agents-tick">Tick 14 category agents</button>
          </div>
          <div class="chips" id="orch-health-chips" style="margin-top:0.6rem">
            <span class="chip">inference…</span>
            <span class="chip">MPT…</span>
          </div>
          <p class="muted" id="tick-label" style="margin-top:0.45rem"></p>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("CEO", "Hermes OS Orchestrator", "Orchestrator")}
          ${metric("Workforce", "<span id=\"orch-count\">—</span>", "GET /api/orchestra/pipeline")}
          ${metric("Healthy", "<span id=\"orch-healthy\">—</span>", "LM Studio")}
          ${metric("Jobs", "<span id=\"orch-platform\">—</span>", "GET /api/jobs")}
        </div>
        <section class="card" style="margin-top:0.75rem"><h2>Workforce · 8 agents</h2><div class="orch-grid" id="orch-grid"><p class="empty">Loading GET /api/orchestra/pipeline…</p></div></section>
        <section class="card" style="margin-top:0.75rem"><h2>Jobs</h2><div id="job-list"><p class="empty">Loading GET /api/jobs…</p></div></section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Live event stream</h2>
          <div class="feed" id="event-stream"><p class="empty">Waiting for workflow events…</p></div>
          <div class="actions" style="margin-top:0.8rem">
            <button class="btn primary" type="button" id="dry-run">Run dry-run campaign</button>
            <a class="btn" href="#/debugger">AI Debugger</a>
            <a class="btn" href="#/command">Command Center · 14 categories</a>
          </div>
        </section>`
      debugger: `
        <section class="card">
          <h2>Debugger agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/debugger…</p>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("Inferences", String(inferences), "Recorded")}
          ${metric("Total Cost", "$0.0000", "USD")}
          ${metric("Avg Latency", inferences ? "42ms" : "0ms", "p50-ish avg")}
          ${metric("Fallback Rate", "0", "Provider failover")}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>Probe inference</h2>
          <div class="actions" style="margin-top:0.6rem">
            <button class="btn primary" type="button" id="probe">Run debugger probe</button>
            <button class="btn" type="button" id="refresh-probe">Refresh</button>
          </div>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Recent inferences</h2>
          <p class="empty" id="probe-empty">${probeMsg}</p>
          <div class="feed" id="debug-events"></div>
        </section>`,
      studio: `
        <section class="card">
          <h2>Studio agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/studio…</p>
        </section>
        ${walkPanelHtml()}
        <section class="card" style="margin-top:0.75rem">
          <h2>Walking timeline</h2>
          <p class="muted">Scenes come from the walking skeleton chain — not a fake 7-scene list.</p>
          <div class="studio-timeline" id="studio-timeline"><p class="empty">Run the walking skeleton to fill beats.</p></div>
          <div class="actions" style="margin-top:0.8rem">
            <a class="btn primary" href="#/campaigns">Plan cuts in Campaigns</a>
            <a class="btn" href="#/publishing">Publishing queue</a>
          </div>
        </section>`,
      evolution: `
        <p class="muted" id="agent-feed">Loading /api/agents/evolution…</p>
        <div class="grid metrics-3">
          ${metric("Flywheel cycles", "<span id=\"flywheel-cycles\">—</span>", "Completed ticks", true)}
          ${metric("Promoted", "<span id=\"evo-done\">—</span>", "variants")}
          ${metric("Archived", "<span id=\"evo-healed\">—</span>", "variants")}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>Perpetual flywheel</h2>
          <div class="loop fly-loop" id="evo-loop">${["Discover","Create","Publish","Learn"].map((s) => `<span class="chip" data-fly="${s}">${s}</span>`).join("")}</div>
          <p class="muted" id="flywheel-status">Loading /api/flywheel…</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" id="flywheel-start">Start flywheel</button>
            <button class="btn" type="button" id="flywheel-stop">Stop</button>
          </div>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Evolution board</h2>
          <p class="muted" id="evo-status">GET /api/evolution experiments · promote / archive.</p>
          <div id="evo-list"></div>
        </section>`
      analytics: `
        <p class="muted" id="agent-feed">Loading /api/agents/analytics…</p>
        <div class="grid metrics">
          ${metric("Tick total", "<span id=\"an-ticks\">—</span>", "flywheel / analytics")}
          ${metric("Campaigns", "<span id=\"an-campaigns\">—</span>", "by label")}
          ${metric("Knowledge", "<span id=\"an-kg\">—</span>", "node count")}
          ${metric("Research", "<span id=\"an-research\">—</span>", "live vs DRY-RUN", true)}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2 id="an-headline">Compounding</h2>
          <div id="an-cards" class="grid metrics-3"></div>
          <svg id="analytics-svg" class="analytics-svg" role="img" aria-label="Analytics bars"></svg>
          <p class="muted" id="an-status">Polling GET /api/analytics ~10s while this hash is open.</p>
        </section>`,
      memory: `
        <section class="card">
          <h2>Memory agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/memory…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Learned</h2>
          <p class="muted" id="mem-status">GET /api/memory</p>
          <div id="mem-list"><p class="empty">Loading GET /api/memory…</p></div>
        </section>`,
      command: `
        <p class="muted" id="agent-feed">Loading /api/agents/command…</p>
        <div class="chips" id="runtime-chips" style="margin:0 0 0.75rem">
          <span class="chip">livez…</span>
        </div>
        <section class="card">
          <h2>/readyz</h2>
          <pre class="status" id="readyz-pre">checking…</pre>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>/health</h2>
          <pre class="status" id="health-pre">checking…</pre>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Ops</h2>
          <p class="muted">/livez process up · /readyz production key present · /health inference + models · /docs OpenAPI. GET /health and /console stay public without a key.</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" id="refresh-runtime">Refresh runtime</button>
            <a class="btn" href="/docs">Open /docs</a>
            <a class="btn" href="/livez">Open /livez</a>
          </div>
        </section>`,
      publishing: `
        <section class="card">
          <h2>Publishing agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/publishing…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Publish queue</h2>
          <p class="muted">Live rows from GET /api/jobs (stage publish or kind publishing). No fake 14-item list.</p>
          <div id="pub-queue"><p class="muted">Loading /api/jobs…</p></div>
        </section>`,
      uploads: `
        <section class="card">
          <h2>Uploads agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/uploads…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Drop zone</h2>
          <p class="muted">Brand kits, stills, and source clips land here before Studio. Binary YouTube upload stays on the studio Mac CLI — this control is disabled on purpose.</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn" type="button" id="upload-stub" disabled title="Binary upload stays on the studio Mac CLI">Upload file</button>
            <a class="btn" href="#/studio">Open Studio</a>
          </div>
        </section>`,
      settings: `
        <section class="card">
          <h2>Settings agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/settings…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>API key</h2>
          <p class="muted">Stored in <code>sessionStorage</code> only (<code>hermes-api-key</code>). Sent as <code>Authorization: Bearer</code> on mutating and locked <code>/v1</code> requests. GET /health and the console stay usable with no key.</p>
          <form class="form" id="api-key-form" style="margin-top:0.8rem">
            <label>HERMES_API_KEY <input id="api-key-input" name="apiKey" type="password" autocomplete="off" placeholder="Paste key for this tab" /></label>
            <div class="actions">
              <button class="btn primary" type="submit">Save for this session</button>
              <button class="btn" type="button" id="api-key-clear">Clear</button>
            </div>
            <p class="muted" id="api-key-status"></p>
          </form>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Public door</h2>
          <p class="muted">This host is the locked gateway for Hermes Studios: OpenAI-compatible <code>/v1</code>, health, and OpenMontage delivery.</p>
          <pre class="status" style="margin-top:0.8rem">export OPENAI_BASE_URL=https://hermestudios.com/v1
export OPENAI_API_KEY=$HERMES_API_KEY</pre>
        </section>
        <section class="card" style="margin-top:0.75rem" id="billing-panel">
          <h2>Billing</h2>
          <p class="muted" id="billing-status">Loading Stripe catalog…</p>
          <p class="muted" id="billing-copy"></p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" data-pay="campaign_launch">Pay campaign launch</button>
            <button class="btn" type="button" data-pay="credit_pack">Buy credit pack</button>
            <button class="btn" type="button" data-subscribe>Subscribe Autonomous v0.4.0</button>
          </div>
        </section>
        <p class="muted" style="margin:1rem 0 0"><a href="#/outro">End card</a> · <a href="/docs">/docs</a> · <a href="/health">/health</a> · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/refunds">Refunds</a></p>`,
    };
  }

  function currentId() {
    const hash = (location.hash || "#/overview").replace("#/", "");
    if (hash === "outro") return "outro";
    return PAGES.some((p) => p.id === hash) ? hash : "overview";
  }

  function enterConsole() {
    document.documentElement.classList.add("entered");
    document.documentElement.classList.remove("outro-mode");
    splash.classList.add("closing");
    splash.style.display = "none";
    outro.classList.remove("show");
    app.classList.add("show");
    if (!location.hash || location.hash === "#/" || location.hash === "#/splash") {
      location.hash = "#/overview";
    }
    render();
  }

  function showOutro() {
    document.documentElement.classList.remove("entered");
    document.documentElement.classList.add("outro-mode");
    app.classList.remove("show");
    splash.style.display = "none";
    outro.classList.add("show");
  }

  function render() {
    const id = currentId();
    if (id === "outro") {
      showOutro();
      return;
    }
    outro.classList.remove("show");
    if (splash.style.display !== "none" && !sessionStorage.getItem("hermes-entered")) {
      return;
    }
    app.classList.add("show");
    splash.style.display = "none";
    const page = PAGES.find((p) => p.id === id) || PAGES[0];
    titleEl.textContent = page.title;
    subEl.textContent = page.sub;
    main.innerHTML = views()[page.id];
    document.querySelectorAll("nav a").forEach((a) => {
      a.classList.toggle("active", a.getAttribute("href") === `#/${page.id}`);
    });
    document.querySelectorAll(".os-dock a").forEach((a) => {
      a.classList.toggle("active", a.getAttribute("data-dock") === page.id);
    });
    const chromeMeta = document.getElementById("os-chrome-meta");
    if (chromeMeta) chromeMeta.textContent = `#/${page.id}`;
    stopAnalyticsPoll();
    if (kgSim) {
      kgSim.stop();
      kgSim = null;
    }
    if (page.id === "command") loadHealth();
    if (page.id === "settings") paintApiKeyStatus();
    if (page.id === "settings" || page.id === "overview" || page.id === "evolution" || page.id === "campaigns") loadBilling();
    if (page.id === "overview" || page.id === "evolution" || page.id === "debugger") loadFlywheel();
    if (page.id === "overview" || page.id === "discovery" || page.id === "knowledge") loadKnowledge();
    if (page.id === "overview") loadOverviewLive();
    if (page.id === "discovery") loadDiscovery();
    if (page.id === "publishing") loadPublishingQueue();
    if (page.id === "knowledge") loadKnowledgeGraph();
    if (page.id === "orchestra") { loadOrchestra(); loadJobs(); }
    if (page.id === "evolution") loadEvolution();
    if (page.id === "memory") loadMemory();
    if (page.id === "debugger") loadDebuggerFeed();
    if (page.id === "studio") paintStudioTimeline();
    if (page.id === "analytics") startAnalyticsPoll();
    loadAgent(page.id);
    bindPage(page.id);
    bindBilling();
    bindSettings();
    loadLiveStrip();
    gateMutating();
  }

  function eventHtml(events) {
    if (!events || !events.length) return `<p class="empty">Waiting for workflow events…</p>`;
    return events.slice().reverse().map((ev) => {
      const label = ev.label ? ` [${ev.label}]` : "";
      return `<div class="feed-item"><time>${ev.stage || ev.type || ""}</time><strong>${ev.agent || ev.type}</strong><span>${ev.message || ""}${label}</span></div>`;
    }).join("");
  }

  function paintCuts(cuts) {
    const box = document.getElementById("active-cuts");
    if (!box) return;
    if (!cuts || !cuts.length) {
      box.innerHTML = `<p class="empty">No cuts yet. Launch starts the video-campaign agent.</p>`;
      return;
    }
    box.innerHTML = cuts.map((cut) => {
      const meta = `${cut.slug || cut.id} · ${cut.scenes || "?"} scenes · ${cut.duration_s || "?"}s`;
      const st = cut.label || cut.status || "";
      return `<div class="row"><div><h3>${cut.title || "Cut"}</h3><div class="stats">${meta}</div><div class="muted">${cut.hook || ""}</div></div><span class="pill">${st}</span></div>`;
    }).join("");
  }

  function paintCampaigns(items) {
    const box = document.getElementById("active-campaigns");
    if (!box) return;
    if (!items.length) {
      box.innerHTML = `<p class="empty">No campaigns yet. Launch one to start the video agent.</p>`;
      return;
    }
    box.innerHTML = items.map((c) => {
      const mode = c.healed ? "DRY-RUN · healed" : (c.mode || "pending");
      const n = (c.cuts || []).length;
      return `<div class="row"><div><h3>${c.niche}</h3><div class="stats">${c.status} · ${mode} · ${c.stage || "queued"} · ${n} cuts · ${c.agent || "video-campaign"}</div></div><button class="btn" type="button" data-watch="${c.id}">Orchestra</button></div>`;
    }).join("");
    box.querySelectorAll("[data-watch]").forEach((btn) => {
      btn.addEventListener("click", () => {
        sessionStorage.setItem(CAMPAIGN_KEY, btn.dataset.watch);
        location.hash = "#/orchestra";
      });
    });
  }

  function paintStatus(campaign) {
    if (!campaign) return;
    const healed = campaign.healed ? " · self-healed dry-run" : "";
    launchMsg = `${campaign.status}${healed} · stage ${campaign.stage || "queued"}`;
    const toast = document.getElementById("launch-toast");
    if (toast) toast.textContent = launchMsg;
    const stream = document.getElementById("event-stream");
    if (stream) stream.innerHTML = eventHtml(campaign.events);
    const debug = document.getElementById("debug-events");
    if (debug) debug.innerHTML = eventHtml(campaign.events);
    const empty = document.getElementById("probe-empty");
    if (empty && campaign.events && campaign.events.length) {
      empty.textContent = `${campaign.events.length} orchestra events · ${campaign.status}`;
    }
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = 0;
    }
  }

  async function fetchCampaign(id) {
    const r = await fetch(`/api/campaigns/${id}`);
    if (!r.ok) throw new Error(`campaign ${r.status}`);
    return r.json();
  }

  async function refreshActive() {
    try {
      const list = await (await fetch("/api/campaigns")).json();
      paintCampaigns(list.campaigns || []);
      const id = sessionStorage.getItem(CAMPAIGN_KEY);
      if (id) {
        const campaign = await fetchCampaign(id);
        paintStatus(campaign);
        paintCuts(campaign.cuts || []);
        if (campaign.status === "completed" || campaign.status === "completed_healed" || campaign.status === "failed") {
          stopPoll();
        }
      }
    } catch (err) {
      launchMsg = String(err);
      const toast = document.getElementById("launch-toast");
      if (toast) toast.textContent = launchMsg;
    }
  }

  function startPoll() {
    stopPoll();
    refreshActive();
    pollTimer = setInterval(refreshActive, 700);
  }

  async function launchCampaign(fields) {
    launchMsg = "Launching agent orchestra…";
    const toast = document.getElementById("launch-toast");
    if (toast) toast.textContent = launchMsg;
    const r = await apiFetch("/api/campaigns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...fields, launch: true }),
    });
    if (!r.ok) throw new Error(`launch failed ${r.status}`);
    const campaign = await r.json();
    sessionStorage.setItem(CAMPAIGN_KEY, campaign.id);
    paintStatus(campaign);
    startPoll();
    return campaign;
  }

  function paintBillingUi(data) {
    const el = document.getElementById("billing-status");
    const copy = document.getElementById("billing-copy");
    const skus = (data.products || []).map((p) => p.sku).join(", ");
    const live = Boolean(data.configured) && data.test_mode === false;
    if (el) {
      if (live) {
        el.innerHTML = `Stripe <strong>live</strong> · ${skus}`;
      } else if (data.configured) {
        el.textContent = `Stripe test · ${skus}`;
      } else {
        el.textContent = `Stripe not configured. ${data.hint || "Set STRIPE_SECRET_KEY (sk_test_… or sk_live_…)"}`;
      }
    }
    if (copy) {
      copy.textContent = live
        ? "Checkout is live (not test_mode). Keys stay on the server; this page only reads public /api/billing/config."
        : data.configured
          ? "Stripe Checkout is in test mode (sk_test_)."
          : "One-time campaign packs and Autonomous v0.4.0 sit on Stripe Checkout once a secret key is set.";
    }
  }

  async function loadBilling() {
    const el = document.getElementById("billing-status");
    try {
      const r = await fetch("/api/billing/config");
      const data = await r.json();
      window.__stripeConfigured = Boolean(data.configured);
      paintBillingUi(data);
      gateStripe();
    } catch (err) {
      window.__stripeConfigured = false;
      if (el) el.textContent = String(err);
      gateStripe();
    }
  }

  function bindBilling() {
    document.querySelectorAll("[data-pay]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sku = btn.getAttribute("data-pay");
        try {
          const r = await apiFetch("/api/billing/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sku }),
          });
          const data = await r.json();
          if (data.url) {
            window.location.href = data.url;
            return;
          }
          const toast = document.getElementById("launch-toast") || document.getElementById("billing-status");
          if (toast) toast.textContent = data.hint || data.error || JSON.stringify(data);
        } catch (err) {
          const toast = document.getElementById("billing-status");
          if (toast) toast.textContent = String(err);
        }
      });
    });
    document.querySelectorAll("[data-subscribe]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          const r = await apiFetch("/api/billing/subscribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          const data = await r.json();
          if (data.url) {
            window.location.href = data.url;
            return;
          }
          const toast = document.getElementById("billing-status") || document.getElementById("launch-toast");
          if (toast) toast.textContent = data.hint || data.error || JSON.stringify(data);
        } catch (err) {
          const toast = document.getElementById("billing-status");
          if (toast) toast.textContent = String(err);
        }
      });
    });
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
          scenesEl.innerHTML = scenes.length
            ? scenes.map((s) => `<div class="row"><div><h3>${s.title || `Scene ${s.index}`}</h3><div class="muted">${s.visual || ""} · ${s.duration_s || 6}s</div></div></div>`).join("")
            : "";
          try { sessionStorage.setItem("hermes-walk-scenes", JSON.stringify(scenes)); } catch { /* */ }
          paintStudioTimeline(scenes);
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

  function bindPage(id) {
    document.querySelectorAll("[data-loop]").forEach((btn) => {
      btn.addEventListener("click", () => {
        loopStep = btn.dataset.loop;
        render();
      });
    });
    const form = document.getElementById("campaign-form");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const data = new FormData(form);
        try {
          await launchCampaign({
            niche: data.get("niche"),
            goal: data.get("goal"),
            brief: data.get("brief"),
            platforms: data.get("platforms"),
            budget: data.get("budget"),
            freq: data.get("freq"),
            agent: "video-campaign",
          });
        } catch (err) {
          launchMsg = String(err);
          const toast = document.getElementById("launch-toast");
          if (toast) toast.textContent = launchMsg;
        }
      });
      startPoll();
    }
    if (id === "orchestra" || id === "debugger") startPoll();
    document.getElementById("flywheel-start")?.addEventListener("click", async () => {
      await apiFetch("/api/flywheel/start", { method: "POST" });
      loadFlywheel();
    });
    document.getElementById("flywheel-stop")?.addEventListener("click", async () => {
      await apiFetch("/api/flywheel/stop", { method: "POST" });
      loadFlywheel();
    });
    document.getElementById("probe")?.addEventListener("click", () => runProbe());
    document.getElementById("refresh-probe")?.addEventListener("click", () => {
      refreshActive();
      loadDebuggerFeed();
    });
    document.getElementById("agents-tick")?.addEventListener("click", async () => {
      const el = document.getElementById("agent-feed");
      if (el) el.textContent = "Ticking 14 category agents…";
      try {
        const tickRes = await apiFetch("/api/agents/tick", { method: "POST" });
        const tickJson = await tickRes.json().catch(() => ({}));
        const tickEl = document.getElementById("tick-label");
        if (tickEl) {
          tickEl.textContent = `POST /api/agents/tick ${tickRes.status} · ${dash(tickJson.label || (tickJson.tick && tickJson.tick.label) || tickJson.mode)}`;
        }
        loadAgent("orchestra");
        loadOrchestra();
        loadJobs();
      } catch (err) {
        if (el) el.textContent = String(err);
      }
    });
    bindWalking();
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
              ? `${data.label || data.mode || r.status} · ${data.topic || topic} · ${data.trend || ""}`
              : `Research ${r.status} · ${data.detail || data.error || JSON.stringify(data)}`;
          }
          loadDiscovery();
          loadKnowledge();
        } catch (err) {
          if (status) status.textContent = String(err);
        }
      });
    });
    document.getElementById("refresh-runtime")?.addEventListener("click", () => {
      loadHealth();
      loadLiveStrip();
      loadFlywheel();
    });
    document.getElementById("dry-run")?.addEventListener("click", async () => {
      const stream = document.getElementById("event-stream");
      if (stream) stream.innerHTML = `<p class="empty">Launching labeled dry-run orchestra…</p>`;
      try {
        await launchCampaign({
          niche: "AI education",
          goal: "Grow subscribers",
          brief: "Labeled dry-run video campaign from Orchestra.",
          agent: "video-campaign",
        });
      } catch (err) {
        if (stream) stream.textContent = String(err);
      }
    });
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
    document.getElementById("api-key-clear")?.addEventListener("click", () => {
      setApiKey("");
      const input = document.getElementById("api-key-input");
      if (input) input.value = "";
      paintApiKeyStatus();
    });
  }

  async function runProbe() {
    inferences += 1;
    const empty = document.getElementById("probe-empty");
    const key = getApiKey();
    try {
      if (key) {
        const r = await apiFetch("/v1/chat/completions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [{ role: "user", content: "ping" }],
            max_tokens: 8,
          }),
        });
        const data = await r.json().catch(() => ({}));
        probeMsg = `Probe #${inferences} · POST /v1/chat/completions ${r.status} · ${data.error || data.model || data.object || JSON.stringify(data).slice(0, 180)}`;
      } else {
        const r = await fetch("/health");
        const data = await r.json();
        const inf = data.inference || data;
        probeMsg = `Probe #${inferences} · GET /health (no session key) · backend ${inf.backend || "unknown"} · reachable ${inf.reachable}`;
      }
    } catch (err) {
      probeMsg = `Probe #${inferences} · ${String(err)}`;
    }
    if (empty) empty.textContent = probeMsg;
    refreshActive();
  }

  function paintStudioTimeline(scenes) {
    const box = document.getElementById("studio-timeline");
    if (!box) return;
    let rows = scenes;
    if (!rows) {
      try { rows = JSON.parse(sessionStorage.getItem("hermes-walk-scenes") || "[]"); } catch { rows = []; }
    }
    if (!rows.length) {
      box.innerHTML = `<p class="empty">Run the walking skeleton to fill beats.</p>`;
      return;
    }
    box.innerHTML = rows.map((s, i) => `
      <div class="studio-beat">
        <strong>${s.title || `Scene ${s.index || i + 1}`}</strong>
        <div class="muted">${s.duration_s || 6}s</div>
        <div class="muted">${s.visual || ""}</div>
      </div>`).join("");
  }

  function flyStage(fw) {
    const label = String((fw && (fw.label || (fw.last_tick && fw.last_tick.label))) || "").toLowerCase();
    if (label.includes("discover")) return "Discover";
    if (label.includes("create") || label.includes("campaign") || label.includes("studio")) return "Create";
    if (label.includes("publish")) return "Publish";
    if (label.includes("learn") || label.includes("analy") || label.includes("evol")) return "Learn";
    const n = Number((fw && (fw.tick_total || fw.cycle_count)) || 0);
    return ["Discover", "Create", "Publish", "Learn"][n % 4];
  }

  function paintFlyLoop(fw) {
    const stage = flyStage(fw);
    document.querySelectorAll("#ov-loop [data-loop], #evo-loop [data-fly]").forEach((el) => {
      const name = el.getAttribute("data-loop") || el.getAttribute("data-fly");
      el.classList.toggle("on", name === stage);
    });
  }

  async function loadOverviewLive() {
    const feed = document.getElementById("ov-feed");
    try {
      const [campR, fwR, agR] = await Promise.all([
        fetch("/api/campaigns"),
        fetch("/api/flywheel"),
        fetch("/api/agents"),
      ]);
      const camp = campR.ok ? await campR.json() : { campaigns: [], engine: {} };
      const fw = fwR.ok ? await fwR.json() : {};
      const ag = agR.ok ? await agR.json() : {};
      const items = camp.campaigns || [];
      const engine = camp.engine || {};
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = dash(v); };
      set("ov-campaigns", items.length);
      set("ov-engine", engine.flywheel_label || engine.pipeline);
      set("ov-infer", engine.inference_down ? "down" : "up");
      set("ov-agents", ag.count || (ag.categories || []).length);
      paintFlyLoop(fw);
      const ticks = fw.ticks || [];
      if (feed) {
        if (!ticks.length && !items.length) {
          feed.innerHTML = `<p class="empty">—</p>`;
        } else {
          const rows = ticks.slice(-8).reverse().map((t) => {
            const who = t.stage || t.origin || "flywheel";
            const what = t.label || t.message || JSON.stringify(t).slice(0, 140);
            return `<div class="feed-item"><time>${t.at || t.ts || ""}</time><strong>${who}</strong><span>${what}</span></div>`;
          });
          feed.innerHTML = rows.join("") || `<p class="empty">—</p>`;
        }
      }
    } catch (err) {
      if (feed) feed.innerHTML = `<p class="empty">${String(err)}</p>`;
    }
  }

  function researchChipMode(topic) {
    const blob = JSON.stringify(topic || {}).toLowerCase();
    if (topic && (topic.mode === "live" || topic.label === "live")) return "live";
    if (blob.includes("dry-run") || blob.includes("dry_run")) return "DRY-RUN";
    return topic && (topic.mode || topic.label) || "stored";
  }

  async function loadDiscovery() {
    const chips = document.getElementById("discovery-topic-chips");
    const list = document.getElementById("discovery-nodes");
    const sourcesEl = document.getElementById("discovery-sources");
    try {
      const r = await fetch("/api/discovery");
      const data = r.ok ? await r.json() : { topics: [], opportunities: [], sources: [] };
      const topics = data.topics || [];
      const ops = data.opportunities || [];
      const sources = data.sources || [];
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = dash(v); };
      set("disc-trending", data.count != null ? data.count : topics.length);
      const liveN = topics.filter((t) => researchChipMode(t) === "live").length;
      const dryN = topics.filter((t) => researchChipMode(t) === "DRY-RUN").length;
      set("disc-emerging", liveN);
      set("disc-open", dryN);
      set("disc-viral", data.opportunity_count != null ? data.opportunity_count : ops.length);
      if (sourcesEl) {
        sourcesEl.innerHTML = sources.length
          ? sources.map((s, i) => `<button type="button" class="chip${s.status === "live" || i < 3 ? " on" : ""}" data-research="${s.name}">${s.name} · ${s.status || s.kind}</button>`).join("")
          : ["YouTube","Reddit","TikTok","X","News"].map((c, i) => `<button type="button" class="chip${i<3?" on":""}" data-research="${c}">${c}</button>`).join("");
      }
      if (chips) {
        chips.innerHTML = topics.length
          ? topics.map((t) => {
              const name = t.name || t.topic || "topic";
              const mode = researchChipMode(t);
              return `<button type="button" class="chip" data-research="${name}">${name} · ${mode}</button>`;
            }).join("")
          : `<span class="chip">No stored topics yet</span>`;
        chips.querySelectorAll("[data-research]").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const topic = btn.getAttribute("data-research");
            const status = document.getElementById("research-status");
            if (status) status.textContent = `POST /api/agent/research · ${topic}…`;
            try {
              const res = await apiFetch("/api/agent/research", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ topic }),
              });
              const body = await res.json();
              if (status) status.textContent = `${body.label || body.mode || res.status} · ${body.trend || ""}`;
              loadDiscovery();
              loadKnowledge();
            } catch (e) {
              if (status) status.textContent = String(e);
            }
          });
        });
      }
      if (list) {
        const rows = ops.length ? ops : topics;
        list.innerHTML = rows.length
          ? rows.map((t, i) => {
              const title = t.title || t.name || t.topic;
              const meta = t.source || t.trend || researchChipMode(t);
              const score = t.score != null ? t.score : (t.rank || i + 1);
              return `<div class="row"><div class="min-w"><h3>${String(t.rank || i + 1).toString().padStart(2, "0")} ${title}</h3><div class="stats">${meta}</div></div><span class="pill">${score}</span></div>`;
            }).join("")
          : `<p class="empty">No opportunities yet. Scan live feeds or POST /api/product/bootstrap.</p>`;
      }
      const scanBtn = document.getElementById("discovery-scan");
      if (scanBtn && !scanBtn.dataset.bound) {
        scanBtn.dataset.bound = "1";
        scanBtn.addEventListener("click", async () => {
          const status = document.getElementById("research-status");
          if (status) status.textContent = "POST /api/discovery/scan…";
          try {
            const res = await apiFetch("/api/discovery/scan", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({}),
            });
            const body = await res.json();
            if (status) {
              status.textContent = `${body.mode || res.status} · ${body.live_feeds || 0} feeds · ${body.stored || 0} stored · unpaid`;
            }
            loadDiscovery();
          } catch (e) {
            if (status) status.textContent = String(e);
          }
        });
      }
    } catch (err) {
      if (chips) chips.textContent = String(err);
    }
  }

  async function loadPublishingQueue() {
    const el = document.getElementById("pub-queue");
    if (!el) return;
    try {
      const r = await fetch("/api/jobs");
      const data = r.ok ? await r.json() : { jobs: [] };
      const jobs = (data.jobs || []).filter((j) => {
        const stage = String(j.stage || "").toLowerCase();
        const kind = String(j.kind || "").toLowerCase();
        return stage.includes("publish") || kind.includes("publish");
      });
      el.innerHTML = jobs.length
        ? jobs.map((j) => {
            const title = (j.detail && (j.detail.title || j.detail.topic)) || j.stage || j.kind;
            return `<div class="row"><h3>${title}</h3><span class="pill">${j.status || "queued"}</span></div>`;
          }).join("")
        : `<p class="empty">No publish jobs yet. Launch a campaign; this list is GET /api/jobs, not a mock queue.</p>`;
    } catch (err) {
      el.innerHTML = `<p class="empty">${String(err)}</p>`;
    }
  }

  function drawKnowledgeGraph(graph) {
    const svgEl = document.getElementById("kg-svg");
    if (!svgEl || typeof d3 === "undefined") return;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    const nodesIn = (graph.nodes || []).map((n, i) => ({
      id: String(n.id || n.topic || n.name || i),
      topic: n.topic || n.name || n.id || `n${i}`,
      trend: n.trend || n.rel || "",
    }));
    const empty = document.getElementById("kg-empty");
    if (!nodesIn.length) {
      if (empty) empty.textContent = "Empty graph — POST /api/agent/research to add nodes.";
      return;
    }
    if (empty) empty.textContent = `${nodesIn.length} nodes · ${(graph.links || []).length} links · drag / hover`;
    const width = svgEl.clientWidth || 640;
    const height = svgEl.clientHeight || 352;
    svg.attr("viewBox", [0, 0, width, height]);
    const idSet = new Set(nodesIn.map((n) => n.id));
    const links = (graph.links || graph.edges || [])
      .map((l) => ({
        source: String(l.source || l.src || l.from),
        target: String(l.target || l.dst || l.to),
        rel: l.rel || l.type || "",
      }))
      .filter((l) => idSet.has(l.source) && idSet.has(l.target));
    const tooltip = document.getElementById("kg-tooltip");
    const sim = d3.forceSimulation(nodesIn)
      .force("link", d3.forceLink(links).id((d) => d.id).distance(72))
      .force("charge", d3.forceManyBody().strength(-180))
      .force("center", d3.forceCenter(width / 2, height / 2));
    kgSim = sim;
    const link = svg.append("g").attr("stroke", "#3f3f4a").selectAll("line")
      .data(links).join("line").attr("stroke-width", 1.2);
    const node = svg.append("g").selectAll("circle")
      .data(nodesIn).join("circle")
      .attr("r", 8)
      .attr("fill", "#5ee9a4")
      .attr("stroke", "#0b0b10")
      .call(d3.drag()
        .on("start", (event, d) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on("end", (event, d) => {
          if (!event.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));
    node.on("mouseenter", (event, d) => {
      if (!tooltip) return;
      tooltip.hidden = false;
      tooltip.textContent = `${d.topic}: ${d.trend || "—"}`;
      tooltip.style.left = `${event.offsetX + 12}px`;
      tooltip.style.top = `${event.offsetY + 8}px`;
    }).on("mouseleave", () => { if (tooltip) tooltip.hidden = true; });
    sim.on("tick", () => {
      link.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    });
    if (reduceMotion()) {
      for (let i = 0; i < 80; i++) sim.tick();
      sim.stop();
      link.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    }
  }

  async function loadKnowledgeGraph() {
    let graph = { nodes: [], links: [] };
    try {
      const r = await fetch("/api/knowledge/graph");
      if (r.ok) {
        graph = await r.json();
      } else if (r.status === 404) {
        const n = await (await fetch("/api/knowledge/nodes")).json();
        graph = { nodes: n.nodes || [], links: [] };
      }
    } catch {
      try {
        const n = await (await fetch("/api/knowledge/nodes")).json();
        graph = { nodes: n.nodes || [], links: [] };
      } catch { /* */ }
    }
    drawKnowledgeGraph(graph);
  }

  async function loadOrchestra() {
    const grid = document.getElementById("orch-grid");
    const chips = document.getElementById("orch-health-chips");
    try {
      const [agR, hR, pR] = await Promise.all([
        fetch("/api/agents"),
        fetch("/health"),
        fetch("/api/orchestra/pipeline"),
      ]);
      const ag = agR.ok ? await agR.json() : { categories: [] };
      const health = hR.ok ? await hR.json() : {};
      const pipe = pR.ok ? await pR.json() : {};
      const workforce = pipe.agents || [];
      const cats = ag.categories || [];
      const countEl = document.getElementById("orch-count");
      const healthyEl = document.getElementById("orch-healthy");
      if (countEl) countEl.textContent = dash(workforce.length || pipe.live_count || 8);
      const inf = (health.inference || health.lm_studio || {});
      const infUp = Boolean(inf.reachable);
      if (healthyEl) healthyEl.textContent = infUp ? "lm_studio" : "down";
      const mpt = health.moneyprinter || health.mpt || {};
      if (chips) {
        chips.innerHTML = `
          <span class="chip ${infUp ? "on" : ""}">inference ${infUp ? "lm_studio" : "down"}</span>
          <span class="chip">${pipe.live_count != null ? `${pipe.live_count} live` : "pipeline"}</span>
          <span class="chip">${mpt.enabled != null || mpt.reachable != null || mpt.ok != null
            ? `MPT ${mpt.enabled === false ? "off" : (mpt.reachable || mpt.ok ? "up" : "DRY-RUN")}`
            : "MPT —"}</span>
          <span class="chip">${cats.length} category nav</span>`;
      }
      if (grid) {
        const rows = workforce.length ? workforce : cats;
        grid.innerHTML = rows.length
          ? rows.map((c) => {
              const row = c.result || c;
              const pct = Math.round(Number(c.progress || 0) * 100);
              return `<article class="orch-card"><strong>${c.title || c.key || c.id}</strong><div class="muted">${dash(c.status || row.label || row.mode)}</div><div class="muted">${dash((c.message || row.summary || "").slice(0, 120))}${c.progress != null ? ` · ${pct}%` : ""}</div></article>`;
            }).join("")
          : `<p class="empty">No agents in snapshot.</p>`;
      }
    } catch (err) {
      if (grid) grid.innerHTML = `<p class="empty">${String(err)}</p>`;
    }
  }

  async function loadJobs() {
    const list = document.getElementById("job-list");
    const platEl = document.getElementById("orch-platform");
    try {
      const r = await fetch("/api/jobs");
      const data = r.ok ? await r.json() : { jobs: [] };
      const jobs = data.jobs || [];
      if (platEl) platEl.textContent = dash(data.count != null ? data.count : jobs.length);
      if (list) {
        list.innerHTML = jobs.length
          ? jobs.map((j) => `<div class="row"><div><h3>${j.kind || j.stage || j.id}</h3><div class="stats">${dash(j.status)} · ${dash(j.campaign_id)}</div></div><span class="pill">${Math.round(Number(j.progress || 0) * 100)}%</span></div>`).join("")
          : `<p class="empty">No jobs yet.</p>`;
      }
    } catch (err) {
      if (list) list.innerHTML = `<p class="empty">${String(err)}</p>`;
    }
  }

  async function loadMemory() {
    const list = document.getElementById("mem-list");
    const status = document.getElementById("mem-status");
    try {
      const r = await fetch("/api/memory");
      const data = r.ok ? await r.json() : { items: [] };
      const items = data.items || [];
      if (status) status.textContent = `GET /api/memory · ${dash(data.title || data.count)}`;
      if (list) {
        list.innerHTML = items.length
          ? items.map((m) => `<div class="row"><h3>${m.insight || m.title || m.id}</h3><span class="pill">+${dash(m.lift)}%</span></div>`).join("")
          : `<p class="empty">No learnings yet. POST /api/product/bootstrap seeds memory.</p>`;
      }
    } catch (err) {
      if (list) list.innerHTML = `<p class="empty">${String(err)}</p>`;
    }
  }

  async function loadDebuggerFeed() {
    const debug = document.getElementById("debug-events");
    if (!debug) return;
    try {
      const fw = await (await fetch("/api/flywheel")).json();
      const ticks = fw.ticks || [];
      if (ticks.length) {
        debug.innerHTML = ticks.slice(-12).reverse().map((t) => {
          const msg = t.label || t.message || "";
          return `<div class="feed-item"><time>${t.stage || ""}</time><strong>flywheel</strong><span>${msg}</span></div>`;
        }).join("");
      }
      paintFlyLoop(fw);
    } catch { /* keep campaign poll */ }
  }

  async function loadEvolution() {
    const list = document.getElementById("evo-list");
    const status = document.getElementById("evo-status");
    let data = {};
    try {
      const r = await fetch("/api/evolution");
      if (r.ok) data = await r.json();
      else if (status) status.textContent = `GET /api/evolution ${r.status}`;
    } catch {
      if (status) status.textContent = "GET /api/evolution unavailable";
    }
    const experiments = data.experiments || [];
    const latest = data.latest || experiments[0];
    const variants = (latest && latest.variants) || data.promoted || [];
    const dEl = document.getElementById("evo-done");
    const hEl = document.getElementById("evo-healed");
    if (dEl) dEl.textContent = dash(data.winners_promoted);
    if (hEl) hEl.textContent = dash(data.archived_count);
    if (status) {
      status.textContent = latest
        ? `GET /api/evolution · ${latest.title || latest.id} · ${variants.length} variants`
        : `GET /api/evolution · ${dash(data.count)} campaigns`;
    }
    if (!list) return;
    if (variants.length) {
      list.innerHTML = variants.map((v) => `
        <div class="row">
          <div><h3>${v.label || v.id}</h3><div class="stats">${dash(v.category)} · ${dash(v.state)} · ${dash(v.score)}</div></div>
          <div class="actions">
            <button class="btn primary" type="button" data-promote="${v.id}">Promote</button>
            <button class="btn" type="button" data-archive="${v.id}">Archive</button>
          </div>
        </div>`).join("");
      const postState = async (id, action) => {
        if (status) status.textContent = `POST /api/evolution/variants/${id}/${action}…`;
        try {
          const r = await apiFetch(`/api/evolution/variants/${id}/${action}`, { method: "POST" });
          const body = await r.json().catch(() => ({}));
          if (status) status.textContent = r.ok ? `${action} · ${dash(body.state || body.label)}` : `${action} ${r.status}`;
          if (r.ok) loadEvolution();
        } catch (e) {
          if (status) status.textContent = String(e);
        }
      };
      list.querySelectorAll("[data-promote]").forEach((b) => b.addEventListener("click", () => postState(b.dataset.promote, "promote")));
      list.querySelectorAll("[data-archive]").forEach((b) => b.addEventListener("click", () => postState(b.dataset.archive, "archive")));
      return;
    }
    const rows = data.campaigns || [];
    if (!rows.length) {
      list.innerHTML = `<p class="empty">No experiments yet. POST /api/product/bootstrap seeds variants.</p>`;
      return;
    }
    list.innerHTML = rows.map((c) => `
      <div class="row">
        <div><h3>${c.niche || c.id}</h3><div class="stats">${dash(c.status)} · ${dash(c.label || c.mode)}${c.crowned ? " · crowned" : ""}</div></div>
        <div class="actions">
          <button class="btn primary" type="button" data-crown="${c.id}">Crown</button>
          <button class="btn" type="button" data-retire="${c.id}">Retire</button>
        </div>
      </div>`).join("");
    const postFlag = async (id, path) => {
      try {
        const r = await apiFetch(`/api/evolution/${id}/${path}`, { method: "POST" });
        if (status) status.textContent = `${path} ${r.status}`;
        if (r.ok) loadEvolution();
      } catch (e) {
        if (status) status.textContent = String(e);
      }
    };
    list.querySelectorAll("[data-crown]").forEach((b) => b.addEventListener("click", () => postFlag(b.dataset.crown, "crown")));
    list.querySelectorAll("[data-retire]").forEach((b) => b.addEventListener("click", () => postFlag(b.dataset.retire, "retire")));
  }

  function drawAnalyticsBars(bars) {
    const svgEl = document.getElementById("analytics-svg");
    if (!svgEl || typeof d3 === "undefined") return;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    if (!bars.length) return;
    const width = svgEl.clientWidth || 640;
    const height = svgEl.clientHeight || 352;
    const margin = { top: 16, right: 16, bottom: 48, left: 40 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    svg.attr("viewBox", [0, 0, width, height]);
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
    const x = d3.scaleBand().domain(bars.map((d) => d.category)).range([0, innerW]).padding(0.2);
    const y = d3.scaleLinear().domain([0, d3.max(bars, (d) => d.value) || 1]).nice().range([innerH, 0]);
    g.append("g").attr("transform", `translate(0,${innerH})`).call(d3.axisBottom(x)).selectAll("text")
      .attr("fill", "#8b8b98").attr("transform", "rotate(-20)").style("text-anchor", "end");
    g.append("g").call(d3.axisLeft(y).ticks(4)).selectAll("text").attr("fill", "#8b8b98");
    g.selectAll("rect").data(bars).join("rect")
      .attr("x", (d) => x(d.category))
      .attr("y", (d) => y(d.value))
      .attr("width", x.bandwidth())
      .attr("height", (d) => innerH - y(d.value))
      .attr("fill", "#5ee9a4")
      .attr("rx", 4);
  }

  async function loadAnalytics() {
    const status = document.getElementById("an-status");
    let snap = null;
    try {
      const r = await fetch("/api/analytics");
      if (r.ok) snap = await r.json();
      else if (status) status.textContent = `GET /api/analytics ${r.status} — composing engine telemetry`;
    } catch {
      if (status) status.textContent = "GET /api/analytics unavailable — composing engine telemetry";
    }
    if (!snap) {
      try {
        const [c, f, k] = await Promise.all([
          fetch("/api/campaigns").then((r) => r.json()),
          fetch("/api/flywheel").then((r) => r.json()),
          fetch("/api/knowledge/nodes").then((r) => r.json()),
        ]);
        const items = c.campaigns || [];
        const by = {};
        items.forEach((row) => {
          const key = row.label || row.status || "unknown";
          by[key] = (by[key] || 0) + 1;
        });
        snap = {
          tick_total: f.tick_total || f.cycle_count || 0,
          campaigns: by,
          knowledge_count: k.count != null ? k.count : (k.nodes || []).length,
          research: { live: 0, dry_run: 0 },
        };
      } catch (err) {
        if (status) status.textContent = String(err);
        return;
      }
    }
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = dash(v); };
    set("an-ticks", snap.tick_total);
    const campMap = snap.campaigns_by_label || snap.campaigns || snap.campaign_counts || {};
    const campN = typeof campMap === "number" ? campMap : Object.values(campMap).reduce((a, b) => a + Number(b || 0), 0);
    set("an-campaigns", snap.campaign_count != null ? snap.campaign_count : campN);
    set("an-kg", snap.knowledge_count || snap.knowledge);
    const res = snap.research || {};
    set("an-research", `${dash(res.live)} live / ${dash(res.dry_run)} DRY-RUN`);
    const compounding = snap.compounding || {};
    const cards = compounding.cards || [];
    const headline = document.getElementById("an-headline");
    if (headline) headline.textContent = compounding.headline || "Compounding";
    const cardBox = document.getElementById("an-cards");
    if (cardBox && cards.length) {
      cardBox.innerHTML = cards.map((c) => `<article class="card"><span class="lbl">${c.label || c.metric}</span><div class="val green">${dash(c.value)}</div><div class="hint">${c.trend || ""} ${c.delta != null ? (c.delta >= 0 ? "+" : "") + c.delta : ""}</div></article>`).join("");
    }
    const bars = cards.length
      ? cards.map((c) => ({ category: c.label || c.metric, value: Number(c.value) || 0 }))
      : (Object.keys(campMap).length && typeof campMap === "object"
        ? Object.entries(campMap).map(([category, value]) => ({ category, value: Number(value) || 0 }))
        : [
            { category: "ticks", value: Number(snap.tick_total) || 0 },
            { category: "knowledge", value: Number(snap.knowledge_count) || 0 },
            { category: "campaigns", value: Number(campN) || 0 },
          ]);
    drawAnalyticsBars(bars);
    if (status) status.textContent = `GET /api/analytics · compounding ${cards.length} cards`;
  }

  function stopAnalyticsPoll() {
    if (analyticsTimer) {
      clearInterval(analyticsTimer);
      analyticsTimer = 0;
    }
  }

  function startAnalyticsPoll() {
    stopAnalyticsPoll();
    loadAnalytics();
    analyticsTimer = setInterval(loadAnalytics, 10000);
  }

  async function loadKnowledge() {
    try {
      const data = await (await fetch("/api/knowledge/nodes")).json();
      const nodes = data.nodes || [];
      const count = data.count != null ? data.count : nodes.length;
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
        list.innerHTML = nodes.length
          ? nodes.map((n) => `<div class="row"><div class="min-w"><h3>${n.topic}</h3><div class="stats">${n.trend || ""}</div></div><span class="pill">${n.updated_at || ""}</span></div>`).join("")
          : `<p class="muted">No stored nodes yet. POST /api/agent/research to upsert one.</p>`;
      }
      const pills = document.getElementById("kg-nodes");
      if (pills) {
        pills.innerHTML = nodes.length
          ? nodes.map((n) => `<span class="chip">${n.topic}</span>`).join("")
          : `<span class="chip">Empty</span>`;
      }
    } catch (err) {
      const list = document.getElementById("discovery-nodes");
      if (list) list.textContent = String(err);
    }
  }

  async function loadFlywheel() {
    const status = document.getElementById("flywheel-status");
    const cycles = document.querySelectorAll("#flywheel-cycles");
    try {
      const data = await (await fetch("/api/flywheel")).json();
      const label = `${data.tick_total || data.cycle_count || 0} ticks · ${data.running ? "running" : "stopped"}`;
      cycles.forEach((el) => { el.textContent = String(data.tick_total || data.cycle_count || 0); });
      if (status) {
        const check = data.last_self_check || {};
        status.textContent = `${label} · ${data.label || data.origin || ""}${check.inference_down || data.inference_down ? " · DRY-RUN (inference down)" : ""}`;
      }
      paintFlyLoop(data);
    } catch (err) {
      if (status) status.textContent = String(err);
    }
  }

  async function loadAgent(id) {
    const el = document.getElementById("agent-feed");
    try {
      const data = await (await fetch(`/api/agents/${id}`)).json();
      const r = data.result || {};
      const line = `${data.title || id} · ${r.label || r.mode || "idle"} · ${r.summary || data.goal || ""}`;
      if (el) el.textContent = line;
      const stream = document.getElementById("event-stream");
      const debug = document.getElementById("debug-events");
      if ((id === "orchestra" || id === "debugger") && (data.events || []).length) {
        const extra = eventHtml(data.events);
        if (stream && !sessionStorage.getItem(CAMPAIGN_KEY)) stream.innerHTML = extra;
        if (debug) debug.insertAdjacentHTML("afterbegin", extra);
      }
    } catch (err) {
      if (el) el.textContent = String(err);
    }
  }

  async function loadHealth() {
    async function paint(id, path) {
      const el = document.getElementById(id);
      if (!el) return;
      try {
        const r = await fetch(path);
        const body = await r.json().catch(async () => await r.text());
        el.textContent = typeof body === "string"
          ? `${path} ${r.status}\n${body}`
          : JSON.stringify({ path, status: r.status, ...body }, null, 2);
      } catch (err) {
        el.textContent = `${path} ${String(err)}`;
      }
    }
    const chips = document.getElementById("runtime-chips");
    try {
      const lz = await fetch("/livez");
      const live = await lz.json().catch(() => ({}));
      if (chips) {
        chips.innerHTML = `<span class="chip on">/livez ${lz.status}${live.ok ? " ok" : ""}</span>
          <span class="chip">GET /readyz · /health public</span>`;
      }
    } catch (err) {
      if (chips) chips.innerHTML = `<span class="chip">${String(err)}</span>`;
    }
    await Promise.all([paint("readyz-pre", "/readyz"), paint("health-pre", "/health")]);
  }

  function openPalette() {
    palette.classList.add("open");
    cmdList.innerHTML = PAGES.map((p) => `<button class="cmd-item" type="button" data-go="${p.id}">${p.title}</button>`).join("");
    cmdInput.value = "";
    cmdInput.focus();
    cmdList.querySelectorAll(".cmd-item").forEach((b) => {
      b.addEventListener("click", () => {
        location.hash = `#/${b.dataset.go}`;
        closePalette();
      });
    });
  }
  function closePalette() {
    palette.classList.remove("open");
  }

  function enterFromSplash() {
    sessionStorage.setItem("hermes-entered", "1");
    enterConsole();
  }
  document.getElementById("enter-console").addEventListener("click", (e) => {
    e.stopPropagation();
    enterFromSplash();
  });
  splash.addEventListener("click", enterFromSplash);
  document.getElementById("back-console").addEventListener("click", () => {
    location.hash = "#/overview";
    enterConsole();
  });
  document.getElementById("open-cmd").addEventListener("click", openPalette);
  splash.querySelector("video")?.addEventListener("click", (e) => e.stopPropagation());
  document.getElementById("launch-campaign").addEventListener("click", async () => {
    if (mutatingNeedsBearer()) {
      location.hash = "#/settings";
      return;
    }
    location.hash = "#/campaigns";
    await new Promise((resolve) => setTimeout(resolve, 0));
    const form = document.getElementById("campaign-form");
    const fields = { agent: "video-campaign" };
    if (form instanceof HTMLFormElement) {
      const data = new FormData(form);
      fields.niche = data.get("niche");
      fields.goal = data.get("goal");
      fields.brief = data.get("brief");
      fields.platforms = data.get("platforms");
      fields.budget = data.get("budget");
      fields.freq = data.get("freq");
    } else {
      fields.niche = "AI education";
      fields.goal = "Grow subscribers";
      fields.brief = "Autonomous video-campaign agent from the console header.";
    }
    try {
      await launchCampaign(fields);
    } catch (err) {
      launchMsg = String(err);
    }
  });
  const menuToggle = document.getElementById("menu-toggle");
  function closeMenu() {
    sidebar.classList.remove("open");
    menuToggle.setAttribute("aria-expanded", "false");
  }
  menuToggle.addEventListener("click", (e) => {
    const open = sidebar.classList.toggle("open");
    e.currentTarget.setAttribute("aria-expanded", String(open));
  });
  sidebar.querySelectorAll("nav a").forEach((a) => {
    a.addEventListener("click", closeMenu);
  });
  palette.addEventListener("click", (e) => {
    if (e.target === palette) closePalette();
  });
  cmdInput.addEventListener("input", () => {
    const q = cmdInput.value.toLowerCase();
    cmdList.querySelectorAll(".cmd-item").forEach((b) => {
      b.hidden = !b.textContent.toLowerCase().includes(q);
    });
  });
  window.addEventListener("hashchange", () => {
    closeMenu();
    render();
  });
  window.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      palette.classList.contains("open") ? closePalette() : openPalette();
    }
    if (e.key === "Escape") closePalette();
  });

  if (location.hash === "#/overview" || sessionStorage.getItem("hermes-entered")) {
    sessionStorage.setItem("hermes-entered", "1");
    enterConsole();
  }
  setInterval(loadLiveStrip, 12000);
})();
