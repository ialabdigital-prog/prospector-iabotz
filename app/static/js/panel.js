const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

const PIPELINE = [
  { status: "novo", label: "Novo", hint: "Lead ouro do Maps", next: "redesenhar", nextLabel: "Redesenhar site" },
  { status: "redesenhado", label: "Redesenhado", hint: "Site gerado em sites/", next: "publicar", nextLabel: "Publicar + DNS" },
  { status: "publicado", label: "Publicado", hint: "aaPanel + Cloudflare", next: "proposta", nextLabel: "Enviar proposta" },
  { status: "proposta", label: "Proposta", hint: "Rascunho / Gmail", next: null, nextLabel: "Aguardar resposta" },
  { status: "fechado", label: "Fechado", hint: "Cliente", next: null, nextLabel: "—" },
];

const state = {
  leads: [],
  jobs: [],
  providers: [],
  config: null,
  integrations: null,
  filter: "ativos",
  selected: null,
  es: null,
};

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

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 4200);
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pipelineInfo(status) {
  return PIPELINE.find((p) => p.status === status) || {
    status,
    label: status,
    hint: "",
    next: status === "novo" ? "redesenhar" : null,
    nextLabel: "—",
  };
}

function nextAction(lead) {
  const info = pipelineInfo(lead.status);
  if (lead.status === "publicado" && !lead.email) {
    return { type: null, label: "Falta e-mail no lead", disabled: true };
  }
  if (!info.next) return { type: null, label: info.nextLabel, disabled: true };
  return { type: info.next, label: info.nextLabel, disabled: false };
}

const VIEWS = {
  overview: { title: "Funil", sub: "Do Maps ao e-mail — um lead por vez" },
  prospect: { title: "Prospectar", sub: "Busca no Google Maps · nota · site fraco · e-mail" },
  leads: { title: "Leads", sub: "Redesenhar → publicar (aaPanel + DNS) → proposta" },
  jobs: { title: "Jobs", sub: "Fila e histórico de execução" },
  config: { title: "Configurações", sub: "Maps · aaPanel · Cloudflare · Gmail/Composio · LLM" },
};

function showView(name) {
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $(`#view-${name}`).classList.remove("hidden");
  $$(".nav").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  const meta = VIEWS[name] || { title: name, sub: "" };
  $("#view-title").textContent = meta.title;
  $("#view-sub").textContent = meta.sub;
}

$$(".nav").forEach((btn) =>
  btn.addEventListener("click", () => {
    showView(btn.dataset.view);
    if (btn.dataset.view === "leads") renderLeads();
    if (btn.dataset.view === "jobs") renderJobs();
    if (btn.dataset.view === "config") renderConfig();
    if (btn.dataset.view === "overview") renderOverview();
    if (btn.dataset.view === "prospect") renderProspectForm();
  })
);

$$("[data-close-drawer]").forEach((el) =>
  el.addEventListener("click", closeDrawer)
);

