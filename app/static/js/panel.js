const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

const state = { leads: [], jobs: [], providers: [], config: null, currentJob: null, es: null };

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401) {
    location.href = "/login";
    throw new Error("unauthorized");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.message || res.statusText);
  return data;
}

function showView(name) {
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $(`#view-${name}`).classList.remove("hidden");
  $$(".nav").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  const titles = {
    overview: "Overview",
    prospect: "Prospecções",
    leads: "Leads",
    jobs: "Jobs",
    config: "Config",
  };
  $("#view-title").textContent = titles[name] || name;
}

$$(".nav").forEach((btn) => btn.addEventListener("click", () => {
  showView(btn.dataset.view);
  if (btn.dataset.view === "leads") renderLeads();
  if (btn.dataset.view === "jobs") renderJobs();
  if (btn.dataset.view === "config") renderConfig();
  if (btn.dataset.view === "overview") renderOverview();
}));

async function boot() {
  renderProspectForm();
  const [stats, engines, providers] = await Promise.all([
    api("/api/stats"),
    api("/api/config/engines"),
    api("/api/providers"),
  ]);
  state.providers = providers;
  const eng = engines.default || "nenhum";
  $("#engine-badge").textContent = `Maps: ${eng}`;
  renderOverview(stats);
  await renderLeads();
  await renderJobs();
}

function renderOverview(stats) {
  if (!stats) return api("/api/stats").then(renderOverview);
  $("#view-overview").innerHTML = `
    <div class="grid">
      ${["total","novo","publicado","proposta","fechado","jobs_queued","jobs_running"].map((k) => `
        <div class="stat"><span class="muted">${k}</span><strong>${stats[k] ?? 0}</strong></div>
      `).join("")}
    </div>
    <div class="panel">
      <p class="muted">Funil local — Places/Apify para Maps · Playwright só no site do lead · LLM para redesign/proposta.</p>
    </div>`;
}

function renderProspectForm() {
  $("#view-prospect").innerHTML = `
    <div class="panel">
      <form id="prospect-form" class="stack">
        <div class="row">
          <label style="flex:1">Nicho
            <input name="nicho" value="nutricionistas" required />
          </label>
          <label style="flex:1">Cidade
            <input name="cidade" value="São Paulo" required />
          </label>
          <label>Meta
            <input name="meta" type="number" min="1" max="100" value="5" />
          </label>
        </div>
        <div class="row">
          <label>Nota mín.
            <input name="notaMinima" type="number" step="0.1" value="4.7" />
          </label>
          <label>Aval. mín.
            <input name="avaliacoesMinimas" type="number" value="40" />
          </label>
          <label>Engine
            <select name="engine">
              <option value="auto">auto (Places → Apify)</option>
              <option value="google_places">Google Places</option>
              <option value="apify">Apify</option>
            </select>
          </label>
          <label>LLM (proposta/redesign)
            <select name="provider" id="provider-select"><option value="">default</option></select>
          </label>
        </div>
        <button class="btn primary" type="submit">Disparar prospecção</button>
      </form>
      <h3 style="margin-top:24px">Log ao vivo</h3>
      <div class="log" id="job-log">Aguardando job…</div>
    </div>`;

  $("#prospect-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    payload.meta = Number(payload.meta);
    payload.notaMinima = Number(payload.notaMinima);
    payload.avaliacoesMinimas = Number(payload.avaliacoesMinimas);
    const body = { type: "prospectar", payload, provider: payload.provider || null };
    const res = await api("/api/jobs", { method: "POST", body: JSON.stringify(body) });
    watchJob(res.id);
  });
}

function fillProviders() {
  const sel = $("#provider-select");
  if (!sel) return;
  state.providers.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = `${p.name}${p.available ? "" : " (off)"}`;
    opt.disabled = !p.available && p.id !== "openrouter";
    sel.appendChild(opt);
  });
}

async function renderLeads() {
  state.leads = await api("/api/leads");
  const rows = state.leads
    .filter((l) => l.status !== "descartado")
    .slice(0, 100)
    .map((l) => `
      <tr>
        <td><strong>${esc(l.nome)}</strong><div class="muted small">${esc(l.nicho || "")} · ${esc(l.cidade || "")}</div></td>
        <td>${l.nota ?? "—"} / ${l.avaliacoes ?? 0}</td>
        <td><span class="pill ${esc(l.status)}">${esc(l.status)}</span></td>
        <td class="small">${esc(l.email || "")}</td>
        <td class="small">${esc((l.motivo || "").slice(0, 80))}</td>
        <td class="row">
          <button class="btn ghost" data-act="redesenhar" data-slug="${esc(l.slug)}">Redesenhar</button>
          <button class="btn ghost" data-act="publicar" data-slug="${esc(l.slug)}">Publicar</button>
          <button class="btn ghost" data-act="proposta" data-slug="${esc(l.slug)}">Proposta</button>
        </td>
      </tr>`).join("");
  $("#view-leads").innerHTML = `
    <div class="panel">
      <div class="row" style="margin-bottom:12px">
        <button class="btn ghost" id="refresh-leads">Atualizar</button>
      </div>
      <table class="table">
        <thead><tr><th>Lead</th><th>Nota</th><th>Status</th><th>E-mail</th><th>Motivo</th><th>Ações</th></tr></thead>
        <tbody>${rows || "<tr><td colspan=6>Nenhum lead</td></tr>"}</tbody>
      </table>
    </div>`;
  $("#refresh-leads")?.addEventListener("click", renderLeads);
  $$("[data-act]").forEach((btn) => btn.addEventListener("click", async () => {
    const res = await api("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ type: btn.dataset.act, payload: { slug: btn.dataset.slug } }),
    });
    showView("prospect");
    watchJob(res.id);
  }));
}

