const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

const STATUS_LABEL = {
  novo: "Novo",
  redesenhado: "Redesenhado",
  publicado: "Publicado",
  proposta: "Proposta",
  proposta_whatsapp: "Proposta WhatsApp",
  respondeu: "Respondeu",
  fechado: "Fechado",
  descartado: "Descartado",
  queued: "Na fila",
  running: "Rodando",
  succeeded: "OK",
  failed: "Falhou",
  cancelled: "Cancelado",
};

const JOB_LABEL = {
  prospectar: "Prospecção",
  redesenhar: "Redesign",
  publicar: "Publicar + DNS",
  proposta: "Preparar outreach",
  followup: "Follow-up",
  respostas: "Verificar respostas",
  contrato: "Contrato",
};

const PIPELINE = [
  { status: "novo", label: "Novo", next: "redesenhar", nextLabel: "Redesenhar site" },
  { status: "redesenhado", label: "Redesenhado", next: "publicar", nextLabel: "Publicar + DNS" },
  { status: "publicado", label: "Publicado", next: "proposta", nextLabel: "Gerar proposta" },
  { status: "proposta", label: "Proposta", next: null, nextLabel: "Aguardar resposta" },
  { status: "respondeu", label: "Respondeu", next: null, nextLabel: "Negociar e fechar" },
  { status: "fechado", label: "Fechado", next: null, nextLabel: "—" },
];

const NICHOS = ["nutricionistas", "psicólogos", "dentistas", "advogados", "clínicas estéticas", "personal trainers"];
const CIDADES = ["Rio de Janeiro", "São Paulo", "Belo Horizonte", "Curitiba", "Porto Alegre", "Brasília"];

const state = {
  leads: [],
  jobs: [],
  providers: [],
  config: null,
  integrations: null,
  filter: "ativos",
  search: "",
  selected: null,
  cfgTab: "llm",
  selectedProvider: null,
  emailId: null,
  orModelQuery: "",
  openrouterModels: [],
  es: null,
  jobPoll: null,
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

function statusPill(status) {
  const label = STATUS_LABEL[status] || status;
  return `<span class="pill ${esc(status)}">${esc(label)}</span>`;
}

function pipelineInfo(status) {
  return PIPELINE.find((p) => p.status === status) || {
    status,
    label: STATUS_LABEL[status] || status,
    next: null,
    nextLabel: "—",
  };
}

function nextAction(lead) {
  const info = pipelineInfo(lead.status);
  const canais = state.config?.envio?.canais || ["email"];
  const hasEmail = !!lead.email;
  const hasWhatsapp = !!(lead.whatsapp || lead.telefone);
  if (lead.status === "publicado" && !((canais.includes("email") && hasEmail) || (canais.includes("whatsapp") && hasWhatsapp))) {
    return { type: null, label: "Falta contato do canal", disabled: true };
  }
  if (!info.next) return { type: null, label: info.nextLabel, disabled: true };
  return { type: info.next, label: info.nextLabel, disabled: false };
}

function selectHtml(id, options, attrs = "") {
  const opts = options
    .map((o) => {
      if (typeof o === "string") return `<option value="${esc(o)}">${esc(o)}</option>`;
      return `<option value="${esc(o.value)}" ${o.disabled ? "disabled" : ""}>${esc(o.label)}</option>`;
    })
    .join("");
  return `<div class="select-wrap"><select id="${esc(id)}" ${attrs}>${opts}</select></div>`;
}

const VIEWS = {
  overview: { title: "Funil", sub: "Do Maps ao contato e proposta" },
  kanban: { title: "Pipeline", sub: "Arraste os leads entre as etapas comerciais" },
  prospect: { title: "Prospectar", sub: "Maps · nota · site fraco · canal configurado" },
  leads: { title: "Leads", sub: "Redesenhar → publicar → proposta" },
  followups: { title: "Follow-ups", sub: "3 dias úteis · uma tentativa por canal" },
  emails: { title: "Mensagens", sub: "E-mail e WhatsApp · rascunhos e envios" },
  outreach: { title: "Outreach", sub: "Histórico de e-mail e WhatsApp" },
  jobs: { title: "Jobs", sub: "Fila e histórico" },
  config: { title: "Config", sub: "LLM · Maps · aaPanel · Cloudflare · Gmail" },
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
    if (btn.dataset.view === "kanban") renderKanban();
    if (btn.dataset.view === "followups") renderFollowups();
    if (btn.dataset.view === "emails") renderEmails();
    if (btn.dataset.view === "outreach") renderOutreach();
    if (btn.dataset.view === "jobs") renderJobs();
    if (btn.dataset.view === "config") renderConfig();
    if (btn.dataset.view === "overview") renderOverview();
    if (btn.dataset.view === "prospect") renderProspectForm();
  })
);

$$("[data-close-drawer]").forEach((el) => el.addEventListener("click", closeDrawer));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
});

function openDrawer(lead) {
  state.selected = lead;
  const drawer = $("#drawer");
  drawer.classList.remove("hidden");
  drawer.setAttribute("aria-hidden", "false");
  $("#drawer-title").textContent = lead.nome || lead.slug;
  $("#drawer-status").innerHTML = statusPill(lead.status);

  const stages = ["novo", "redesenhado", "publicado", "proposta", "respondeu", "fechado"];
  const idx = stages.indexOf(lead.status);
  const mini = stages
    .map((s, i) => {
      const cls = i < idx ? "done" : i === idx ? "now" : "";
      return `<div class="pipeline-step ${cls}"><span class="pipeline-dot"></span><span>${esc(pipelineInfo(s).label)}</span></div>`;
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
    </div>
    <p class="muted small" style="margin:0">
      <strong style="color:var(--accent)">Próximo:</strong> ${esc(next.label)}
    </p>`;

  $("#drawer-actions").innerHTML = `
    ${!next.disabled && next.type
      ? `<button class="btn primary" data-run="${esc(next.type)}" data-slug="${esc(lead.slug)}">${esc(next.label)}</button>`
      : ""}
    ${lead.status === "novo" || lead.status === "redesenhado"
      ? `<button class="btn ghost" data-run="redesenhar" data-slug="${esc(lead.slug)}">Redesenhar</button>`
      : ""}
    ${["publicado", "proposta", "fechado"].includes(lead.status)
      ? `<button class="btn ghost" data-run="redesenhar" data-slug="${esc(lead.slug)}">Gerar nova opção</button>`
      : ""}
    ${["redesenhado", "publicado"].includes(lead.status)
      ? `<button class="btn ghost" data-run="publicar" data-slug="${esc(lead.slug)}">Publicar + DNS</button>`
      : ""}
    ${["publicado", "proposta"].includes(lead.status)
      ? `<button class="btn ghost" data-run="proposta" data-slug="${esc(lead.slug)}">Preparar outreach</button>`
      : ""}
    ${lead.urlNova ? `<a class="btn ghost" href="${esc(lead.urlNova)}" target="_blank" rel="noopener">Abrir site</a>` : ""}
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
    const provider = state.selectedProvider || state.config?.llm?.default_provider || null;
    const res = await api("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ type, payload: { slug }, provider }),
    });
    toast(`${JOB_LABEL[type] || type} · ${slug}`);
    await watchJob(res.id, type);
  } catch (err) {
    appendLog(`Erro: ${err.message}`);
    toast(err.message);
  }
}

async function boot() {
  renderProspectForm();
  const [stats, engines, providers, integ, cfg] = await Promise.all([
    api("/api/stats"),
    api("/api/config/engines"),
    api("/api/providers"),
    api("/api/config/integrations").catch(() => ({ funnel: [] })),
    api("/api/config").catch(() => ({})),
  ]);
  state.providers = providers;
  state.integrations = integ;
  state.config = cfg;
  state.selectedProvider = cfg?.llm?.default_provider || "openrouter";
  const eng = engines.default || "nenhum";
  const llm = providers.find((p) => p.id === state.selectedProvider);
  $("#engine-badge").textContent = `Maps: ${eng} · LLM: ${llm?.name || state.selectedProvider}${llm?.available ? "" : " ✕"}`;
  renderOverview(stats);
  await renderLeads();
  await renderJobs();
  // Overview counters must reflect jobs that complete in another tab/worker,
  // not only the initial page load or the currently watched EventSource.
  setInterval(() => {
    api("/api/stats").then(renderOverview).catch(() => {});
  }, 5000);
}