function openDrawer(lead) {
  state.selected = lead;
  const drawer = $("#drawer");
  drawer.classList.remove("hidden");
  drawer.setAttribute("aria-hidden", "false");
  $("#drawer-title").textContent = lead.nome || lead.slug;
  $("#drawer-status").innerHTML = `<span class="pill ${esc(lead.status)}">${esc(lead.status)}</span>`;

  const stages = ["novo", "redesenhado", "publicado", "proposta", "fechado"];
  const idx = stages.indexOf(lead.status);
  const mini = stages
    .map((s, i) => {
      const cls = i < idx ? "done" : i === idx ? "now" : "";
      return `<span class="${cls}">${esc(pipelineInfo(s).label)}</span>`;
    })
    .join("");

  const next = nextAction(lead);
  $("#drawer-body").innerHTML = `
    <div class="pipeline-mini">${mini}</div>
    <div class="kv">
      <div><dt>Nicho</dt><dd>${esc(lead.nicho || "—")}</dd></div>
      <div><dt>Cidade</dt><dd>${esc(lead.cidade || "—")}</dd></div>
      <div><dt>Nota Maps</dt><dd>${esc(lead.nota ?? "—")} · ${esc(lead.avaliacoes ?? 0)} avaliações</dd></div>
      <div><dt>E-mail</dt><dd>${esc(lead.email || "—")}</dd></div>
      <div><dt>WhatsApp</dt><dd>${esc(lead.whatsapp || lead.telefone || "—")}</dd></div>
      <div><dt>Site atual</dt><dd>${lead.siteAntigo ? `<a href="${esc(lead.siteAntigo)}" target="_blank" rel="noopener">${esc(lead.siteAntigo)}</a>` : "—"}</dd></div>
      <div><dt>Site novo</dt><dd>${lead.urlNova ? `<a href="${esc(lead.urlNova)}" target="_blank" rel="noopener">${esc(lead.urlNova)}</a>` : "<span class='muted'>ainda não publicado</span>"}</dd></div>
      <div><dt>Motivo</dt><dd>${esc(lead.motivo || "—")}</dd></div>
      <div><dt>Slug</dt><dd class="muted small">${esc(lead.slug)}</dd></div>
    </div>
    <p class="muted small" style="margin:0">
      <strong style="color:var(--accent)">Próximo passo:</strong> ${esc(next.label)}
      ${lead.status === "redesenhado" ? " — copia para aaPanel e cria CNAME no Cloudflare." : ""}
      ${lead.status === "publicado" ? " — gera rascunho (Composio/Gmail ou arquivo local)." : ""}
    </p>`;

  $("#drawer-actions").innerHTML = `
    ${!next.disabled && next.type
      ? `<button class="btn primary" data-run="${esc(next.type)}" data-slug="${esc(lead.slug)}">${esc(next.label)}</button>`
      : ""}
    ${lead.status === "novo" || lead.status === "redesenhado"
      ? `<button class="btn ghost" data-run="redesenhar" data-slug="${esc(lead.slug)}">Redesenhar</button>`
      : ""}
    ${["redesenhado", "publicado"].includes(lead.status)
      ? `<button class="btn ghost" data-run="publicar" data-slug="${esc(lead.slug)}">Publicar + DNS</button>`
      : ""}
    ${["publicado", "proposta"].includes(lead.status)
      ? `<button class="btn ghost" data-run="proposta" data-slug="${esc(lead.slug)}">Proposta</button>`
      : ""}
    ${lead.urlNova
      ? `<a class="btn ghost" href="${esc(lead.urlNova)}" target="_blank" rel="noopener">Abrir site</a>`
      : ""}
  `;
  $$("#drawer-actions [data-run]").forEach((btn) =>
    btn.addEventListener("click", () => startJob(btn.dataset.run, btn.dataset.slug))
  );
}

function closeDrawer() {
  $("#drawer").classList.add("hidden");
  $("#drawer").setAttribute("aria-hidden", "true");
  state.selected = null;
}

async function startJob(type, slug) {
  closeDrawer();
  showView("prospect");
  renderProspectForm(type);
  try {
    const res = await api("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ type, payload: { slug } }),
    });
    toast(`${type} · ${slug}`);
    await watchJob(res.id, type);
  } catch (err) {
    appendLog(`Erro: ${err.message}`);
    toast(err.message);
  }
}

async function boot() {
  renderProspectForm();
  const [stats, engines, providers, integ] = await Promise.all([
    api("/api/stats"),
    api("/api/config/engines"),
    api("/api/providers"),
    api("/api/config/integrations").catch(() => ({ funnel: [] })),
  ]);
  state.providers = providers;
  state.integrations = integ;
  const eng = engines.default || "nenhum";
  $("#engine-badge").textContent = `Maps: ${eng}`;
  renderOverview(stats);
  await renderLeads();
  await renderJobs();
}

