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

const TOPICS = [
  ["Automation", "0.51", "0.82", "0.70", "0.82"],
  ["Claude", "0.44", "0.79", "0.74", "0.86"],
  ["UGC Product", "0.39", "0.71", "0.66", "0.80"],
  ["Everyday Carry", "0.50", "0.82", "0.70", "0.82"],
];

function card(label, value, hint, glow, mint) {
  return `<article class="card${glow ? " glow" : ""}"><div class="label">${label}</div><div class="value${mint ? " mint" : ""}">${value}</div><div class="hint">${hint}</div></article>`;
}

const PAGES = {
  overview() {
    return `
      <article class="card os-hero">
        <div class="label">Product walkthrough</div>
        <video class="os-hero-video" src="/static/media/hermes-os.mp4" muted loop playsinline autoplay controls preload="metadata"></video>
        <p class="hint" style="margin:0.7rem 0 0">Muted autoplay — use controls if you want sound.</p>
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
        ${card("Knowledge nodes", "5", "Living graph")}
        ${card("Experiments", "242", "Running / scored")}
        ${card("Agents online", "15", "Orchestra ready")}
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
        </article>
      </div>`;
  },
  discovery() {
    return `
      <article class="card">
        <strong>AI opportunity scan</strong>
        <div class="pills" style="margin:0.7rem 0">
          <span class="pill on">YouTube</span><span class="pill">Reddit</span><span class="pill">TikTok</span>
          <span class="pill">Google Trends</span><span class="pill">X</span><span class="pill">News</span><span class="pill">Competitors</span>
        </div>
        <p class="hint">Hermes continuously scans the open web for high-opportunity topics — not a single YouTube search.</p>
      </article>
      <div class="grid cols-4" style="margin-top:0.75rem">
        ${card("Trending", "9", "High velocity")}
        ${card("Emerging", "4", "Early signal")}
        ${card("Low competition", "5", "Whitespace")}
        ${card("Avg virality", "0.78", "Predicted", true, true)}
      </div>
      <article class="card" style="margin-top:0.75rem">
        <strong>High-opportunity topics</strong>
        ${TOPICS.map(([n, c, v, vir, conf]) => `
          <div class="row">
            <div>
              <strong>${n}</strong>
              <div class="hint">Competition ${c} · Velocity ${v}</div>
            </div>
            <div class="hint">Viral ${vir} · <span style="color:var(--mint)">Conf ${conf}</span></div>
          </div>`).join("")}
      </article>`;
  },
  knowledge() {
    return `
      <div class="grid cols-3">
        ${card("Nodes", "9", "Living graph")}
        ${card("Relations", "8", "Causal edges")}
        ${card("Feedback loops", "Active", "Analytics → Memory", true, true)}
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
        <strong>Sample connections</strong>
        <div class="pills" style="margin-top:0.8rem">
          ${["AI","Claude","Coding","Automation","Startup","Productivity","Everyday Carry","UGC Product","YouTube Shorts"].map((t) => `<span class="pill">${t}</span>`).join("")}
        </div>
      </article>`;
  },
  campaigns() {
    return `
      <div class="grid cols-2">
        <article class="card">
          <strong>Campaign builder</strong>
          ${[["niche","NICHE","AI education"],["goal","GOAL","Grow subscribers"],["brief","BRIEF","Vertical shorts that teach one AI workflow per cut."],["platforms","PLATFORMS","YouTube Shorts, TikTok, Reels"],["budget","BUDGET","$2,000 / mo"],["freq","FREQUENCY","2 / day"]].map(([id,l,v]) => `
            <div class="field"><label for="${id}">${l}</label><input id="${id}" value="${v}" /></div>`).join("")}
          <button type="button" class="primary" style="width:100%" data-launch>Launch campaign</button>
          <p class="hint" id="launch-status" style="margin-top:0.6rem"></p>
        </article>
        <article class="card">
          <strong>Active cuts</strong>
          <div id="active-cuts"><p class="hint">Launch the video-campaign agent to plan cuts.</p></div>
        </article>
      </div>`;
  },
  orchestra() {
    return `
      <div class="grid cols-4">
        ${card("CEO", "Hermes OS Orchestrator", "Orchestrator")}
        ${card("Agents", "15", "OS + kernel")}
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
      <div class="grid cols-4">
        ${card("Inferences", "0", "Recorded")}
        ${card("Total cost", "$0.0000", "USD")}
        ${card("Avg latency", "0ms", "p50-ish avg")}
        ${card("Fallback rate", "0", "Provider failover")}
      </div>
      <article class="card" style="margin-top:0.75rem">
        <strong>Probe inference</strong>
        <div style="display:flex;gap:0.5rem;margin-top:0.8rem;flex-wrap:wrap">
          <button type="button" class="primary" id="probe">Run /api/ai/complete probe</button>
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
    return `<article class="card"><strong>Studio</strong><p class="hint">Scene stack for Hermes OS — Platform Promo and Everyday Carry. Open a campaign and press Render.</p></article>`;
  },
  evolution() {
    return `<div class="grid cols-3">${card("Experiments","242","Running / scored")}${card("Crowned","#129","Thumbnail B")}${card("Lift","+18%","Retention")}</div>`;
  },
  analytics() {
    return `<div class="grid cols-4">${card("Views","2.1M","Across channels")}${card("CTR","6.8%","+11%")}${card("Retention","54%","+18% evolved")}${card("RPM","$4.20","+9%")}</div>`;
  },
  memory() {
    return `<article class="card"><strong>Learned</strong><p class="hint">Money hooks +23% CTR. Hook rewrites lift retention. Graph stores causal media intelligence, not files.</p></article>`;
  },
  command() {
    return `<article class="card"><strong>Command Center</strong><p class="hint" id="cmd-health">Loading /health…</p><p class="hint">OpenAI-compatible /v1 on hermestudios.com. Bearer HERMES_API_KEY.</p></article>`;
  },
  publishing() {
    return `<article class="card"><strong>Publishing queue</strong><p class="hint">14 scheduled. Last: 4 Shorts — YouTube + TikTok.</p></article>`;
  },
  uploads() {
    return `<article class="card"><strong>Uploads</strong><p class="hint">Drop references here. Binary YouTube upload stays on the studio Mac CLI.</p></article>`;
  },
  settings() {
    return `<article class="card"><strong>Settings</strong><p class="hint">Domain hermestudios.com · auth required on /v1 · inference via vLLM or studio fallback.</p></article>`;
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
        const r = await fetch("/api/campaigns", {
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
    dry.addEventListener("click", () => {
      document.getElementById("events").textContent =
        "Dry-run queued · Research Agent scanning AI education…";
    });
  }
  const probe = document.getElementById("probe");
  if (probe) {
    probe.addEventListener("click", runProbe);
  }
  const refresh = document.getElementById("refresh-health");
  if (refresh) refresh.addEventListener("click", runProbe);
  if (id === "command") loadHealth("cmd-health");
}

function runProbe() {
  const out = document.getElementById("probe-out");
  if (out) out.textContent = "Calling /health…";
  fetch("/health")
    .then((r) => r.json())
    .then((d) => {
      if (out) out.textContent = JSON.stringify(d, null, 2);
    })
    .catch((e) => {
      if (out) out.textContent = String(e);
    });
}

function loadHealth(elId) {
  const el = document.getElementById(elId);
  if (!el) return;
  fetch("/health")
    .then((r) => r.json())
    .then((d) => { el.textContent = JSON.stringify(d, null, 2); })
    .catch((e) => { el.textContent = String(e); });
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