function renderOverview(stats) {
  if (!stats) return api("/api/stats").then(renderOverview);
  const funnel = [
    { key: "novo", label: "Novos", hint: "Do Maps", filter: "novo" },
    { key: "redesenhado", label: "Redesenhados", hint: "Prontos p/ aaPanel", filter: "redesenhado" },
    { key: "publicado", label: "Publicados", hint: "DNS no ar", filter: "publicado" },
    { key: "proposta", label: "Propostas", hint: "Rascunho / Gmail", filter: "proposta" },
    { key: "respondeu", label: "Responderam", hint: "Em negociação", filter: "respondeu" },
    { key: "fechado", label: "Fechados", hint: "Clientes", filter: "fechado" },
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
        ${f.ready
          ? '<span class="status-pill live"><span class="sdot"></span>ok</span>'
          : '<span class="status-pill dead"><span class="sdot"></span>configurar</span>'}
      </div>`
    )
    .join("");

  const llmCards = (state.providers || [])
    .map((p) => {
      const live = p.available;
      return `<div class="integ-row">
        <span class="dot ${live ? "on" : ""}"></span>
        <div>
          <strong>${esc(p.name)}</strong>
          <div class="muted small">${esc(p.detail || (live ? "Pronto" : "Não detectado / sem key"))}</div>
        </div>
        <span class="status-pill ${live ? "live" : "dead"}"><span class="sdot"></span>${live ? "detectado" : "off"}</span>
      </div>`;
    })
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
      <ol style="margin:0;padding-left:18px;line-height:1.75;color:var(--muted)">
        <li><strong style="color:var(--ink)">Prospectar</strong> — Google Maps (nota + avaliações + site fraco + e-mail).</li>
        <li><strong style="color:var(--ink)">Redesenhar</strong> — gera site em <code>sites/</code> (LLM opcional para copy).</li>
        <li><strong style="color:var(--ink)">Publicar</strong> — hosting + DNS configurados → <code>{slug}.{dominio}</code>.</li>
        <li><strong style="color:var(--ink)">Proposta</strong> — Composio/Gmail ou draft em <code>drafts/</code>.</li>
      </ol>
    </div>

    <div class="row" style="align-items:stretch;margin-top:14px">
      <div class="panel" style="flex:1;margin-top:0">
        <div class="row between" style="margin-bottom:12px">
          <h3 style="margin:0">Integrações</h3>
          <button class="btn ghost sm" type="button" id="goto-cfg">Config</button>
        </div>
        <div class="integ">${integ || "<p class='muted'>—</p>"}</div>
      </div>
      <div class="panel" style="flex:1;margin-top:0">
        <div class="row between" style="margin-bottom:12px">
          <h3 style="margin:0">LLM / CLIs</h3>
          <button class="btn ghost sm" type="button" id="goto-llm">Escolher</button>
        </div>
        <div class="integ">${llmCards || "<p class='muted'>—</p>"}</div>
      </div>
    </div>`;

  $$("[data-jump]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.jump;
      showView("leads");
      renderLeads();
    })
  );
  $("#goto-cfg")?.addEventListener("click", () => {
    state.cfgTab = "maps";
    showView("config");
    renderConfig();
  });
  $("#goto-llm")?.addEventListener("click", () => {
    state.cfgTab = "llm";
    showView("config");
    renderConfig();
  });
}

async function renderKanban() {
  state.leads = await api("/api/leads");
  const dueData = await api("/api/followups").catch(() => ({ leads: [] }));
  const due = new Map((dueData.leads || []).map((lead) => [lead.slug, lead]));
  const columns = ["novo", "redesenhado", "publicado", "proposta", "respondeu", "fechado", "descartado"];
  const cardsByStatus = Object.fromEntries(columns.map((status) => [status, []]));
  state.leads.forEach((lead) => (cardsByStatus[lead.status] || cardsByStatus.novo).push(lead));

  const board = columns.map((status) => {
    const cards = cardsByStatus[status].map((lead) => {
      const pending = due.get(lead.slug);
      const followupBadge = pending
        ? `<span class="kanban-alert">Follow-up ${Math.max(pending.email_days || 0, pending.whatsapp_days || 0)}d</span>`
        : "";
      const prepared = lead.proposalPreparedAt && !lead.dataProposta
        ? '<span class="kanban-prepared">Outreach preparado</span>' : "";
      return `<article class="kanban-card" draggable="true" data-kanban-card="${esc(lead.slug)}">
        <div class="row between"><strong>${esc(lead.nome)}</strong>${followupBadge}</div>
        <div class="muted small">${esc(lead.nicho || "Sem nicho")} · ${esc(lead.cidade || "—")}</div>
        ${lead.nota ? `<div class="kanban-rating">★ ${esc(lead.nota)} <span>${esc(lead.avaliacoes || 0)} avaliações</span></div>` : ""}
        ${prepared}
        ${lead.responseSummary ? `<p class="kanban-response">${esc(lead.responseSummary)}</p>` : ""}
        <div class="row">
          <button class="btn ghost sm" type="button" data-kanban-open="${esc(lead.slug)}">Ver lead</button>
          <select class="kanban-move" data-kanban-move="${esc(lead.slug)}" aria-label="Mover ${esc(lead.nome)}">
            ${columns.map((option) => `<option value="${option}" ${option === lead.status ? "selected" : ""}>${esc(STATUS_LABEL[option] || option)}</option>`).join("")}
          </select>
        </div>
      </article>`;
    }).join("");
    return `<section class="kanban-column" data-kanban-status="${status}">
      <header><span>${esc(STATUS_LABEL[status] || status)}</span><b>${cardsByStatus[status].length}</b></header>
      <div class="kanban-cards">${cards || '<div class="kanban-empty">Solte aqui</div>'}</div>
    </section>`;
  }).join("");

  $("#view-kanban").innerHTML = `
    <div class="row between kanban-toolbar">
      <p class="muted small">Arraste para atualizar a etapa. ` +
      `Mover para <strong>Proposta</strong> marca o contato como enviado manualmente; <strong>Respondeu</strong> interrompe follow-ups.</p>
      <button class="btn ghost sm" id="refresh-kanban" type="button">Atualizar</button>
    </div>
    <div class="kanban-board">${board}</div>`;

  let dragged = null;
  $$('[data-kanban-card]').forEach((card) => {
    card.addEventListener("dragstart", () => { dragged = card.dataset.kanbanCard; card.classList.add("dragging"); });
    card.addEventListener("dragend", () => { dragged = null; card.classList.remove("dragging"); });
  });
  $$('[data-kanban-status]').forEach((column) => {
    column.addEventListener("dragover", (event) => { event.preventDefault(); column.classList.add("drop-target"); });
    column.addEventListener("dragleave", () => column.classList.remove("drop-target"));
    column.addEventListener("drop", async (event) => {
      event.preventDefault(); column.classList.remove("drop-target");
      if (!dragged) return;
      const status = column.dataset.kanbanStatus;
      if (status === "proposta" && !confirm("Confirma que a proposta foi realmente enviada? Isso inicia a contagem de 3 dias úteis para follow-up.")) return;
      const update = { status };
      if (status === "fechado") {
        const value = prompt("Valor fechado (opcional):", "");
        if (value && !Number.isNaN(Number(value.replace(",", ".")))) update.valor = Number(value.replace(",", "."));
      }
      await api(`/api/leads/${encodeURIComponent(dragged)}`, { method: "PUT", body: JSON.stringify(update) });
      toast(`Lead movido para ${STATUS_LABEL[status] || status}`);
      await renderKanban();
    });
  });
  $$('[data-kanban-open]').forEach((button) => button.addEventListener("click", () => {
    const lead = state.leads.find((item) => item.slug === button.dataset.kanbanOpen);
    if (lead) openDrawer(lead);
  }));
  $$('[data-kanban-move]').forEach((select) => select.addEventListener("change", async () => {
    const status = select.value;
    if (status === "proposta" && !confirm("Confirma que a proposta foi realmente enviada? Isso inicia a contagem para follow-up.")) {
      await renderKanban(); return;
    }
    await api(`/api/leads/${encodeURIComponent(select.dataset.kanbanMove)}`, { method: "PUT", body: JSON.stringify({ status }) });
    toast(`Lead movido para ${STATUS_LABEL[status] || status}`);
    await renderKanban();
  }));
  $("#refresh-kanban")?.addEventListener("click", renderKanban);
}

async function renderFollowups() {
  const data = await api("/api/followups");
  const cards = (data.leads || []).map((lead) => `
    <article class="followup-card">
      <div>
        <div class="row"><strong>${esc(lead.nome)}</strong>${statusPill(lead.status)}</div>
        <p class="muted small">Proposta: ${esc(lead.dataProposta || lead.emailSentAt || lead.whatsappSentAt || "—")}</p>
      </div>
      <div class="followup-channels">
        ${lead.due_email ? `<span>@ E-mail · ${lead.email_days} dias úteis</span>` : ""}
        ${lead.due_whatsapp ? `<span>WA WhatsApp · ${lead.whatsapp_days} dias úteis</span>` : ""}
      </div>
      <button class="btn primary sm" data-followup="${esc(lead.slug)}" type="button">Preparar follow-up</button>
    </article>`).join("");
  $("#view-followups").innerHTML = `
    <div class="followup-hero">
      <div><span class="eyebrow">ACOMPANHAMENTO</span><h2>${data.count || 0} follow-up(s) pendente(s)</h2>
      <p>Antes de criar qualquer mensagem, o sistema verifica respostas no Gmail. Cada canal recebe no máximo um follow-up.</p></div>
      <div class="row">
        <button class="btn ghost" id="check-replies" type="button">Verificar respostas</button>
        <button class="btn primary" id="run-all-followups" type="button" ${data.count ? "" : "disabled"}>Preparar todos</button>
      </div>
    </div>
    <div class="followup-list">${cards || '<div class="empty"><strong>Nada pendente</strong>Nenhum lead completou 3 dias úteis sem resposta.</div>'}</div>`;
  $$('[data-followup]').forEach((button) => button.addEventListener("click", () => startJob("followup", button.dataset.followup)));
  $("#run-all-followups")?.addEventListener("click", () => startJob("followup", "todos"));
  $("#check-replies")?.addEventListener("click", () => startJob("respostas", "todos"));
}