function renderOverview(stats) {
  if (!stats) return api("/api/stats").then(renderOverview);
  const funnel = [
    { key: "novo", label: "Novos", hint: "Achados no Maps", view: "leads", filter: "novo" },
    { key: "redesenhado", label: "Redesenhados", hint: "Prontos p/ aaPanel", view: "leads", filter: "redesenhado" },
    { key: "publicado", label: "Publicados", hint: "DNS no ar", view: "leads", filter: "publicado" },
    { key: "proposta", label: "Propostas", hint: "Enviadas / rascunho", view: "leads", filter: "proposta" },
    { key: "fechado", label: "Fechados", hint: "Clientes", view: "leads", filter: "fechado" },
  ];

  const integ = (state.integrations?.funnel || [])
    .map(
      (f) => `
      <div class="integ-row">
        <span class="dot ${f.ready ? "on" : ""}"></span>
        <div>
          <strong>${esc(f.label)}</strong>
          <div class="muted small">${esc(f.detail)}</div>
        </div>
        <span class="pill">${f.ready ? "ok" : "configurar"}</span>
      </div>`
    )
    .join("");

  $("#view-overview").innerHTML = `
    <div class="funnel">
      ${funnel
        .map(
          (f) => `
        <button type="button" class="funnel-step" data-jump="${f.filter}">
          <div class="n">${stats[f.key] ?? 0}</div>
          <div class="lbl">${f.label}</div>
          <div class="hint">${f.hint}</div>
        </button>`
        )
        .join("")}
    </div>

    <div class="panel">
      <h3 style="margin-top:0">Como funciona</h3>
      <ol class="clean" style="margin:0;padding-left:18px;line-height:1.7;color:var(--muted)">
        <li><strong style="color:var(--ink)">Prospectar</strong> — Google Maps (Places/Apify): nota alta + muitas avaliações + site fraco + e-mail.</li>
        <li><strong style="color:var(--ink)">Redesenhar</strong> — gera site premium em <code>sites/slug/</code>.</li>
        <li><strong style="color:var(--ink)">Publicar</strong> — sobe no aaPanel local e cria CNAME no Cloudflare (<code>slug.iabotz.online</code>).</li>
        <li><strong style="color:var(--ink)">Proposta</strong> — rascunho no Gmail via Composio (ou arquivo em <code>drafts/</code> se Composio não estiver ligado).</li>
      </ol>
    </div>

    <div class="panel">
      <div class="row between" style="margin-bottom:12px">
        <h3 style="margin:0">Integrações</h3>
        <button class="btn ghost sm" type="button" id="goto-cfg">Abrir config</button>
      </div>
      <div class="integ">${integ || "<p class='muted'>Sem status</p>"}</div>
    </div>

    <div class="grid" style="margin-top:14px">
      <div class="stat"><span class="muted">Leads ativos</span><strong>${(stats.total || 0) - (stats.descartado || 0)}</strong></div>
      <div class="stat"><span class="muted">Jobs na fila</span><strong>${stats.jobs_queued ?? 0}</strong></div>
      <div class="stat"><span class="muted">Rodando</span><strong>${stats.jobs_running ?? 0}</strong></div>
    </div>`;

  $$("[data-jump]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.jump;
      showView("leads");
      renderLeads();
    })
  );
  $("#goto-cfg")?.addEventListener("click", () => {
    showView("config");
    renderConfig();
  });
}

function renderProspectForm(activeJobType = "prospectar") {
  const isProspect = activeJobType === "prospectar" || !activeJobType;
  $("#view-prospect").innerHTML = `
    <div class="panel">
      <p class="muted" style="margin-top:0">
        Busca negócios no <strong style="color:var(--ink)">Google Maps</strong>, filtra por nota/avaliações,
        analisa o site e só salva quem tem site fraco + e-mail público.
      </p>
      <form id="prospect-form" class="stack">
        <div class="row">
          <label style="flex:1">Nicho
            <input name="nicho" value="nutricionistas" required />
          </label>
          <label style="flex:1">Cidade
            <input name="cidade" value="Rio de Janeiro" required />
          </label>
          <label>Meta de leads
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
          <label>LLM
            <select name="provider" id="provider-select"><option value="">default</option></select>
          </label>
        </div>
        <button class="btn primary" type="submit" id="btn-prospect">Disparar prospecção</button>
      </form>
    </div>

    <div class="panel" id="run-panel">
      <div class="run-head">
        <h3 style="margin:0" id="run-title">${isProspect ? "Andamento da prospecção" : `Job: ${esc(activeJobType)}`}</h3>
        <span class="muted small" id="run-job-label">Nenhuma rodada ainda</span>
      </div>
      <ol class="steps" id="run-steps">
        ${
          isProspect
            ? `
        <li data-step="start" class="step"><span class="step-num">0</span><div><strong>Preparar</strong><div class="muted small">Critérios e motor</div></div></li>
        <li data-step="search" class="step"><span class="step-num">1</span><div><strong>Buscar no Maps</strong><div class="muted small">Places / Apify</div></div></li>
        <li data-step="filter" class="step"><span class="step-num">2</span><div><strong>Filtrar potencial</strong><div class="muted small">Nota, avaliações, tem site</div></div></li>
        <li data-step="qualify" class="step"><span class="step-num">3</span><div><strong>Analisar sites</strong><div class="muted small">Site ruim + e-mail</div></div></li>
        <li data-step="save" class="step"><span class="step-num">4</span><div><strong>Salvar leads</strong><div class="muted small">Resumo final</div></div></li>`
            : `
        <li data-step="start" class="step"><span class="step-num">1</span><div><strong>Iniciar</strong><div class="muted small">Fila</div></div></li>
        <li data-step="run" class="step"><span class="step-num">2</span><div><strong>Executar</strong><div class="muted small">Script do funil</div></div></li>
        <li data-step="save" class="step"><span class="step-num">3</span><div><strong>Finalizar</strong><div class="muted small">Atualiza status do lead</div></div></li>`
        }
      </ol>
      <div class="grid counters ${isProspect ? "" : "hidden"}" id="run-counters">
        <div class="stat"><span class="muted">No Maps</span><strong id="c-candidates">—</strong></div>
        <div class="stat"><span class="muted">Para analisar</span><strong id="c-qualify">—</strong></div>
        <div class="stat"><span class="muted">Leads ouro</span><strong id="c-qualified">—</strong></div>
        <div class="stat"><span class="muted">Descartados</span><strong id="c-discarded">—</strong></div>
      </div>
      <div id="run-summary" class="summary hidden"></div>
      <details class="log-wrap" open>
        <summary>Log detalhado</summary>
        <div class="log" id="job-log">Aguardando job…</div>
      </details>
    </div>`;

  fillProviders();
  $("#prospect-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#btn-prospect");
    btn.disabled = true;
    btn.textContent = "Rodando…";
    try {
      const fd = new FormData(e.target);
      const payload = Object.fromEntries(fd.entries());
      payload.meta = Number(payload.meta);
      payload.notaMinima = Number(payload.notaMinima);
      payload.avaliacoesMinimas = Number(payload.avaliacoesMinimas);
      const body = { type: "prospectar", payload, provider: payload.provider || null };
      resetRunUI();
      const res = await api("/api/jobs", { method: "POST", body: JSON.stringify(body) });
      await watchJob(res.id, "prospectar");
    } catch (err) {
      appendLog(`Erro: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = "Disparar prospecção";
    }
  });
}

function resetRunUI() {
  $$("#run-steps .step").forEach((el) => el.classList.remove("active", "done"));
  ["c-candidates", "c-qualify", "c-qualified", "c-discarded"].forEach((id) => {
    const el = $(`#${id}`);
    if (el) el.textContent = "—";
  });
  const box = $("#run-summary");
  if (box) {
    box.classList.add("hidden");
    box.innerHTML = "";
  }
  const log = $("#job-log");
  if (log) log.textContent = "";
}