async function renderJobs() {
  state.jobs = await api("/api/jobs?limit=40");
  const rows = state.jobs.map((j) => `
    <tr>
      <td>#${j.id}</td>
      <td>${esc(j.type)}</td>
      <td><span class="pill ${esc(j.status)}">${esc(j.status)}</span></td>
      <td class="small">${esc(j.created_at || "")}</td>
      <td class="row">
        <button class="btn ghost" data-watch="${j.id}">Log</button>
        ${j.status === "queued" || j.status === "running"
          ? `<button class="btn danger" data-cancel="${j.id}">Cancelar</button>` : ""}
      </td>
    </tr>`).join("");
  $("#view-jobs").innerHTML = `
    <div class="panel">
      <table class="table">
        <thead><tr><th>ID</th><th>Tipo</th><th>Status</th><th>Criado</th><th></th></tr></thead>
        <tbody>${rows || "<tr><td colspan=5>Sem jobs</td></tr>"}</tbody>
      </table>
    </div>`;
  $$("[data-watch]").forEach((b) => b.addEventListener("click", () => {
    showView("prospect");
    watchJob(Number(b.dataset.watch));
  }));
  $$("[data-cancel]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/jobs/${b.dataset.cancel}/cancel`, { method: "POST", body: "{}" });
    renderJobs();
  }));
}

async function renderConfig() {
  state.config = await api("/api/config");
  const m = state.config.maps || {};
  const llm = state.config.llm || {};
  const a = state.config.assinatura || {};
  const p = state.config.prospeccao || {};
  $("#view-config").innerHTML = `
    <div class="panel stack">
      <h3>Assinatura</h3>
      <div class="row">
        <label style="flex:1">Nome<input id="cfg-nome" value="${esc(a.nome || "")}" /></label>
        <label style="flex:1">WhatsApp<input id="cfg-wa" value="${esc(a.whatsapp || "")}" /></label>
      </div>
      <label>Apresentação<textarea id="cfg-apres" rows="2">${esc(a.apresentacao || "")}</textarea></label>
      <h3>Maps engines</h3>
      <div class="row">
        <label style="flex:1">Google Maps API Key<input id="cfg-gmaps" type="password" value="${esc(m.google_maps_api_key || "")}" placeholder="AIza…" /></label>
        <label style="flex:1">Apify API Key<input id="cfg-apify" type="password" value="${esc(m.apify_api_key || "")}" placeholder="apify_api_…" /></label>
        <label>Engine<select id="cfg-engine">
          <option value="auto">auto</option>
          <option value="google_places">places</option>
          <option value="apify">apify</option>
        </select></label>
      </div>
      <div class="row">
        <button class="btn ghost" id="test-places">Testar Places</button>
        <button class="btn ghost" id="test-apify">Testar Apify</button>
      </div>
      <h3>LLM</h3>
      <div class="row">
        <label style="flex:1">OpenRouter Key<input id="cfg-or" type="password" value="${esc(llm.openrouter_api_key || "")}" /></label>
        <label style="flex:1">Modelo default<input id="cfg-ormodel" value="${esc(llm.openrouter_model || "openai/gpt-4o-mini")}" /></label>
        <label>Provider default<select id="cfg-prov">
          <option value="openrouter">openrouter</option>
          <option value="claude">claude</option>
          <option value="codex">codex</option>
          <option value="cursor">cursor</option>
        </select></label>
      </div>
      <div id="providers-status" class="muted small"></div>
      <button class="btn primary" id="save-cfg">Salvar config</button>
      <div id="cfg-msg" class="muted"></div>
    </div>`;
  $("#cfg-engine").value = m.engine || "auto";
  $("#cfg-prov").value = llm.default_provider || "openrouter";
  $("#providers-status").textContent = state.providers
    .map((x) => `${x.name}: ${x.available ? "ok" : "off"}`)
    .join(" · ");

  $("#save-cfg").onclick = async () => {
    const body = {
      assinatura: {
        nome: $("#cfg-nome").value,
        whatsapp: $("#cfg-wa").value,
        apresentacao: $("#cfg-apres").value,
      },
      maps: {
        google_maps_api_key: $("#cfg-gmaps").value || "***",
        apify_api_key: $("#cfg-apify").value || "***",
        engine: $("#cfg-engine").value,
      },
      llm: {
        openrouter_api_key: $("#cfg-or").value || "***",
        openrouter_model: $("#cfg-ormodel").value,
        default_provider: $("#cfg-prov").value,
      },
      prospeccao: p,
    };
    await api("/api/config", { method: "POST", body: JSON.stringify(body) });
    $("#cfg-msg").textContent = "Salvo.";
    state.providers = await api("/api/providers");
  };
  $("#test-places").onclick = async () => {
    const r = await api("/api/config/engines/test", { method: "POST", body: JSON.stringify({ engine: "google_places" }) });
    $("#cfg-msg").textContent = r.message || JSON.stringify(r);
  };
  $("#test-apify").onclick = async () => {
    const r = await api("/api/config/engines/test", { method: "POST", body: JSON.stringify({ engine: "apify" }) });
    $("#cfg-msg").textContent = r.message || JSON.stringify(r);
  };
}

function watchJob(id) {
  if (state.es) state.es.close();
  const log = $("#job-log");
  log.textContent = `Job #${id}…\n`;
  state.es = new EventSource(`/api/jobs/${id}/events`);
  state.es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.done) {
        log.textContent += `\n— fim (${data.status}) —\n`;
        state.es.close();
        renderLeads();
        renderJobs();
        return;
      }
      if (data.message) log.textContent += `[${data.level || "info"}] ${data.message}\n`;
      log.scrollTop = log.scrollHeight;
    } catch (_) {}
  };
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

boot().then(fillProviders).catch((e) => console.error(e));