function renderProspectForm(activeJobType = "prospectar") {
  const isProspect = activeJobType === "prospectar" || !activeJobType;
  const canais = state.config?.envio?.canais || ["email"];
  const channelLabel = canais.length === 2 ? "e-mail ou WhatsApp" : canais[0] === "whatsapp" ? "WhatsApp" : "e-mail";
  const providerOpts = [
    { value: "", label: "Usar default (config)" },
    ...(state.providers || []).map((p) => ({
      value: p.id,
      label: `${p.name}${p.available ? "" : " — off"}`,
      disabled: !p.available && p.id !== "openrouter",
    })),
  ];

  $("#view-prospect").innerHTML = `
    <div class="prospect-layout">
      <div class="panel" style="margin-top:0">
        <p class="muted" style="margin-top:0">Defina exatamente a área. O círculo no mapa será usado pelo Google Places para buscar negócios do nicho escolhido.</p>
        <form id="prospect-form" class="stack">
          <label>Nicho
            <input name="nicho" id="f-nicho" value="nutricionistas" required />
            <div class="suggest" id="sug-nicho">${NICHOS.map((n) => `<button type="button" data-fill="f-nicho" data-v="${esc(n)}">${esc(n)}</button>`).join("")}</div>
          </label>
          <label>Onde você quer prospectar?
            <input name="cidade" id="f-cidade" autocomplete="off" value="Rio de Janeiro" placeholder="Bairro, cidade ou endereço" required />
            <span class="field-hint">Digite ao menos 3 caracteres e escolha uma localização.</span>
            <div class="location-results" id="location-results"></div>
          </label>
          <input type="hidden" name="lat" id="f-lat" />
          <input type="hidden" name="lng" id="f-lng" />
          <div class="row">
            <label style="flex:1">Raio de busca <span class="range-value" id="radius-value">15 km</span>
              <input name="raioKm" id="f-radius" type="range" min="1" max="50" value="15" />
            </label>
            <label>Meta de leads ouro
              <input name="meta" type="number" min="1" max="100" value="5" />
            </label>
            <label>Volume a analisar
              ${selectHtml("f-candidates", [
                { value: "100", label: "100 negócios" },
                { value: "250", label: "250 negócios" },
                { value: "500", label: "500 negócios" },
              ], 'name="candidateLimit"')}
              <span class="field-hint">Mais volume = mais tempo e consumo Maps</span>
            </label>
          </div>
          <div class="row">
            <label>Nota mín.<input name="notaMinima" type="number" min="1" max="5" step="0.1" value="4.7" /></label>
            <label>Avaliações mín.<input name="avaliacoesMinimas" type="number" min="0" value="40" /></label>
            <label>Motor Maps
              ${selectHtml("f-engine", [
                { value: "auto", label: "Auto — Places → Apify" },
                { value: "google_places", label: "Google Places" },
                { value: "apify", label: "Apify" },
              ], 'name="engine"')}
            </label>
            <label>Site considerado fraco
              ${selectHtml("f-quality", [
                { value: "strict", label: "Rigoroso · 3+ sinais" },
                { value: "balanced", label: "Equilibrado · 2+ sinais" },
                { value: "broad", label: "Amplo · 1 problema forte" },
              ], 'name="siteQuality"')}
            </label>
          </div>
          <button class="btn primary" type="submit" id="btn-prospect">Iniciar prospecção nesta área</button>
        </form>
      </div>
      <div class="panel" style="margin-top:0">
        <h3>Área selecionada</h3>
        <div class="prospect-map" id="prospect-map"></div>
        <div class="map-caption"><span id="map-location">Busque uma localização para centralizar.</span><span>${esc(channelLabel)} obrigatório</span></div>
      </div>
    </div>

    <div class="panel" id="run-panel">
      <div class="run-head">
        <h3 style="margin:0" id="run-title">${isProspect ? "Andamento" : JOB_LABEL[activeJobType] || activeJobType}</h3>
        <span class="muted small" id="run-job-label">Nenhuma rodada ainda</span>
      </div>
      <ol class="steps" id="run-steps">
        ${
          isProspect
            ? `
        <li data-step="start" class="step"><span class="step-num">0</span><div><strong>Preparar</strong><div class="muted small">Critérios</div></div></li>
        <li data-step="search" class="step"><span class="step-num">1</span><div><strong>Buscar no Maps</strong><div class="muted small">Places / Apify</div></div></li>
        <li data-step="filter" class="step"><span class="step-num">2</span><div><strong>Filtrar</strong><div class="muted small">Nota e avaliações</div></div></li>
        <li data-step="qualify" class="step"><span class="step-num">3</span><div><strong>Analisar sites</strong><div class="muted small">Fraco + ${esc(channelLabel)}</div></div></li>
        <li data-step="save" class="step"><span class="step-num">4</span><div><strong>Salvar leads</strong><div class="muted small">Resumo</div></div></li>`
            : `
        <li data-step="start" class="step"><span class="step-num">1</span><div><strong>Iniciar</strong><div class="muted small">Fila</div></div></li>
        <li data-step="run" class="step"><span class="step-num">2</span><div><strong>Executar</strong><div class="muted small">Script</div></div></li>
        <li data-step="save" class="step"><span class="step-num">3</span><div><strong>Finalizar</strong><div class="muted small">Status do lead</div></div></li>`
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
        <summary>Log</summary>
        <div class="log" id="job-log">Aguardando…</div>
      </details>
    </div>`;

  $("#f-engine").value = "auto";
  $("#f-quality").value = state.config?.prospeccao?.siteQuality || "balanced";
  let prospectMap = null;
  let marker = null;
  let circle = null;
  const setArea = (area) => {
    $("#f-lat").value = area.lat;
    $("#f-lng").value = area.lng;
    $("#f-cidade").value = area.label;
    $("#map-location").textContent = area.label;
    $("#location-results").innerHTML = "";
    if (!prospectMap) return;
    const point = [area.lat, area.lng];
    prospectMap.setView(point, Math.max(prospectMap.getZoom(), 12));
    if (marker) marker.setLatLng(point); else marker = L.marker(point, { draggable: true }).addTo(prospectMap);
    marker.off("dragend").on("dragend", () => {
      const pos = marker.getLatLng();
      $("#f-lat").value = pos.lat.toFixed(6);
      $("#f-lng").value = pos.lng.toFixed(6);
      refreshRadius();
    });
    refreshRadius();
  };
  const refreshRadius = () => {
    if (!prospectMap || !marker) return;
    const radiusKm = Number($("#f-radius").value || 15);
    $("#radius-value").textContent = `${radiusKm} km`;
    if (circle) circle.setRadius(radiusKm * 1000); else circle = L.circle(marker.getLatLng(), { radius: radiusKm * 1000, color: "#ff7a1a", fillColor: "#ff7a1a", fillOpacity: .12 }).addTo(prospectMap);
    circle.setLatLng(marker.getLatLng());
  };
  if (window.L) {
    prospectMap = L.map("prospect-map", { scrollWheelZoom: true }).setView([-22.9068, -43.1729], 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(prospectMap);
    prospectMap.on("click", (event) => setArea({ label: $("#f-cidade").value || "Ponto selecionado no mapa", lat: event.latlng.lat, lng: event.latlng.lng }));
  } else {
    $("#prospect-map").innerHTML = '<p class="muted" style="padding:20px">Não foi possível carregar o mapa. Você ainda pode buscar uma localização.</p>';
  }
  $("#f-radius").addEventListener("input", refreshRadius);
  let locationTimer;
  $("#f-cidade").addEventListener("input", (event) => {
    clearTimeout(locationTimer);
    const query = event.target.value.trim();
    if (query.length < 3) { $("#location-results").innerHTML = ""; return; }
    locationTimer = setTimeout(async () => {
      try {
        const places = await api(`/api/maps/locations?q=${encodeURIComponent(query)}`);
        $("#location-results").innerHTML = places.map((p, index) => `<button type="button" class="location-result" data-location="${index}">${esc(p.label)}</button>`).join("");
        $$("[data-location]").forEach((button) => button.addEventListener("click", () => setArea(places[Number(button.dataset.location)])));
      } catch (error) {
        $("#location-results").innerHTML = `<span class="muted small">${esc(error.message)}</span>`;
      }
    }, 350);
  });
  $$("[data-fill]").forEach((b) =>
    b.addEventListener("click", () => {
      const input = $(`#${b.dataset.fill}`);
      if (input) input.value = b.dataset.v;
      $$(`[data-fill="${b.dataset.fill}"]`).forEach((x) => x.classList.toggle("active", x === b));
    })
  );

  $("#prospect-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#btn-prospect");
    btn.disabled = true;
    btn.textContent = "Rodando…";
    try {
      const fd = new FormData(e.target);
      const payload = Object.fromEntries(fd.entries());
      payload.meta = Number(payload.meta);
      payload.candidateLimit = Number(payload.candidateLimit);
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
    setStep(left.slice(5) === "done" ? "done" : left.slice(5));
    if (rest.length) appendLog(rest.join("|"));
    return;
  }
  if (msg.startsWith("COUNT:")) {
    msg.slice(6).split(",").forEach((part) => {
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
    box.classList.remove("hidden");
    box.innerHTML = `
      <strong>Resumo</strong>
      <p>
        <strong>${result.candidates ?? "—"}</strong> no Maps ·
        <strong>${result.qualified_count ?? 0}</strong> leads ouro ·
        <strong>${result.discarded_count ?? 0}</strong> descartados
      </p>
      ${leads ? `<ul class="clean">${leads}</ul>` : "<p class='muted'>Nenhum lead ouro.</p>"}
      <button class="btn ghost" id="goto-leads" type="button">Ver leads</button>`;
    $("#goto-leads")?.addEventListener("click", () => {
      showView("leads");
      renderLeads();
    });
    return;
  }

  setStep("done");
  box.classList.remove("hidden");
  if (["proposta", "followup"].includes(job.type) && Array.isArray(result.channels)) {
    const statusLabel = {
      gmail_draft: "NO GMAIL · NÃO ENVIADO",
      local_draft: "RASCUNHO · NÃO ENVIADO",
      sent: "ENVIADO",
      failed_local_draft: "FALHOU · RASCUNHO SALVO",
      not_due: "AINDA NÃO DEVIDO",
    };
    const cards = result.channels.map((item) => {
      const status = item.status || "failed";
      const tone = item.sent ? "sent" : status.includes("failed") ? "failed" : "draft";
      const channel = item.channel === "whatsapp" ? "WhatsApp" : "E-mail";
      const icon = item.channel === "whatsapp" ? "WA" : "@";
      return `<div class="channel-result">
        <div class="channel-result-icon">${icon}</div>
        <div>
          <strong>${channel}</strong>
          <span class="muted small">${esc(item.location || "Destino não informado")}</span>
          ${item.fallback_reason || item.error ? `<span class="error small">${esc(item.fallback_reason || item.error)}</span>` : ""}
        </div>
        <span class="channel-result-status ${tone}">${esc(statusLabel[status] || status.toUpperCase())}</span>
        ${status === "gmail_draft" ? '<a class="btn ghost sm" href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noopener">Abrir Gmail</a>' : ""}
      </div>`;
    }).join("");
    box.innerHTML = `
      <strong class="ok">${job.type === "followup" ? "Follow-up processado" : "Outreach preparado"}</strong>
      <p class="muted">Confira abaixo exatamente o que aconteceu em cada canal.</p>
      <div class="channel-results">${cards}</div>
      <button class="btn primary" id="goto-drafts" type="button">Ver mensagens e rascunhos</button>
      <button class="btn ghost" id="goto-leads" type="button">Ver lead</button>`;
    $("#goto-drafts")?.addEventListener("click", () => { showView("emails"); renderEmails(); });
    $("#goto-leads")?.addEventListener("click", () => { showView("leads"); renderLeads(); });
    return;
  }
  if (job.type === "respostas") {
    const replied = result.responded || [];
    const sent = result.sent_detected || [];
    box.innerHTML = `<strong class="ok">Gmail verificado</strong>
      <p><strong>${result.checked || 0}</strong> lead(s) consultado(s) · <strong>${replied.length}</strong> resposta(s) · <strong>${sent.length}</strong> envio(s) detectado(s)</p>
      ${replied.length ? `<p class="ok">Movidos para Respondeu: ${replied.map(esc).join(", ")}</p>` : '<p class="muted">Nenhuma resposta nova.</p>'}
      <button class="btn primary" id="goto-followups" type="button">Voltar aos follow-ups</button>`;
    $("#goto-followups")?.addEventListener("click", () => { showView("followups"); renderFollowups(); });
    return;
  }
  const labels = {
    redesenhar: "Site redesenhado. Próximo: Publicar + DNS.",
    publicar: "Publicado + DNS. Próximo: Proposta.",
    proposta: "Outreach processado. Consulte o log para confirmar cada canal.",
  };
  box.innerHTML = `
    <strong class="ok">Concluído</strong>
    <p class="muted">${esc(labels[job.type] || "Job finalizado.")}</p>
    ${job.type === "proposta" ? '<button class="btn primary" id="goto-drafts" type="button">Abrir rascunhos</button>' : ''}
    <button class="btn ghost" id="goto-leads" type="button">Ver leads</button>`;
  $("#goto-drafts")?.addEventListener("click", () => {
    showView("emails");
    renderEmails();
  });
  $("#goto-leads")?.addEventListener("click", () => {
    showView("leads");
    renderLeads();
  });
}

async function watchJob(id, jobType = "prospectar") {
  if (state.es) state.es.close();
  if (state.jobPoll) clearInterval(state.jobPoll);
  $("#run-job-label").textContent = `Job #${id}`;
  if ($("#run-title")) $("#run-title").textContent = JOB_LABEL[jobType] || jobType;
  resetRunUI();
  setStep("start");
  appendLog(`Job #${id}…`);

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
    const finish = async () => {
      if (state.es) state.es.close();
      if (state.jobPoll) clearInterval(state.jobPoll);
      state.jobPoll = null;
      const job = await api(`/api/jobs/${id}`);
      showJobSummary(job);
      appendLog(`— fim —`);
      renderLeads();
      renderJobs();
      api("/api/stats").then(renderOverview).catch(() => {});
      resolve(job);
    };
    const pollEvents = async () => {
      try {
        const job = await api(`/api/jobs/${id}`);
        (job.events || []).filter((event) => (event.id || 0) > lastId).forEach((event) => {
          lastId = event.id || lastId;
          applyRunMessage(event.message, jobType);
        });
        if (["succeeded", "failed", "cancelled"].includes(job.status)) await finish();
      } catch (_) {}
    };
    state.es = new EventSource(`/api/jobs/${id}/events?after=${lastId}`);
    state.es.onmessage = async (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.done) {
          await finish();
          return;
        }
        if (data.id) lastId = data.id;
        if (data.message) applyRunMessage(data.message, jobType);
      } catch (_) {}
    };
    state.es.onerror = () => {
      // Proxies may buffer/close SSE during long 250/500-result runs. Polling
      // keeps the counters and final state live instead of freezing the UI.
      state.es?.close();
      if (!state.jobPoll) state.jobPoll = setInterval(pollEvents, 2500);
    };
  });
}