function setStep(key) {
  const order = ["start", "search", "filter", "qualify", "run", "save", "done"];
  const idx = order.indexOf(key);
  $$("#run-steps .step").forEach((el) => {
    const s = el.dataset.step;
    const i = order.indexOf(s);
    el.classList.toggle("done", idx > i || key === "done");
    el.classList.toggle("active", s === key && key !== "done");
  });
}

function applyRunMessage(msg, jobType) {
  if (!msg) return;
  if (msg.startsWith("STEP:")) {
    const [left, ...rest] = msg.split("|");
    const key = left.slice(5);
    const label = rest.join("|");
    setStep(key === "done" ? "done" : key);
    if (label) appendLog(label);
    return;
  }
  if (msg.startsWith("COUNT:")) {
    const body = msg.slice(6);
    body.split(",").forEach((part) => {
      const [k, v] = part.split("=");
      if (k === "candidates" && $("#c-candidates")) $("#c-candidates").textContent = v;
      if (k === "to_qualify" && $("#c-qualify")) $("#c-qualify").textContent = v;
      if (k === "qualified" && $("#c-qualified")) $("#c-qualified").textContent = v;
      if (k === "discarded" && $("#c-discarded")) $("#c-discarded").textContent = v;
    });
    return;
  }
  if (jobType && jobType !== "prospectar") {
    if (/inici|execut|rodando|deploy|cloudflare|dns|copi|nginx/i.test(msg)) setStep("run");
    if (/sucesso|conclu|publicado|rascunho|✓|✅/i.test(msg)) setStep("save");
  }
  appendLog(msg);
}

function appendLog(msg) {
  const log = $("#job-log");
  if (!log) return;
  log.textContent += msg + "\n";
  log.scrollTop = log.scrollHeight;
}

