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

  const topics = [
    { name: "Automation", competition: 0.5, velocity: 0.82, viral: 0.7, conf: 0.82 },
    { name: "Claude", competition: 0.61, velocity: 0.88, viral: 0.74, conf: 0.9 },
    { name: "UGC Product", competition: 0.42, velocity: 0.76, viral: 0.69, conf: 0.81 },
    { name: "Everyday Carry", competition: 0.38, velocity: 0.71, viral: 0.66, conf: 0.78 },
  ];
  const activity = [
    ["Research Agent", "Found 6 high-velocity AI education topics", "now"],
    ["Evolution Lab", "Experiment #129 crowned thumbnail B winner", "2m"],
    ["Publishing Agent", "Queued 4 Shorts — YouTube + TikTok", "8m"],
    ["Analytics Agent", "Retention lift +18% after hook rewrite", "14m"],
    ["Memory", "Learned: money hooks ↑23% CTR", "1h"],
  ];
  const campaigns = [
    ["Everyday Carry", "edc_tech · 7 scenes · 20s"],
    ["Everyday Carry", "edc_tech_best · 7 scenes · 19.94s"],
    ["Hermes OS — Platform Promo", "hermes_os_promo · 4 scenes · 12.6s"],
  ];

  function metric(label, value, hint, accent) {
    return `<article class="card${accent ? " accent" : ""}"><span class="lbl">${label}</span><div class="val${accent ? " green" : ""}">${value}</div><div class="hint">${hint}</div></article>`;
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
          <p class="muted">One-time campaign packs and Autonomous v0.4.0 sit on Stripe Checkout (test mode until you approve live).</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" data-pay="campaign_launch">Pay campaign launch</button>
            <button class="btn" type="button" data-subscribe>Subscribe console</button>
            <a class="btn" href="#/settings">Settings billing</a>
          </div>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("Revenue", "$12.4k", "30d · +18%", true)}
          ${metric("Views", "2.1M", "Across channels")}
          ${metric("CTR", "6.8%", "+11% vs baseline")}
          ${metric("Retention", "54%", "+18% evolved")}
          ${metric("RPM", "$4.20", "+9%")}
          ${metric("Publishing Queue", "14", "Scheduled")}
          ${metric("AI Confidence", "0.91", "Prediction gate")}
          ${metric("Opportunities", "37", "High velocity")}
          ${metric("Knowledge Nodes", "5", "Living graph")}
          ${metric("Flywheel cycles", "<span id=\"flywheel-cycles\">—</span>", "Live self-check ticks")}
          ${metric("Agents Online", "15", "Orchestra ready")}
          ${metric("Channel Health", "Strong", "Growth forecast ↑")}
        </div>
        <p class="muted" id="agent-feed" style="margin-top:0.75rem">Loading /api/agents/overview…</p>
        <div class="grid split" style="margin-top:0.75rem">
          <section class="card">
            <h2 class="section-h" style="margin:0 0 0.85rem">AI activity</h2>
            <div class="feed">${activity.map(([who, what, t]) => `<div class="feed-item"><time>${t}</time><strong>${who}</strong><span>${what}</span></div>`).join("")}</div>
          </section>
          <section class="card">
            <h2 class="section-h" style="margin:0 0 0.85rem">Operating loop</h2>
            <div class="loop" role="tablist">${["Discover","Create","Publish","Learn","Improve"].map((s) => `<button type="button" data-loop="${s}" class="${s===loopStep?"on":""}">${s}</button>`).join("")}</div>
            <p class="muted" style="margin:0.9rem 0 0">Every publish updates the knowledge graph and evolution weights for the next campaign.</p>
          </section>
        </div>`,
      discovery: `
        <p class="muted" id="agent-feed">Loading /api/agents/discovery…</p>
        <section class="card">
          <h2>AI opportunity scan</h2>
          <div class="chips">${["YouTube","Reddit","TikTok","Google Trends","X","News","Competitors"].map((c,i)=>`<button type="button" class="chip${i<4?" on":""}">${c}</button>`).join("")}</div>
          <p class="muted">Hermes continuously scans the open web for high-opportunity topics — not a single YouTube search.</p>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("Trending", "9", "High velocity")}
          ${metric("Emerging", "4", "Early signal")}
          ${metric("Low Competition", "5", "Whitespace")}
          ${metric("Avg Virality", "0.78", "Predicted", true)}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>High-opportunity topics</h2>
          <div id="discovery-nodes"><p class="muted">Loading stored knowledge nodes…</p></div>
        </section>`,
      knowledge: `
        <p class="muted" id="agent-feed">Loading /api/agents/knowledge…</p>
        <div class="grid metrics-3">
          ${metric("Nodes", "9", "Living graph")}
          ${metric("Relations", "8", "Causal edges")}
          ${metric("Feedback Loops", "Active", "Analytics → Memory", true)}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>Living knowledge graph</h2>
          <div class="flow">${["Topic","Audience","Hooks","Scripts","Videos","Analytics"].map((n)=>`<span>${n}</span><i>→</i>`).join("")}<span class="end">Updated Graph</span></div>
          <p class="muted">Every publish strengthens the graph. Hermes doesn’t store files — it stores causal media intelligence.</p>
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
        </div>`,
      orchestra: `
        <section class="card">
          <h2>Category orchestra</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/orchestra…</p>
          <div class="actions" style="margin-top:0.6rem">
            <button class="btn primary" type="button" id="agents-tick">Tick all category agents</button>
          </div>
        </section>
        <div class="grid metrics" style="margin-top:0.75rem">
          ${metric("CEO", "Hermes OS Orchestrator", "Orchestrator")}
          ${metric("Agents", "0", "OS + kernel")}
          ${metric("Healthy", "—%", "Runtime health")}
          ${metric("Platform", "—", "Reliability layer")}
        </div>
        <section class="card" style="margin-top:0.75rem"><h2>Organization</h2><p class="empty">Loading organization…</p></section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Live event stream</h2>
          <div class="feed" id="event-stream"><p class="empty">Waiting for workflow events…</p></div>
          <div class="actions" style="margin-top:0.8rem">
            <button class="btn primary" type="button" id="dry-run">Run dry-run campaign</button>
            <a class="btn" href="#/debugger">AI Debugger</a>
          </div>
        </section>`,
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
            <button class="btn primary" type="button" id="probe">Run /api/ai/complete probe</button>
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
        <section class="card" style="margin-top:0.75rem">
          <h2>Timeline</h2>
          <p class="muted">Hook → proof → payoff. 7-scene EDC cut at 20s, or a 4-scene Hermes OS promo at 12.6s.</p>
          <div class="flow" style="margin-top:1rem">${["Hook","Problem","Demo","Proof","CTA"].map((n)=>`<span>${n}</span><i>→</i>`).join("")}<span class="end">Export</span></div>
        </section>
        <div class="grid split" style="margin-top:0.75rem">
          <section class="card"><h2>Active cut</h2><p class="muted">hermes_os_promo · 1920×1080 · 30 fps</p></section>
          <section class="card"><h2>Captions</h2><p class="muted">Burned-in, high contrast, 4-word lines.</p></section>
        </div>`,
      evolution: `
        <p class="muted" id="agent-feed">Loading /api/agents/evolution…</p>
        <div class="grid metrics-3">
          ${metric("Flywheel cycles", "<span id=\"flywheel-cycles\">—</span>", "Completed ticks", true)}
          ${metric("Crown", "#129", "Thumbnail B")}
          ${metric("Lift", "+18%", "Retention after hook rewrite")}
        </div>
        <section class="card" style="margin-top:0.75rem">
          <h2>Perpetual flywheel</h2>
          <p class="muted" id="flywheel-status">Loading /api/flywheel…</p>
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" id="flywheel-start">Start flywheel</button>
            <button class="btn" type="button" id="flywheel-stop">Stop</button>
          </div>
        </section>
        <section class="card" style="margin-top:0.75rem"><h2>Variant board</h2><p class="muted">Thumbnail B beat A on CTR. Money hooks keep winning. Losing intros are retired automatically.</p></section>`,
      analytics: `
        <p class="muted" id="agent-feed">Loading /api/agents/analytics…</p>
        <div class="grid metrics">
          ${metric("Views", "2.1M", "Across channels")}
          ${metric("CTR", "6.8%", "+11% vs baseline", true)}
          ${metric("Retention", "54%", "+18% evolved")}
          ${metric("RPM", "$4.20", "+9%")}
        </div>
        <section class="card" style="margin-top:0.75rem"><h2>Forecast</h2><p class="muted">Channel health is Strong. Next 30 days assume the current operating loop stays on Improve.</p></section>`,
      memory: `
        <section class="card">
          <h2>Memory agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/memory…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Learned</h2>
          ${["Money hooks ↑23% CTR","Short first-frame motion beats stills","EDC niches compound on Shorts + TikTok"].map((x)=>`<div class="row"><h3>${x}</h3></div>`).join("")}
        </section>`,
      command: `
        <p class="muted" id="agent-feed">Loading /api/agents/command…</p>
        <section class="card">
          <h2>Gateway</h2>
          <pre class="status" id="health-pre">checking…</pre>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Ops</h2>
          <p class="muted">/livez process up · /readyz production key present · /health inference + models · /docs OpenAPI</p>
        </section>`,
      publishing: `
        <section class="card">
          <h2>Publishing agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/publishing…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Queue · 14 scheduled</h2>
          ${["YouTube Short · Automation hook","TikTok · Claude vs coding","Reels · Everyday Carry 20s"].map((x)=>`<div class="row"><h3>${x}</h3><span class="pill">Queued</span></div>`).join("")}
        </section>`,
      uploads: `
        <section class="card">
          <h2>Uploads agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/uploads…</p>
        </section>
        <section class="card" style="margin-top:0.75rem">
          <h2>Drop zone</h2>
          <p class="muted">Brand kits, stills, and source clips land here before Studio. Nothing is a dead file — uploads become graph nodes.</p>
        </section>`,
      settings: `
        <section class="card">
          <h2>Settings agent</h2>
          <p class="muted" id="agent-feed">Loading /api/agents/settings…</p>
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
          <div class="actions" style="margin-top:0.7rem">
            <button class="btn primary" type="button" data-pay="campaign_launch">Pay campaign launch</button>
            <button class="btn" type="button" data-pay="credit_pack">Buy credit pack</button>
            <button class="btn" type="button" data-subscribe>Subscribe Autonomous v0.4.0</button>
          </div>
        </section>
        <p class="muted" style="margin:1rem 0 0"><a href="#/outro">End card</a> · <a href="/docs">/docs</a> · <a href="/health">/health</a></p>`,
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
    if (page.id === "command") loadHealth();
    if (page.id === "settings") loadBilling();
    if (page.id === "overview" || page.id === "evolution") loadFlywheel();
    if (page.id === "discovery" || page.id === "knowledge") loadKnowledge();
    loadAgent(page.id);
    bindPage(page.id);
    bindBilling();
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
    const r = await fetch("/api/campaigns", {
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

  async function loadBilling() {
    const el = document.getElementById("billing-status");
    if (!el) return;
    try {
      const r = await fetch("/api/billing/config");
      const data = await r.json();
      const skus = (data.products || []).map((p) => p.sku).join(", ");
      el.textContent = data.configured
        ? `Stripe ${data.test_mode ? "test" : "live"} · ${skus}`
        : `Stripe not configured. ${data.hint || "Set STRIPE_SECRET_KEY=sk_test_..."}`;
    } catch (err) {
      el.textContent = String(err);
    }
  }

  function bindBilling() {
    document.querySelectorAll("[data-pay]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sku = btn.getAttribute("data-pay");
        try {
          const r = await fetch("/api/billing/checkout", {
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
          const r = await fetch("/api/billing/subscribe", {
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
      await fetch("/api/flywheel/start", { method: "POST" });
      loadFlywheel();
    });
    document.getElementById("flywheel-stop")?.addEventListener("click", async () => {
      await fetch("/api/flywheel/stop", { method: "POST" });
      loadFlywheel();
    });
    document.getElementById("probe")?.addEventListener("click", async () => {
      inferences += 1;
      probeMsg = "Probe recorded. Gateway /v1/chat/completions is the production path.";
      try {
        const r = await fetch("/health");
        const data = await r.json();
        const inf = data.inference || data;
        probeMsg = `Probe #${inferences} · backend ${inf.backend || "unknown"} · reachable ${inf.reachable}`;
      } catch (err) {
        probeMsg = `Probe #${inferences} · local console (${String(err)})`;
      }
      const empty = document.getElementById("probe-empty");
      if (empty) empty.textContent = probeMsg;
      refreshActive();
    });
    document.getElementById("refresh-probe")?.addEventListener("click", () => refreshActive());
    document.getElementById("agents-tick")?.addEventListener("click", async () => {
      const el = document.getElementById("agent-feed");
      if (el) el.textContent = "Ticking 14 category agents…";
      try {
        await fetch("/api/agents/tick", { method: "POST" });
        loadAgent("orchestra");
      } catch (err) {
        if (el) el.textContent = String(err);
      }
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

  async function loadKnowledge() {
    try {
      const data = await (await fetch("/api/knowledge/nodes")).json();
      const nodes = data.nodes || [];
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
      const label = `${data.cycle_count || 0} cycles · ${data.running ? "running" : "stopped"}`;
      cycles.forEach((el) => { el.textContent = String(data.cycle_count || 0); });
      if (status) {
        const check = data.last_self_check || {};
        status.textContent = `${label} · origin ${data.origin}${check.inference_down ? " · DRY-RUN (inference down)" : ""}`;
      }
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
    const el = document.getElementById("health-pre");
    if (!el) return;
    try {
      const r = await fetch("/health");
      el.textContent = JSON.stringify(await r.json(), null, 2);
    } catch (err) {
      el.textContent = String(err);
    }
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
  document.getElementById("launch-campaign").addEventListener("click", async () => {
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
})();