async function renderLeads() {
  state.leads = await api("/api/leads");
  const filters = [
    { id: "ativos", label: "Ativos" },
    { id: "novo", label: "Novos" },
    { id: "redesenhado", label: "A publicar" },
    { id: "publicado", label: "Publicados" },
    { id: "proposta", label: "Propostas" },
    { id: "respondeu", label: "Responderam" },
    { id: "fechado", label: "Fechados" },
    { id: "todos", label: "Todos" },
  ];

  const q = (state.search || "").toLowerCase().trim();
  let list = state.leads;
  if (state.filter === "ativos") list = list.filter((l) => l.status !== "descartado");
  else if (state.filter !== "todos") list = list.filter((l) => l.status === state.filter);
  if (q) {
    list = list.filter(
      (l) =>
        (l.nome || "").toLowerCase().includes(q) ||
        (l.email || "").toLowerCase().includes(q) ||
        (l.cidade || "").toLowerCase().includes(q) ||
        (l.nicho || "").toLowerCase().includes(q)
    );
  }

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
        <td>${statusPill(l.status)}</td>
        <td class="small">${esc(l.email || "—")}</td>
        <td onclick="event.stopPropagation()">
          <div class="row">
            <button class="btn ghost sm" data-act="redesenhar" data-slug="${esc(l.slug)}">Nova direção visual</button>
            ${!next.disabled && next.type
              ? `<button class="btn primary sm" data-act="${esc(next.type)}" data-slug="${esc(l.slug)}">${esc(next.label)}</button>`
              : `<button class="btn ghost sm" data-open-btn="${esc(l.slug)}">Detalhe</button>`}
          </div>
        </td>
      </tr>`;
    })
    .join("");

  $("#view-leads").innerHTML = `
    <div class="panel">
      <div class="filters">
        <div class="seg">
          ${filters
            .map(
              (f) =>
                `<button type="button" class="${state.filter === f.id ? "active" : ""}" data-filter="${f.id}">${f.label}</button>`
            )
            .join("")}
        </div>
        <div class="search-wrap">
          <input id="lead-search" type="search" placeholder="Buscar nome, e-mail, cidade…" value="${esc(state.search)}" />
        </div>
        <button class="btn ghost sm" id="refresh-leads" type="button">Atualizar</button>
      </div>
      <p class="muted small" style="margin:0 0 14px">“Nova direção visual” gera outro estilo, composição e imagens. “Preparar outreach” cria e-mail e WhatsApp, mas não altera o site.</p>
      ${
        rows
          ? `<table class="table">
        <thead><tr><th>Lead</th><th>Maps</th><th>Status</th><th>E-mail</th><th>Ação</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`
          : `<div class="empty"><strong>Nenhum lead aqui</strong>Ajuste o filtro ou rode uma prospecção.</div>`
      }
    </div>`;

  $$("[data-filter]").forEach((b) =>
    b.addEventListener("click", () => {
      state.filter = b.dataset.filter;
      renderLeads();
    })
  );
  $("#lead-search")?.addEventListener("input", (e) => {
    state.search = e.target.value;
    clearTimeout(renderLeads._t);
    renderLeads._t = setTimeout(renderLeads, 180);
  });
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

async function renderEmails() {
  const data = await api("/api/emails");
  const drafts = data.drafts || [];
  const leads = data.leads || [];
  const selected = state.emailId;

  const list = drafts
    .map((d) => {
      const active = selected === d.id ? "active" : "";
      return `
      <button type="button" class="email-item ${active}" data-email="${esc(d.id)}">
        <div class="email-item-top">
          <strong>${esc(d.subject || "(sem assunto)")}</strong>
          <span class="muted small">${esc((d.created || "").slice(0, 16))}</span>
        </div>
        <div class="muted small">${esc(d.to || "—")} · ${esc(d.slug || "")}</div>
        <div class="email-item-meta">
          <span class="pill proposta">${d.channel === "whatsapp" ? "WhatsApp" : "E-mail"}</span>
          <span class="muted small">${esc(d.storage || "local")}</span>
        </div>
      </button>`;
    })
    .join("");

  const leadRows = leads
    .map(
      (l) => `
    <tr>
      <td><strong>${esc(l.nome)}</strong><div class="muted small">${esc(l.email)}</div></td>
      <td>${statusPill(l.status)}</td>
      <td class="small">${esc(l.dataProposta || l.atualizado || "")}</td>
      <td class="row">
        ${l.urlNova ? `<a class="btn ghost sm" href="${esc(l.urlNova)}" target="_blank" rel="noopener">Site</a>` : ""}
        <button class="btn primary sm" data-act="proposta" data-slug="${esc(l.slug)}">Preparar outreach</button>
      </td>
    </tr>`
    )
    .join("");

  $("#view-emails").innerHTML = `
    <div class="panel" style="margin-top:0">
      <div class="row between" style="margin-bottom:12px">
        <div>
          <h3 style="margin:0">Mensagens e rascunhos</h3>
          <p class="muted small" style="margin:4px 0 0">E-mail e WhatsApp salvos para revisão. O selo indica o canal; o resumo do job confirma se houve envio.</p>
        </div>
        <button class="btn ghost sm" type="button" id="refresh-emails">Atualizar</button>
        <a class="btn ghost sm" href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noopener">Abrir Gmail</a>
      </div>
      <div class="email-layout">
        <div class="email-list">
          ${list || `<div class="empty"><strong>Nenhuma mensagem ainda</strong>Publique um lead e rode «Gerar outreach».</div>`}
        </div>
        <div class="email-preview" id="email-preview">
          <div class="empty"><strong>Selecione uma mensagem</strong>para visualizar o conteúdo.</div>
        </div>
      </div>
    </div>
    <div class="panel">
      <h3 style="margin-top:0">Leads com proposta / publicados</h3>
      ${
        leadRows
          ? `<table class="table">
        <thead><tr><th>Lead</th><th>Status</th><th>Data</th><th></th></tr></thead>
        <tbody>${leadRows}</tbody>
      </table>`
          : `<div class="empty"><strong>Nenhum lead</strong>Publique e envie proposta primeiro.</div>`
      }
    </div>`;

  $("#refresh-emails")?.addEventListener("click", () => {
    state.emailId = null;
    renderEmails();
  });
  $$("[data-email]").forEach((btn) =>
    btn.addEventListener("click", () => openEmailPreview(btn.dataset.email))
  );
  $$("#view-emails [data-act]").forEach((btn) =>
    btn.addEventListener("click", () => startJob(btn.dataset.act, btn.dataset.slug))
  );

  if (selected && drafts.some((d) => d.id === selected)) {
    openEmailPreview(selected);
  }
}

async function openEmailPreview(id) {
  state.emailId = id;
  $$(".email-item").forEach((el) => el.classList.toggle("active", el.dataset.email === id));
  const box = $("#email-preview");
  if (!box) return;
  box.innerHTML = `<div class="muted small" style="padding:16px">Carregando…</div>`;
  try {
    const mail = await api(`/api/emails/${encodeURIComponent(id)}`);
    box.innerHTML = `
      <div class="email-preview-head">
        <div>
          <div class="muted small">Para</div>
          <strong>${esc(mail.to || "—")}</strong>
        </div>
        <div>
          <div class="muted small">Assunto</div>
          <strong>${esc(mail.subject || "—")}</strong>
        </div>
        <div class="row">
          <a class="btn ghost sm" href="/api/emails/${encodeURIComponent(id)}/preview" target="_blank" rel="noopener">Abrir</a>
          <button class="btn ghost sm" type="button" id="copy-email">Copiar HTML</button>
          <button class="btn danger sm" type="button" id="del-email">Apagar</button>
        </div>
      </div>
      <iframe class="email-frame" title="preview" sandbox="allow-same-origin" src="/api/emails/${encodeURIComponent(id)}/preview"></iframe>
      <p class="muted small" style="margin:10px 0 0">Arquivo: <code>${esc(mail.filename)}</code> · ${esc(mail.channel || "")}</p>`;
    $("#copy-email")?.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(mail.content || "");
        toast("HTML copiado — cole no Gmail");
      } catch {
        toast("Não foi possível copiar");
      }
    });
    $("#del-email")?.addEventListener("click", async () => {
      if (!confirm("Apagar este rascunho?")) return;
      await api(`/api/emails/${encodeURIComponent(id)}`, { method: "DELETE" });
      state.emailId = null;
      toast("Rascunho apagado");
      renderEmails();
    });
  } catch (e) {
    box.innerHTML = `<div class="empty"><strong class="error">Erro</strong>${esc(e.message)}</div>`;
  }
}

async function renderJobs() {
  state.jobs = await api("/api/jobs?limit=40");
  const rows = state.jobs
    .map(
      (j) => `
    <tr>
      <td>#${j.id}</td>
      <td>${esc(JOB_LABEL[j.type] || j.type)}</td>
      <td>${statusPill(j.status)}</td>
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
      ${
        rows
          ? `<table class="table">
        <thead><tr><th>ID</th><th>Tipo</th><th>Status</th><th>Criado</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`
          : `<div class="empty"><strong>Sem jobs</strong>Dispare uma prospecção para começar.</div>`
      }
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

function providerHelp(id) {
  const map = {
    openrouter: "API cloud — precisa de key. Bom default para copy de redesign/proposta.",
    claude: "CLI local <code>claude</code> autenticado no PATH do servidor.",
    codex: "CLI local <code>codex</code> no PATH.",
    cursor: "CLI <code>cursor-agent</code> / <code>agent</code> no PATH.",
  };
  return map[id] || "";
}

async function loadOpenRouterModels(query = "") {
  const sel = $("#cfg-ormodel");
  const status = $("#or-models-status");
  const count = $("#or-model-count");
  if (!sel) return;
  state.orModelQuery = query;
  if (status) status.textContent = "Carregando modelos…";
  if (count) count.textContent = "…";

  const current = val("#cfg-ormodel") || state.config?.llm?.openrouter_model || "openai/gpt-4o-mini";
  const keyInput = val("#cfg-or");
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  // Se o usuário acabou de colar uma key nova (não mascarada), envia no query
  if (keyInput && keyInput !== "***" && keyInput.length > 8) params.set("key", keyInput);

  try {
    const res = await fetch(`/api/providers/openrouter/models?${params}`, {
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      location.href = "/login";
      return;
    }
    if (!res.ok || !data.success) {
      if (status) status.textContent = data.message || "Falha ao listar modelos";
      if (count) count.textContent = "erro";
      return;
    }
    const models = data.models || [];
    const want = data.default || current;
    sel.innerHTML = models
      .map((m) => {
        const id = m.id || m;
        const label = m.name && m.name !== id ? `${m.name} — ${id}` : id;
        return `<option value="${esc(id)}">${esc(label)}</option>`;
      })
      .join("");
    if (want && ![...sel.options].some((o) => o.value === want)) {
      const opt = document.createElement("option");
      opt.value = want;
      opt.textContent = want;
      sel.prepend(opt);
    }
    sel.value = want;
    if ($("#or-current-label")) $("#or-current-label").textContent = sel.value;
    if (status) status.textContent = `${models.length} modelos disponíveis`;
    if (count) count.textContent = String(models.length);
    state.openrouterModels = models;
  } catch (e) {
    if (status) status.textContent = e.message || "Erro";
    if (count) count.textContent = "erro";
  }
}

async function renderOutreach() {
  const rows = await api("/api/outreach");
  const outreachStatus = { sent: "Enviado", gmail_draft: "Rascunho no Gmail", local_draft: "Rascunho local", failed_local_draft: "Falhou · rascunho salvo", failed: "Falhou" };
  const body = rows.length
    ? rows.map((r) => `<tr>
        <td><strong>${esc(r.nome)}</strong><div class="muted small">${esc(r.lead_slug)}</div></td>
        <td>${esc(r.channel)}</td>
        <td>${esc(r.recipient || "—")}</td>
        <td>${esc(outreachStatus[r.status] || r.status)}</td>
        <td class="small">${esc(r.created_at)}</td>
        <td class="small">${esc(r.error || "—")}</td>
      </tr>`).join("")
    : '<tr><td colspan="6" class="muted">Nenhuma tentativa de envio registrada.</td></tr>';
  $("#view-outreach").innerHTML = `
    <div class="panel stack">
      <div class="row between"><div><h3 style="margin:0">Histórico de outreach</h3><p class="muted small" style="margin:4px 0 0">Cada linha informa se houve envio ou apenas criação de rascunho.</p></div>
      <button class="btn ghost sm" id="refresh-outreach">Atualizar</button></div>
      <div style="overflow:auto"><table><thead><tr><th>Lead</th><th>Canal</th><th>Destino</th><th>Status</th><th>Quando</th><th>Erro</th></tr></thead><tbody>${body}</tbody></table></div>
    </div>`;
  $("#refresh-outreach")?.addEventListener("click", renderOutreach);
}

async function renderConfig() {
  state.config = await api("/api/config");
  state.providers = await api("/api/providers");
  state.integrations = await api("/api/config/integrations").catch(() => state.integrations);
  const c = state.config;
  const m = c.maps || {};
  const llm = c.llm || {};
  const a = c.assinatura || {};
  const aa = c.aapanel || {};
  const cf = c.cloudflare || {};
  const co = c.composio || {};
  const envio = c.envio || {};
  const waCfg = envio.whatsapp || {};
  const evoApi = waCfg.evolution_api || {};
  const evoGo = waCfg.evolution_go || {};
  const automation = c.automation || {};
  const redesign = c.redesign || {};
  const ready = Object.fromEntries((state.integrations?.funnel || []).map((f) => [f.id, f.ready]));
  const gmailIntegration = (state.integrations?.funnel || []).find((f) => f.id === "gmail") || {};
  state.selectedProvider = state.selectedProvider || llm.default_provider || "openrouter";

  const tabs = [
    { id: "llm", label: "LLM" },
    { id: "maps", label: "Maps" },
    { id: "publish", label: "Publicar" },
    { id: "gmail", label: "Gmail" },
    { id: "outreach", label: "Canais" },
    { id: "redesign", label: "Redesign" },
    { id: "assinatura", label: "Assinatura" },
  ];

  const providerCards = (state.providers || [])
    .map((p) => {
      const selected = state.selectedProvider === p.id;
      const live = !!p.available;
      return `
      <button type="button" class="provider-card ${selected ? "selected" : ""} ${live ? "" : "disabled"}"
        data-provider="${esc(p.id)}" ${live || p.id === "openrouter" ? "" : "disabled"}>
        <div class="pc-top">
          <span class="pc-name">${esc(p.name)}</span>
          <span class="status-pill ${live ? "live" : "dead"}"><span class="sdot"></span>${live ? "detectado" : "não encontrado"}</span>
        </div>
        <div class="pc-detail">${providerHelp(p.id)}</div>
        <div class="pc-detail">${esc(p.detail || (live ? "Pronto para usar" : "Instale/auth a CLI ou cole a API key"))}</div>
        ${selected ? `<div class="pc-detail" style="color:var(--accent-2)">✓ Provider padrão</div>` : ""}
      </button>`;
    })
    .join("");

  const models = []; // carregados sob demanda ao escolher OpenRouter
  const currentModel = llm.openrouter_model || "openai/gpt-4o-mini";
  const showOrPanel = state.selectedProvider === "openrouter";

  $("#view-config").innerHTML = `
    <div class="cfg-tabs">
      ${tabs.map((t) => `<button type="button" class="${state.cfgTab === t.id ? "active" : ""}" data-tab="${t.id}">${t.label}</button>`).join("")}
    </div>

    <div class="cfg-pane ${state.cfgTab === "llm" ? "" : "hidden"}" data-pane="llm">
      <div class="panel cfg-card stack">
        <h3>Provider de IA <span class="tag">redesign · proposta</span></h3>
        <p class="muted small" style="margin:0">
          O LLM <strong style="color:var(--ink)">não</strong> prospecta no Maps.
          Só entra em <strong style="color:var(--ink)">redesign</strong> e <strong style="color:var(--ink)">proposta</strong>.
          Clique em OpenRouter para carregar os modelos disponíveis.
        </p>
        <div class="provider-grid">${providerCards}</div>
        <div class="row">
          <label style="flex:1">Modelo para orquestrar / avaliar
            ${selectHtml("cfg-orchestrator-provider", (state.providers || []).map((p) => ({ value: p.id, label: p.name })))}
          </label>
          <label style="flex:1">Modelo específico de orquestração<input id="cfg-orchestrator-model" value="${esc(llm.orchestrator_model || "")}" placeholder="vazio = padrão do provider" /></label>
        </div>
        <div class="row">
          <label style="flex:1">Modelo para redesign / copy
            ${selectHtml("cfg-redesign-provider", (state.providers || []).map((p) => ({ value: p.id, label: p.name })))}
          </label>
          <label style="flex:1">Modelo específico de redesign<input id="cfg-redesign-model" value="${esc(llm.redesign_model || "")}" placeholder="vazio = padrão do provider" /></label>
          <label><input id="cfg-redesign-llm-enabled" type="checkbox" ${llm.redesign_llm_enabled ? "checked" : ""} /> Usar LLM no redesign</label>
        </div>
        <div class="row">
          <button class="btn ghost sm" type="button" id="refresh-providers">Re-detectar CLIs</button>
          <button class="btn ghost sm" type="button" id="test-provider">Testar provider + modelo</button>
        </div>
        <div id="llm-test-msg" class="muted small"></div>
      </div>

      <div class="panel cfg-card stack ${showOrPanel ? "" : "hidden"}" id="openrouter-panel">
        <h3>OpenRouter · modelos <span class="tag on" id="or-model-count">…</span></h3>
        <div class="row">
          <label style="flex:1">API Key
            <input id="cfg-or" type="password" value="${esc(llm.openrouter_api_key || "")}" placeholder="sk-or-…" />
          </label>
          <label style="flex:1">Buscar modelo
            <input id="or-model-search" type="search" placeholder="gpt, claude, gemini, deepseek…" />
          </label>
        </div>
        <label>Modelo que vamos usar
          <div class="select-wrap">
            <select id="cfg-ormodel" size="1">
              <option value="${esc(currentModel)}">${esc(currentModel)}</option>
            </select>
          </div>
        </label>
        <div class="row">
          <button class="btn primary sm" type="button" id="load-or-models">Carregar modelos</button>
          <span class="muted small" id="or-models-status">Selecione OpenRouter para listar</span>
        </div>
        <p class="field-hint">Modelo atual salvo: <code id="or-current-label">${esc(currentModel)}</code></p>
      </div>

      <div class="panel cfg-card stack ${showOrPanel ? "hidden" : ""}" id="cli-panel">
        <h3>CLI selecionada</h3>
        <p class="muted small" style="margin:0">
          Com Claude / Codex / Cursor não há lista de modelos OpenRouter —
          o modelo é o da própria CLI autenticada no servidor.
        </p>
      </div>
    </div>

    <div class="cfg-pane ${state.cfgTab === "maps" ? "" : "hidden"}" data-pane="maps">
      <div class="panel cfg-card stack">
        <h3>Google Maps <span class="tag ${ready.maps ? "on" : "off"}">${ready.maps ? "conectado" : "faltando"}</span></h3>
        <p class="muted small" style="margin:0">Places (oficial) ou Apify. Auto tenta Places e cai no Apify.</p>
        <div class="row">
          <label style="flex:1">Google Maps API Key<input id="cfg-gmaps" type="password" value="${esc(m.google_maps_api_key || "")}" placeholder="AIza…" /></label>
          <label style="flex:1">Apify API Key<input id="cfg-apify" type="password" value="${esc(m.apify_api_key || "")}" placeholder="apify_api_…" /></label>
          <label>Engine
            ${selectHtml("cfg-engine", [
              { value: "auto", label: "Auto" },
              { value: "google_places", label: "Places" },
              { value: "apify", label: "Apify" },
            ])}
          </label>
        </div>
        <div class="row">
          <button class="btn ghost sm" type="button" id="test-places">Testar Places</button>
          <button class="btn ghost sm" type="button" id="test-apify">Testar Apify</button>
        </div>
      </div>
    </div>

    <div class="cfg-pane ${state.cfgTab === "publish" ? "" : "hidden"}" data-pane="publish">
      <div class="panel cfg-card stack">
        <h3>aaPanel <span class="tag ${ready.aapanel ? "on" : "off"}">${ready.aapanel ? "ok" : "faltando"}</span></h3>
        <p class="muted small" style="margin:0">URL pública: <code>https://{slug}.{domínio}</code>. Use un dominio cuya zona DNS administre.</p>
        <div class="row">
          <label style="flex:1">URL painel<input id="cfg-aa-url" value="${esc(aa.url || "")}" /></label>
          <label style="flex:1">Domínio base<input id="cfg-aa-dom" value="${esc(aa.dominio_base || "example.com")}" /></label>
          <label style="flex:1">DNS target<input id="cfg-aa-dns" value="${esc(aa.dns_target || "origin.example.com")}" /></label>
        </div>
        <div class="row">
          <label>Subdomínio?
            ${selectHtml("cfg-aa-sub", [
              { value: "true", label: "Sim" },
              { value: "false", label: "Não (subpasta)" },
            ])}
          </label>
          <label style="flex:1">API token (opcional)<input id="cfg-aa-token" type="password" value="${esc(aa.api_token || "")}" placeholder="vazio = sudo local" /></label>
          <label>SSL
            ${selectHtml("cfg-aa-ssl", [
              { value: "true", label: "Cert compartilhado" },
              { value: "false", label: "Off" },
            ])}
          </label>
        </div>
      </div>
      <div class="panel cfg-card stack">
        <h3>Cloudflare DNS <span class="tag ${ready.cloudflare ? "on" : "off"}">${ready.cloudflare ? "conectado" : "faltando"}</span></h3>
        <p class="muted small" style="margin:0">Cria CNAME <code>{slug}</code> → target ao publicar.</p>
        <div class="row">
          <label style="flex:1">API Key / Token<input id="cfg-cf-key" type="password" value="${esc(cf.api_key || cf.api_token || "")}" /></label>
          <label style="flex:1">E-mail<input id="cfg-cf-email" value="${esc(cf.email || "")}" /></label>
          <label style="flex:1">Zona<input id="cfg-cf-zone" value="${esc(cf.zone || "example.com")}" /></label>
        </div>
        <button class="btn ghost sm" type="button" id="test-cf">Testar Cloudflare</button>
      </div>
    </div>

    <div class="cfg-pane ${state.cfgTab === "gmail" ? "" : "hidden"}" data-pane="gmail">
      <div class="panel cfg-card stack">
        <h3>Gmail via Composio <span class="tag ${ready.gmail ? "on" : "off"}">${ready.gmail ? "conta ativa" : "não conectado"}</span></h3>
        <p class="muted small" style="margin:0">
          ${esc(gmailIntegration.detail || "A conexão ainda não foi verificada.")}<br>
          O sistema cria um rascunho no Gmail e mantém uma cópia visual no painel. Ele não envia o e-mail automaticamente.
        </p>
        <div class="row">
          <label style="flex:1">Composio API Key<input id="cfg-co-key" type="password" value="${esc(co.api_key || "")}" /></label>
          <label style="flex:1">Entity ID<input id="cfg-co-entity" value="${esc(co.entity_id || "")}" placeholder="default" /></label>
          <label>Modo
            ${selectHtml("cfg-envio", [
              { value: "rascunho", label: "Rascunho (recomendado)" },
              { value: "envio", label: "Envio habilitado (WhatsApp)" },
            ])}
          </label>
        </div>
        <div class="row"><button class="btn ghost sm" type="button" id="test-composio">Testar Gmail conectado</button><span id="test-composio-msg" class="muted small"></span></div>
      </div>
    </div>

    <div class="cfg-pane ${state.cfgTab === "outreach" ? "" : "hidden"}" data-pane="outreach">
      <div class="panel cfg-card stack">
        <h3>Canais e piloto automático</h3>
        <p class="muted small" style="margin:0">O canal define quais contatos tornam um resultado do Maps elegível: e-mail exige e-mail; WhatsApp exige número; ambos aceitam qualquer um e enviam em todos os canais disponíveis.</p>
        <div class="row">
          <label>Canal de prospecção
            ${selectHtml("cfg-channel", [
              { value: "email", label: "E-mail" },
              { value: "whatsapp", label: "WhatsApp" },
              { value: "both", label: "E-mail + WhatsApp" },
            ])}
          </label>
          <label>Modo dos canais
            ${selectHtml("cfg-outreach-mode", [
              { value: "rascunho", label: "Rascunho" },
              { value: "envio", label: "Envio habilitado" },
            ])}
          </label>
          <label>Provedor WhatsApp
            ${selectHtml("cfg-wa-provider", [
              { value: "evolution_api", label: "Evolution API" },
              { value: "evolution_go", label: "Evolution Go" },
            ])}
          </label>
        </div>
        <div class="row">
          <label><input id="cfg-auto-enabled" type="checkbox" ${automation.enabled ? "checked" : ""} /> Piloto automático</label>
          <label><input id="cfg-auto-publish" type="checkbox" ${automation.publish !== false ? "checked" : ""} /> Publicar após redesign</label>
          <label><input id="cfg-auto-outreach" type="checkbox" ${automation.outreach ? "checked" : ""} /> Enviar após publicar</label>
        </div>
        <div class="panel" style="margin:0">
          <h4 style="margin:0 0 8px">Acompanhamento automático</h4>
          <p class="muted small">Uma vez por dia: verifica respostas no Gmail e prepara um único follow-up por canal após 3 dias úteis. Em modo rascunho, nada é enviado automaticamente.</p>
          <div class="row">
            <label><input id="cfg-followup-enabled" type="checkbox" ${automation.followup_enabled ? "checked" : ""} /> Ativar rotina diária</label>
            <label><input id="cfg-response-check" type="checkbox" ${automation.response_check_enabled !== false ? "checked" : ""} /> Verificar respostas antes</label>
            <label>Executar após<input id="cfg-followup-hour" type="number" min="0" max="23" value="${esc(automation.followup_hour ?? 9)}" style="width:90px" /> horas</label>
          </div>
        </div>
      </div>
      <div class="panel cfg-card stack">
        <h3>Evolution API / Go</h3>
        <div class="row">
          <label style="flex:1">URL Evolution API<input id="cfg-evo-api-url" value="${esc(evoApi.url || "http://localhost:8080")}" /></label>
          <label style="flex:1">API key<input id="cfg-evo-api-key" type="password" value="${esc(evoApi.api_key || "")}" /></label>
          <label>Instância<input id="cfg-evo-api-instance" value="${esc(evoApi.instance || "prospector")}" /></label>
        </div>
        <div class="row">
          <label style="flex:1">URL Evolution Go<input id="cfg-evo-go-url" value="${esc(evoGo.url || "http://localhost:8080")}" /></label>
          <label style="flex:1">API key<input id="cfg-evo-go-key" type="password" value="${esc(evoGo.api_key || "")}" /></label>
        </div>
        <div class="row"><button class="btn ghost sm" type="button" id="test-whatsapp">Testar conexão WhatsApp</button><span id="test-whatsapp-msg" class="muted small"></span></div>
      </div>
    </div>

    <div class="cfg-pane ${state.cfgTab === "redesign" ? "" : "hidden"}" data-pane="redesign">
      <div class="panel cfg-card stack">
        <h3>Direção criativa</h3>
        <p class="muted small" style="margin:0">O gerador escolhe uma composição por nicho, não apenas outra cor. Imagens de origem são usadas primeiro; geração externa é opcional.</p>
        <div class="row">
          <label>Direção
            ${selectHtml("cfg-redesign-direction", [
              { value: "auto", label: "Auto por nicho" },
              { value: "editorial", label: "Editorial sofisticado" },
              { value: "cinematic", label: "Cinemático imersivo" },
              { value: "minimal", label: "Minimalista premium" },
            ])}
          </label>
          <label>Imagens
            ${selectHtml("cfg-image-provider", [
              { value: "source", label: "Fotos do site / fallback" },
              { value: "kie_mcp", label: "KIE MCP (configuração externa)" },
            ])}
          </label>
          <label>Modelo de imagem
            <select id="cfg-image-model"><option value="${esc(redesign.image_model || "")}">${esc(redesign.image_model || "Escolha após conectar KIE")}</option></select>
          </label>
          <label><input id="cfg-parallax" type="checkbox" ${redesign.parallax !== false ? "checked" : ""} /> Parallax</label>
        </div>
        <div class="row">
          <label style="flex:1">KIE AI API key<input id="cfg-kie-key" type="password" value="${esc(redesign.kie_api_key || "")}" placeholder="Salva somente no servidor" /></label>
          <button class="btn ghost sm" type="button" id="test-kie">Testar KIE MCP</button>
          <button class="btn ghost sm" type="button" id="load-kie-models">Carregar modelos</button>
          <span id="test-kie-msg" class="muted small"></span>
        </div>
        <label>Prompt de preview
          <textarea id="kie-image-prompt" rows="3" placeholder="Ex.: foto editorial premium de clínica odontológica contemporânea, luz natural, paleta roxa, sem texto, 16:9"></textarea>
        </label>
        <div class="row">
          <label>Formato ${selectHtml("kie-aspect", ["16:9", "4:3", "1:1", "9:16"])}</label>
          <label>Resolução ${selectHtml("kie-resolution", ["1K", "2K", "4K"])}</label>
          <button class="btn primary sm" type="button" id="generate-kie-image">Gerar imagem de preview</button>
        </div>
        <div id="kie-generation-result" class="hidden"></div>
        <p class="field-hint">O teste inicia o MCP via npx no servidor e valida o handshake. Salve a chave antes de testar.</p>
      </div>
    </div>

    <div class="cfg-pane ${state.cfgTab === "assinatura" ? "" : "hidden"}" data-pane="assinatura">
      <div class="panel cfg-card stack">
        <h3>Assinatura dos e-mails</h3>
        <div class="row">
          <label style="flex:1">Nome<input id="cfg-nome" value="${esc(a.nome || "")}" /></label>
          <label style="flex:1">WhatsApp<input id="cfg-wa" value="${esc(a.whatsapp || "")}" /></label>
          <label style="flex:1">E-mail<input id="cfg-email" value="${esc(a.email || "")}" /></label>
        </div>
        <label>Apresentação<textarea id="cfg-apres" rows="2">${esc(a.apresentacao || "")}</textarea></label>
      </div>
    </div>

    <div class="row" style="margin-top:14px">
      <button class="btn primary" id="save-cfg" type="button">Salvar</button>
      <div id="cfg-msg" class="muted"></div>
    </div>`;

  // set select values after mount
  if ($("#cfg-engine")) $("#cfg-engine").value = m.engine || "auto";
  if ($("#cfg-orchestrator-provider")) $("#cfg-orchestrator-provider").value = llm.orchestrator_provider || llm.default_provider || "openrouter";
  if ($("#cfg-redesign-provider")) $("#cfg-redesign-provider").value = llm.redesign_provider || llm.default_provider || "openrouter";
  if ($("#cfg-aa-sub")) $("#cfg-aa-sub").value = String(aa.usar_subdominio !== false);
  if ($("#cfg-aa-ssl")) $("#cfg-aa-ssl").value = String(aa.ssl_auto !== false);
  if ($("#cfg-envio")) $("#cfg-envio").value = envio.modo || "rascunho";
  if ($("#cfg-outreach-mode")) $("#cfg-outreach-mode").value = envio.modo || "rascunho";
  if ($("#cfg-channel")) $("#cfg-channel").value = (envio.canais || ["email"]).length === 2 ? "both" : (envio.canais || ["email"])[0];
  if ($("#cfg-wa-provider")) $("#cfg-wa-provider").value = waCfg.provedor || "evolution_api";
  if ($("#cfg-redesign-direction")) $("#cfg-redesign-direction").value = redesign.direction || "auto";
  if ($("#cfg-image-provider")) $("#cfg-image-provider").value = redesign.image_provider || "source";

  $$("[data-tab]").forEach((b) =>
    b.addEventListener("click", () => {
      state.cfgTab = b.dataset.tab;
      renderConfig();
    })
  );

  $$("[data-provider]").forEach((card) =>
    card.addEventListener("click", () => {
      if (card.disabled) return;
      state.selectedProvider = card.dataset.provider;
      toast(`Provider: ${state.selectedProvider}`);
      renderConfig();
    })
  );

  $("#refresh-providers")?.addEventListener("click", async () => {
    state.providers = await api("/api/providers");
    toast("CLIs re-detectados");
    renderConfig();
  });

  $("#load-or-models")?.addEventListener("click", () => loadOpenRouterModels());
  $("#or-model-search")?.addEventListener("input", (e) => {
    clearTimeout(loadOpenRouterModels._t);
    loadOpenRouterModels._t = setTimeout(() => loadOpenRouterModels(e.target.value), 280);
  });
  $("#cfg-ormodel")?.addEventListener("change", () => {
    const v = val("#cfg-ormodel");
    if ($("#or-current-label")) $("#or-current-label").textContent = v;
    toast(`Modelo: ${v}`);
  });

  // Auto-carrega modelos ao abrir aba LLM com OpenRouter
  if (state.cfgTab === "llm" && state.selectedProvider === "openrouter") {
    loadOpenRouterModels(state.orModelQuery || "");
  }

  $("#test-provider")?.addEventListener("click", async () => {
    const msgEl = $("#llm-test-msg");
    msgEl.textContent = "Testando…";
    try {
      const r = await api("/api/providers/test", {
        method: "POST",
        body: JSON.stringify({
          provider: state.selectedProvider,
          model: state.selectedProvider === "openrouter" ? val("#cfg-ormodel") : null,
        }),
      });
      msgEl.textContent = r.success ? `OK: ${r.reply}` : r.message || "falhou";
    } catch (e) {
      msgEl.textContent = e.message;
    }
  });

  const msg = (t) => {
    $("#cfg-msg").textContent = t;
  };

  $("#save-cfg").onclick = async () => {
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
        engine: val("#cfg-engine") || "auto",
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
        api_key: val("#cfg-cf-key") || "***",
        email: val("#cfg-cf-email"),
        zone: val("#cfg-cf-zone"),
        proxied: true,
      },
      composio: {
        api_key: val("#cfg-co-key") || "***",
        entity_id: val("#cfg-co-entity"),
      },
      envio: {
        modo: val("#cfg-outreach-mode") || val("#cfg-envio") || "rascunho",
        canais: val("#cfg-channel") === "both" ? ["email", "whatsapp"] : [val("#cfg-channel") || "email"],
        whatsapp: {
          provedor: val("#cfg-wa-provider") || "evolution_api",
          evolution_api: { url: val("#cfg-evo-api-url"), api_key: val("#cfg-evo-api-key") || "***", instance: val("#cfg-evo-api-instance") },
          evolution_go: { url: val("#cfg-evo-go-url"), api_key: val("#cfg-evo-go-key") || "***" },
        },
      },
      automation: {
        enabled: $("#cfg-auto-enabled")?.checked || false,
        redesign: true,
        publish: $("#cfg-auto-publish")?.checked || false,
        outreach: $("#cfg-auto-outreach")?.checked || false,
        followup_enabled: $("#cfg-followup-enabled")?.checked || false,
        response_check_enabled: $("#cfg-response-check")?.checked !== false,
        followup_hour: Number(val("#cfg-followup-hour") || 9),
      },
      redesign: {
        direction: val("#cfg-redesign-direction") || "auto",
        image_provider: val("#cfg-image-provider") || "source",
        image_model: val("#cfg-image-model"),
        kie_api_key: val("#cfg-kie-key") || "***",
        parallax: $("#cfg-parallax")?.checked || false,
      },
      llm: {
        openrouter_api_key: val("#cfg-or") || "***",
        openrouter_model: val("#cfg-ormodel") || "openai/gpt-4o-mini",
        default_provider: state.selectedProvider || "openrouter",
        orchestrator_provider: val("#cfg-orchestrator-provider") || state.selectedProvider || "openrouter",
        orchestrator_model: val("#cfg-orchestrator-model"),
        redesign_provider: val("#cfg-redesign-provider") || state.selectedProvider || "openrouter",
        redesign_model: val("#cfg-redesign-model"),
        redesign_llm_enabled: $("#cfg-redesign-llm-enabled")?.checked || false,
      },
    };
    await api("/api/config", { method: "POST", body: JSON.stringify(body) });
    state.providers = await api("/api/providers");
    state.integrations = await api("/api/config/integrations");
    state.config = await api("/api/config");
    const llmP = state.providers.find((p) => p.id === state.selectedProvider);
    $("#engine-badge").textContent = `LLM: ${llmP?.name || state.selectedProvider}${llmP?.available ? "" : " ✕"}`;
    msg("Salvo.");
    toast("Config salva");
  };

  $("#test-places")?.addEventListener("click", async () => {
    const r = await api("/api/config/engines/test", {
      method: "POST",
      body: JSON.stringify({ engine: "google_places" }),
    });
    msg(r.message || JSON.stringify(r));
  });
  $("#test-apify")?.addEventListener("click", async () => {
    const r = await api("/api/config/engines/test", {
      method: "POST",
      body: JSON.stringify({ engine: "apify" }),
    });
    msg(r.message || JSON.stringify(r));
  });
  $("#test-whatsapp")?.addEventListener("click", async () => {
    const el = $("#test-whatsapp-msg");
    el.textContent = "Salve a configuração antes de testar.";
    try {
      const r = await api("/api/config/whatsapp/test", { method: "POST", body: "{}" });
      el.textContent = r.message || (r.success ? "Conectado" : "Falhou");
    } catch (e) { el.textContent = e.message; }
  });
  $("#test-composio")?.addEventListener("click", async () => {
    const el = $("#test-composio-msg");
    el.textContent = "Verificando SDK, projeto e conta Gmail…";
    try {
      const r = await api("/api/config/composio/test", { method: "POST", body: "{}" });
      el.textContent = r.success
        ? `${r.message}. ${r.accounts} conta(s) ativa(s).`
        : `${r.message || "Falhou"}. Salve a configuração e reconecte o Gmail no Composio.`;
    } catch (e) { el.textContent = e.message; }
  });
  $("#test-kie")?.addEventListener("click", async () => {
    const el = $("#test-kie-msg");
    const apiKey = val("#cfg-kie-key");
    if (!apiKey || apiKey === "***") {
      el.textContent = "Informe a API key para testar.";
      return;
    }
    el.textContent = "Testando MCP KIE…";
    try {
      const r = await api("/api/config/kie/test", { method: "POST", body: JSON.stringify({ api_key: apiKey }) });
      el.textContent = r.message || (r.success ? "Conectado" : "Falhou");
    } catch (e) { el.textContent = e.message; }
  });
  $("#load-kie-models")?.addEventListener("click", async () => {
    const el = $("#test-kie-msg");
    const apiKey = val("#cfg-kie-key");
    if (!apiKey || apiKey === "***") { el.textContent = "Informe a API key para carregar modelos."; return; }
    el.textContent = "Lendo modelos do KIE MCP…";
    try {
      const r = await api("/api/config/kie/models", { method: "POST", body: JSON.stringify({ api_key: apiKey }) });
      const select = $("#cfg-image-model");
      const current = select.value;
      select.innerHTML = (r.models || []).map((model) => `<option value="${esc(model.id)}">${esc(model.label)} (${esc(model.id)})</option>`).join("") || `<option value="${esc(current)}">${esc(current || "Nenhum modelo declarado pelo MCP")}</option>`;
      if ([...select.options].some((option) => option.value === current)) select.value = current;
      el.textContent = r.models?.length ? `${r.models.length} modelo(s) de imagem disponível(is)` : `MCP conectado, mas não declarou modelos. Ferramentas: ${(r.tools || []).join(", ")}`;
    } catch (e) { el.textContent = e.message; }
  });
  $("#generate-kie-image")?.addEventListener("click", async () => {
    const output = $("#kie-generation-result");
    const apiKey = val("#cfg-kie-key");
    const model = val("#cfg-image-model");
    const prompt = val("#kie-image-prompt");
    if (!apiKey || apiKey === "***" || !model || !prompt) { output.textContent = "Informe API key, carregue um modelo e escreva o prompt."; output.classList.remove("hidden"); return; }
    output.textContent = "Solicitando imagem ao KIE…"; output.classList.remove("hidden");
    try {
      const r = await api("/api/config/kie/generate", { method: "POST", body: JSON.stringify({ api_key: apiKey, model, prompt, aspect_ratio: val("#kie-aspect"), resolution: val("#kie-resolution") }) });
      if (!r.task_id) throw new Error(r.message || "KIE não retornou task ID");
      const poll = async (attempt = 0) => {
        output.textContent = `Imagem solicitada. Aguardando KIE… (${attempt + 1})`;
        const status = await api("/api/config/kie/status", { method: "POST", body: JSON.stringify({ api_key: apiKey, task_id: r.task_id }) });
        if (status.status === "success" && status.urls?.length) {
          output.innerHTML = `<p class="ok">Imagem gerada com sucesso.</p><div class="row">${status.urls.map((url) => `<a href="${esc(url)}" target="_blank" rel="noopener"><img src="${esc(url)}" alt="Imagem gerada pelo KIE" style="max-width:320px;border-radius:12px;border:1px solid var(--line)" /></a>`).join("")}</div>`;
          return;
        }
        if (["failed", "error", "cancelled"].includes(status.status)) {
          output.textContent = status.error || status.message || "A geração falhou.";
          return;
        }
        if (attempt >= 29) { output.textContent = `A tarefa ${r.task_id} continua processando. Use o task ID para consultar depois.`; return; }
        setTimeout(() => poll(attempt + 1), 5000);
      };
      poll();
    } catch (e) { output.textContent = e.message; }
  });
  $("#test-cf")?.addEventListener("click", async () => {
    const r = await api("/api/config/cloudflare/test", { method: "POST", body: "{}" });
    msg(r.message || JSON.stringify(r));
  });
}

boot().catch((e) => console.error(e));