function showJobSummary(job) {
  let result = {};
  try {
    result = typeof job.result === "string" ? JSON.parse(job.result || "{}") : job.result || {};
  } catch (_) {}
  const box = $("#run-summary");
  if (!box) return;

  if (job.status === "failed") {
    box.classList.remove("hidden");
    box.innerHTML = `<strong class="error">Falhou</strong><p class="muted">${esc(job.error || "erro")}</p>`;
    setStep("done");
    return;
  }

  if (job.type === "prospectar" && (result.candidates != null || result.qualified_count != null)) {
    if (result.candidates != null) $("#c-candidates").textContent = result.candidates;
    if (result.to_qualify != null) $("#c-qualify").textContent = result.to_qualify;
    if (result.qualified_count != null) $("#c-qualified").textContent = result.qualified_count;
    if (result.discarded_count != null) $("#c-discarded").textContent = result.discarded_count;
    setStep("done");
    const leads = (result.qualified || [])
      .map((q) => `<li><strong>${esc(q.nome)}</strong> — <span class="muted">${esc(q.motivo || "")}</span></li>`)
      .join("");
    const reasons = Object.entries(result.discard_reasons || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([k, v]) => `<li>${esc(k)} <span class="pill">${v}</span></li>`)
      .join("");
    box.classList.remove("hidden");
    box.innerHTML = `
      <strong>Resumo</strong>
      <p>
        Encontrou <strong>${result.candidates ?? "—"}</strong> no Maps (${esc(result.engine || "")}).
        Analisou <strong>${result.to_qualify ?? "—"}</strong> sites.
        Salvou <strong>${result.qualified_count ?? 0}</strong> leads ouro
        e descartou <strong>${result.discarded_count ?? 0}</strong>.
      </p>
      ${leads ? `<p class="muted small" style="margin-bottom:4px">Leads salvos</p><ul class="clean">${leads}</ul>` : "<p class='muted'>Nenhum lead ouro nesta rodada.</p>"}
      ${reasons ? `<p class="muted small" style="margin-bottom:4px">Principais descartes</p><ul class="clean">${reasons}</ul>` : ""}
      <button class="btn ghost" id="goto-leads" type="button">Ver leads</button>`;
    $("#goto-leads")?.addEventListener("click", () => {
      showView("leads");
      renderLeads();
    });
    return;
  }

  setStep("done");
  box.classList.remove("hidden");
  const labels = {
    redesenhar: "Site redesenhado. Próximo: Publicar + DNS.",
    publicar: "Publicado no aaPanel e DNS Cloudflare. Próximo: Proposta.",
    proposta: "Rascunho de proposta gerado (Gmail/Composio ou drafts/).",
  };
  box.innerHTML = `
    <strong class="ok">Concluído</strong>
    <p class="muted">${esc(labels[job.type] || "Job finalizado.")}</p>
    <button class="btn ghost" id="goto-leads" type="button">Ver leads</button>`;
  $("#goto-leads")?.addEventListener("click", () => {
    showView("leads");
    renderLeads();
  });
}

async function watchJob(id, jobType = "prospectar") {
  if (state.es) state.es.close();
  $("#run-job-label").textContent = `Job #${id}`;
  if ($("#run-title")) {
    $("#run-title").textContent =
      jobType === "prospectar" ? "Andamento da prospecção" : `Job: ${jobType}`;
  }
  resetRunUI();
  setStep("start");
  appendLog(`Job #${id} (${jobType})…`);

  let lastId = 0;
  try {
    const job = await api(`/api/jobs/${id}`);
    jobType = job.type || jobType;
    (job.events || []).forEach((ev) => {
      lastId = Math.max(lastId, ev.id || 0);
      applyRunMessage(ev.message, jobType);
    });
    if (["succeeded", "failed", "cancelled"].includes(job.status)) {
      showJobSummary(job);
      return job;
    }
  } catch (_) {}

  return new Promise((resolve) => {
    state.es = new EventSource(`/api/jobs/${id}/events?after=${lastId}`);
    state.es.onmessage = async (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.done) {
          state.es.close();
          const job = await api(`/api/jobs/${id}`);
          showJobSummary(job);
          appendLog(`— fim (${data.status}) —`);
          renderLeads();
          renderJobs();
          resolve(job);
          return;
        }
        if (data.id) lastId = data.id;
        if (data.message) applyRunMessage(data.message, jobType);
      } catch (_) {}
    };
  });
}

function fillProviders() {
  const sel = $("#provider-select");
  if (!sel || sel.options.length > 1) return;
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
  const filters = [
    { id: "ativos", label: "Ativos" },
    { id: "novo", label: "Novos" },
    { id: "redesenhado", label: "Redesenhar" },
    { id: "publicado", label: "Publicados" },
    { id: "proposta", label: "Propostas" },
    { id: "fechado", label: "Fechados" },
    { id: "todos", label: "Todos" },
  ];

  let list = state.leads;
  if (state.filter === "ativos") list = list.filter((l) => l.status !== "descartado");
  else if (state.filter !== "todos") list = list.filter((l) => l.status === state.filter);

  const rows = list
    .slice(0, 80)
    .map((l) => {
      const next = nextAction(l);
      return `
      <tr class="clickable" data-open="${esc(l.slug)}">
        <td>
          <strong>${esc(l.nome)}</strong>
          <div class="muted small">${esc(l.nicho || "")} · ${esc(l.cidade || "")}</div>
          <div class="next-hint">${esc(next.label)}</div>
        </td>
        <td>${l.nota ?? "—"}<div class="muted small">${l.avaliacoes ?? 0} aval.</div></td>
        <td><span class="pill ${esc(l.status)}">${esc(l.status)}</span></td>
        <td class="small">${esc(l.email || "—")}</td>
        <td onclick="event.stopPropagation()">
          ${
            !next.disabled && next.type
              ? `<button class="btn primary sm" data-act="${esc(next.type)}" data-slug="${esc(l.slug)}">${esc(next.label)}</button>`
              : `<button class="btn ghost sm" data-open-btn="${esc(l.slug)}">Detalhe</button>`
          }
        </td>
      </tr>`;
    })
    .join("");

  $("#view-leads").innerHTML = `
    <div class="panel">
      <div class="filters">
        ${filters
          .map(
            (f) =>
              `<button type="button" class="chip ${state.filter === f.id ? "active" : ""}" data-filter="${f.id}">${f.label}</button>`
          )
          .join("")}
        <button class="btn ghost sm" id="refresh-leads" type="button">Atualizar</button>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Lead · próximo passo</th>
            <th>Maps</th>
            <th>Status</th>
            <th>E-mail</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody>${rows || "<tr><td colspan=5>Nenhum lead neste filtro</td></tr>"}</tbody>
      </table>
    </div>`;

  $$("[data-filter]").forEach((b) =>
    b.addEventListener("click", () => {
      state.filter = b.dataset.filter;
      renderLeads();
    })
  );
  $("#refresh-leads")?.addEventListener("click", renderLeads);
  $$("[data-open]").forEach((tr) =>
    tr.addEventListener("click", () => {
      const lead = state.leads.find((x) => x.slug === tr.dataset.open);
      if (lead) openDrawer(lead);
    })
  );
  $$("[data-open-btn]").forEach((b) =>
    b.addEventListener("click", () => {
      const lead = state.leads.find((x) => x.slug === b.dataset.openBtn);
      if (lead) openDrawer(lead);
    })
  );
  $$("[data-act]").forEach((btn) =>
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      startJob(btn.dataset.act, btn.dataset.slug);
    })
  );
}

async function renderJobs() {
  state.jobs = await api("/api/jobs?limit=40");
  const rows = state.jobs
    .map(
      (j) => `
    <tr>
      <td>#${j.id}</td>
      <td>${esc(j.type)}</td>
      <td><span class="pill ${esc(j.status)}">${esc(j.status)}</span></td>
      <td class="small">${esc(j.created_at || "")}</td>
      <td class="row">
        <button class="btn ghost sm" data-watch="${j.id}" data-type="${esc(j.type)}">Ver</button>
        ${
          j.status === "queued" || j.status === "running"
            ? `<button class="btn danger sm" data-cancel="${j.id}">Cancelar</button>`
            : ""
        }
      </td>
    </tr>`
    )
    .join("");
  $("#view-jobs").innerHTML = `
    <div class="panel">
      <table class="table">
        <thead><tr><th>ID</th><th>Tipo</th><th>Status</th><th>Criado</th><th></th></tr></thead>
        <tbody>${rows || "<tr><td colspan=5>Sem jobs</td></tr>"}</tbody>
      </table>
    </div>`;
  $$("[data-watch]").forEach((b) =>
    b.addEventListener("click", async () => {
      showView("prospect");
      renderProspectForm(b.dataset.type);
      await watchJob(Number(b.dataset.watch), b.dataset.type);
    })
  );
  $$("[data-cancel]").forEach((b) =>
    b.addEventListener("click", async () => {
      await api(`/api/jobs/${b.dataset.cancel}/cancel`, { method: "POST", body: "{}" });
      renderJobs();
    })
  );
}

function val(id, fallback = "") {
  const el = $(id);
  return el ? el.value : fallback;
}

async function renderConfig() {
  state.config = await api("/api/config");
  state.integrations = await api("/api/config/integrations").catch(() => state.integrations);
  const c = state.config;
  const m = c.maps || {};
  const llm = c.llm || {};
  const a = c.assinatura || {};
  const aa = c.aapanel || {};
  const cf = c.cloudflare || {};
  const co = c.composio || {};
  const envio = c.envio || {};
  const ready = Object.fromEntries((state.integrations?.funnel || []).map((f) => [f.id, f.ready]));

  $("#view-config").innerHTML = `
    <div class="cfg-grid">
      <div class="panel cfg-card stack">
        <h3>Assinatura <span class="tag">e-mails</span></h3>
        <div class="row">
          <label style="flex:1">Nome<input id="cfg-nome" value="${esc(a.nome || "")}" /></label>
          <label style="flex:1">WhatsApp<input id="cfg-wa" value="${esc(a.whatsapp || "")}" /></label>
          <label style="flex:1">E-mail remete<input id="cfg-email" value="${esc(a.email || "")}" placeholder="voce@gmail.com" /></label>
        </div>
        <label>Apresentação<textarea id="cfg-apres" rows="2">${esc(a.apresentacao || "")}</textarea></label>
      </div>

      <div class="panel cfg-card stack">
        <h3>1 · Google Maps <span class="tag ${ready.maps ? "on" : "off"}">${ready.maps ? "conectado" : "faltando"}</span></h3>
        <p class="muted small" style="margin:0">Places (oficial) ou Apify (scraping). Engine auto tenta Places e cai no Apify.</p>
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
          <button class="btn ghost sm" type="button" id="test-places">Testar Places</button>
          <button class="btn ghost sm" type="button" id="test-apify">Testar Apify</button>
        </div>
      </div>

      <div class="panel cfg-card stack">
        <h3>3 · aaPanel (publicar) <span class="tag ${ready.aapanel ? "on" : "off"}">${ready.aapanel ? "ok" : "faltando"}</span></h3>
        <p class="muted small" style="margin:0">Publicação local em <code>/www/wwwroot/</code> com nginx do aaPanel. URL: <code>{slug}.{dominio_base}</code> (use <code>iabotz.online</code> — Universal SSL não cobre <code>*.panel.iabotz.online</code>).</p>
        <div class="row">
          <label style="flex:1">URL painel<input id="cfg-aa-url" value="${esc(aa.url || "")}" /></label>
          <label style="flex:1">Domínio base<input id="cfg-aa-dom" value="${esc(aa.dominio_base || "iabotz.online")}" /></label>
          <label style="flex:1">DNS target<input id="cfg-aa-dns" value="${esc(aa.dns_target || "panel.iabotz.online")}" /></label>
        </div>
        <div class="row">
          <label>Subdomínio?
            <select id="cfg-aa-sub">
              <option value="true">sim (recomendado)</option>
              <option value="false">não (subpasta)</option>
            </select>
          </label>
          <label style="flex:1">API token (opcional)<input id="cfg-aa-token" type="password" value="${esc(aa.api_token || "")}" placeholder="vazio = modo local sudo" /></label>
          <label>SSL auto
            <select id="cfg-aa-ssl">
              <option value="true">sim</option>
              <option value="false">não</option>
            </select>
          </label>
        </div>
      </div>

      <div class="panel cfg-card stack">
        <h3>4 · Cloudflare DNS <span class="tag ${ready.cloudflare ? "on" : "off"}">${ready.cloudflare ? "conectado" : "faltando"}</span></h3>
        <p class="muted small" style="margin:0">Ao publicar, cria CNAME <code>{slug}</code> → <code>panel.iabotz.online</code> (URL final <code>https://{slug}.iabotz.online</code>).</p>
        <div class="row">
          <label style="flex:1">API Key / Token<input id="cfg-cf-key" type="password" value="${esc(cf.api_key || cf.api_token || "")}" /></label>
          <label style="flex:1">E-mail conta<input id="cfg-cf-email" value="${esc(cf.email || "")}" /></label>
          <label style="flex:1">Zona<input id="cfg-cf-zone" value="${esc(cf.zone || "iabotz.online")}" /></label>
        </div>
        <div class="row">
          <button class="btn ghost sm" type="button" id="test-cf">Testar Cloudflare</button>
        </div>
      </div>

      <div class="panel cfg-card stack">
        <h3>5 · Gmail via Composio <span class="tag ${ready.gmail ? "on" : "off"}">${ready.gmail ? "conectado" : "draft local"}</span></h3>
        <p class="muted small" style="margin:0">
          Originalmente usamos <strong style="color:var(--ink)">Composio</strong> para criar rascunhos no Gmail.
          Sem API key, a proposta salva HTML em <code>drafts/</code> para você colar no Gmail.
        </p>
        <div class="row">
          <label style="flex:1">Composio API Key<input id="cfg-co-key" type="password" value="${esc(co.api_key || "")}" placeholder="COMPOSIO_API_KEY" /></label>
          <label style="flex:1">Entity ID<input id="cfg-co-entity" value="${esc(co.entity_id || "")}" placeholder="default" /></label>
          <label>Modo envio
            <select id="cfg-envio">
              <option value="rascunho">rascunho (recomendado)</option>
              <option value="enviar">enviar direto</option>
            </select>
          </label>
        </div>
      </div>

      <div class="panel cfg-card stack">
        <h3>LLM (redesign / copy) <span class="tag on">opcional</span></h3>
        <div class="row">
          <label style="flex:1">OpenRouter Key<input id="cfg-or" type="password" value="${esc(llm.openrouter_api_key || "")}" /></label>
          <label style="flex:1">Modelo<input id="cfg-ormodel" value="${esc(llm.openrouter_model || "openai/gpt-4o-mini")}" /></label>
          <label>Provider<select id="cfg-prov">
            <option value="openrouter">openrouter</option>
            <option value="claude">claude</option>
            <option value="codex">codex</option>
            <option value="cursor">cursor</option>
          </select></label>
        </div>
        <div id="providers-status" class="muted small"></div>
      </div>

      <div class="row">
        <button class="btn primary" id="save-cfg" type="button">Salvar tudo</button>
        <div id="cfg-msg" class="muted"></div>
      </div>
    </div>`;

  $("#cfg-engine").value = m.engine || "auto";
  $("#cfg-prov").value = llm.default_provider || "openrouter";
  $("#cfg-aa-sub").value = String(aa.usar_subdominio !== false);
  $("#cfg-aa-ssl").value = String(aa.ssl_auto !== false);
  $("#cfg-envio").value = envio.modo || "rascunho";
  $("#providers-status").textContent = state.providers
    .map((x) => `${x.name}: ${x.available ? "ok" : "off"}`)
    .join(" · ");

  const msg = (t) => {
    $("#cfg-msg").textContent = t;
  };

  $("#save-cfg").onclick = async () => {
    const cfKey = val("#cfg-cf-key");
    const body = {
      assinatura: {
        nome: val("#cfg-nome"),
        whatsapp: val("#cfg-wa"),
        email: val("#cfg-email"),
        apresentacao: val("#cfg-apres"),
      },
      maps: {
        google_maps_api_key: val("#cfg-gmaps") || "***",
        apify_api_key: val("#cfg-apify") || "***",
        engine: val("#cfg-engine"),
      },
      aapanel: {
        url: val("#cfg-aa-url"),
        dominio_base: val("#cfg-aa-dom"),
        dns_target: val("#cfg-aa-dns"),
        usar_subdominio: val("#cfg-aa-sub") === "true",
        ssl_auto: val("#cfg-aa-ssl") === "true",
        api_token: val("#cfg-aa-token") || "***",
      },
      cloudflare: {
        api_key: cfKey || "***",
        email: val("#cfg-cf-email"),
        zone: val("#cfg-cf-zone"),
        proxied: true,
      },
      composio: {
        api_key: val("#cfg-co-key") || "***",
        entity_id: val("#cfg-co-entity"),
      },
      envio: { modo: val("#cfg-envio") },
      llm: {
        openrouter_api_key: val("#cfg-or") || "***",
        openrouter_model: val("#cfg-ormodel"),
        default_provider: val("#cfg-prov"),
      },
    };
    await api("/api/config", { method: "POST", body: JSON.stringify(body) });
    state.providers = await api("/api/providers");
    state.integrations = await api("/api/config/integrations");
    msg("Salvo.");
    toast("Configurações salvas");
  };

  $("#test-places").onclick = async () => {
    const r = await api("/api/config/engines/test", {
      method: "POST",
      body: JSON.stringify({ engine: "google_places" }),
    });
    msg(r.message || JSON.stringify(r));
  };
  $("#test-apify").onclick = async () => {
    const r = await api("/api/config/engines/test", {
      method: "POST",
      body: JSON.stringify({ engine: "apify" }),
    });
    msg(r.message || JSON.stringify(r));
  };
  $("#test-cf").onclick = async () => {
    const r = await api("/api/config/cloudflare/test", { method: "POST", body: "{}" });
    msg(r.message || JSON.stringify(r));
  };
}

boot().catch((e) => console.error(e));
