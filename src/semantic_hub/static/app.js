/* No third-party scripts, remote fonts, or persistent browser credentials. */
"use strict";
const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const state = {
  token: "",
  catalog: null,
  session: null,
  draft: null,
  dirty: false,
  page: "overview",
};
const names = {
  overview: "Overview",
  catalog: "Semantic catalog",
  graph: "Relationships",
  playground: "Query playground",
  context: "Agent context",
  editor: "Definition editor",
  history: "Version history",
};
let toastTimer;
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 5500);
}
async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(state.token ? { Authorization: "Bearer " + state.token } : {}),
      ...options.headers,
    },
  });
  if (response.status === 401) {
    if (!$("#tokenDialog").open) $("#tokenDialog").showModal();
    throw new Error("Enter an authorized API token to continue.");
  }
  if (!response.ok) {
    const data = await response.json();
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return (response.headers.get("content-type") || "").includes(
    "application/json",
  )
    ? response.json()
    : response.text();
}
const post = (path, data) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
const head = (title, description, action = "") =>
  `<div class="page-head"><div><div class="eyebrow">YOUR BUSINESS, DEFINED</div><h1>${title}</h1><p>${description}</p></div>${action}</div>`;
function metricRows(metrics) {
  return metrics
    .map(
      (m) =>
        `<tr><td><span class="metric-icon">∑</span><strong>${esc(m.label.split(" / ")[0])}</strong><small>${esc(m.id)}</small></td><td><span class="tag">${esc(m.model)}</span></td><td><span class="tag green">Published</span></td><td>${esc(m.owner)}</td></tr>`,
    )
    .join("");
}
function counts() {
  const c = state.catalog.catalog;
  return ["models", "metrics", "terms", "relationships"].map(
    (k) => c[k].length,
  );
}
async function refresh() {
  state.session = await api("/session");
  state.catalog = await api("/catalog");
  $("#workspaceName").textContent = state.catalog.catalog.name;
  $("#roleLabel").textContent = state.session.role;
  $("#environment").textContent = state.session.demo
    ? "Synthetic demo · local"
    : "Authenticated workspace";
  $("#catalogCount").textContent = state.catalog.catalog.metrics.length;
  document
    .querySelectorAll(".editor-only")
    .forEach((e) => (e.hidden = state.session.role === "viewer"));
}
async function overview() {
  const c = state.catalog.catalog,
    [models, metrics, terms, relations] = counts();
  let history = null;
  if (state.session.role !== "viewer") history = await api("/history");
  const events = history
    ? history.audit
        .slice(0, 4)
        .map(
          (a) =>
            `<div class="activity-row"><strong>${esc(a.action[0].toUpperCase() + a.action.slice(1))} revision ${a.revision}</strong><p>${esc(a.actor)}</p><small>${esc(a.created_at.replace("T", " ").slice(0, 19))} UTC</small></div>`,
        )
        .join("")
    : "<p>Published definitions are ready to explore.</p>";
  $("#main").innerHTML =
    head(
      "A shared language for your data.",
      "Bring trusted business definitions to every dashboard and AI agent.",
      `<a href="#editor" class="${state.session.role === "viewer" ? "muted" : ""}">${state.session.role === "viewer" ? "" : "Edit definitions ↗"}</a>`,
    ) +
    `<div class="stats">${[
      [models, "Semantic models", "▦", "Explicit data grains"],
      [metrics, "Business metrics", "∑", "Consistent calculations"],
      [relations, "Relationships", "⌘", "Declared join contracts"],
      [terms, "Business terms", "Aa", "Shared vocabulary"],
    ]
      .map(
        ([v, l, i, d]) =>
          `<div class="stat"><div class="stat-top">${l}<span class="stat-icon">${i}</span></div><strong>${v}</strong><small><em>●</em> ${d}</small></div>`,
      )
      .join("")}</div>
  <div class="hero"><div class="hero-icon">✧</div><div class="hero-content"><h2>Your semantics. Ready for AI.</h2><p>Give agents the right metrics, relationships and business rules — with a traceable published version behind every answer.</p></div><a href="#context">Explore agent context →</a></div>
  <div class="grid-main"><section class="card"><div class="card-head"><div><h2>Published metrics</h2><p>The definitions your team and agents can rely on</p></div><a href="#catalog">View catalog →</a></div><div class="table-wrap"><table><thead><tr><th>METRIC</th><th>MODEL</th><th>STATUS</th><th>OWNER</th></tr></thead><tbody>${metricRows(c.metrics.slice(0, 5))}</tbody></table>${!c.metrics.length ? '<div class="empty">Import your first catalog in the definition editor.</div>' : ""}</div></section>
  <section class="card"><div class="card-head"><div><h2>Workspace activity</h2><p>Changes with a clear history</p></div><span class="tag green">v${state.catalog.revision}</span></div><div class="activity">${events}</div></section></div>
  <div class="integration"><div class="integration-icon">⌁</div><div><h3>One hub. Every agent.</h3><p>Connect through REST or the read-only MCP adapter.</p></div><code>semantic-hub mcp</code><a href="/docs" target="_blank" rel="noopener">Explore API ↗</a></div>`;
}
async function catalog() {
  $("#main").innerHTML =
    head(
      "Semantic catalog",
      "Discover the meaning behind your data. Search names, descriptions and bilingual synonyms.",
    ) +
    `<div class="toolbar"><input id="search" type="search" placeholder="Search metrics, models, terms… / 搜索语义" aria-label="Search catalog"><select id="kind" aria-label="Entity type"><option value="all">All definitions</option><option value="metrics">Metrics</option><option value="models">Models</option><option value="terms">Terms</option></select></div><div id="entities" class="catalog-grid"></div><div id="entityDetail"></div>`;
  const render = () => {
    const q = $("#search").value.trim().toLowerCase(),
      kind = $("#kind").value,
      c = state.catalog.catalog;
    const entries = ["metrics", "models", "terms"]
      .flatMap((k) => c[k].map((e) => ({ kind: k, ...e })))
      .filter(
        (e) =>
          (kind === "all" || e.kind === kind) &&
          JSON.stringify(e).toLowerCase().includes(q),
      );
    $("#entities").innerHTML = entries.length
      ? entries
          .map(
            (e) =>
              `<article class="card entity" tabindex="0" role="button" data-kind="${e.kind}" data-id="${esc(e.id)}"><span class="tag ${e.kind === "metrics" ? "green" : ""}">${e.kind.slice(0, -1)}</span>${e.visibility === "internal" ? '<span class="tag amber">Internal</span>' : ""}<h2>${esc(e.label)}</h2><p>${esc(e.description)}</p><div>${e.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div><div class="bottom"><span>${esc(e.owner)}</span><span>View definition ↗</span></div></article>`,
          )
          .join("")
      : '<div class="empty">No definitions match this search.</div>';
    const show = (e) => {
      const item = c[e.dataset.kind].find((i) => i.id === e.dataset.id);
      $("#entityDetail").innerHTML =
        `<section class="card detail"><h2>${esc(item.label)}</h2><p>Published definition · revision ${state.catalog.revision}</p><pre>${esc(JSON.stringify(item, null, 2))}</pre></section>`;
      $("#entityDetail").scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    };
    document.querySelectorAll(".entity").forEach((e) => {
      e.onclick = () => show(e);
      e.onkeydown = (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          show(e);
        }
      };
    });
  };
  $("#search").oninput = render;
  $("#kind").onchange = render;
  render();
}
async function graph() {
  const g = await api("/graph"),
    positions = new Map(
      g.nodes.map((n, i) => [
        n.id,
        { x: 60 + (i % 2) * 410, y: 55 + Math.floor(i / 2) * 170 },
      ]),
    );
  const height = Math.max(300, Math.ceil(g.nodes.length / 2) * 170 + 50);
  $("#main").innerHTML =
    head(
      "Relationships with intent.",
      "A model’s grain and declared cardinality are part of the semantic contract.",
    ) +
    `<section class="card"><svg class="graph-canvas" viewBox="0 0 800 ${height}" role="img" aria-label="Model relationship graph">${g.edges
      .map((r) => {
        const a = positions.get(r.from_model),
          b = positions.get(r.to_model);
        return `<line x1="${a.x + 130}" y1="${a.y + 48}" x2="${b.x + 130}" y2="${b.y + 48}"/><text x="${(a.x + b.x) / 2 + 130}" y="${(a.y + b.y) / 2 + 35}" text-anchor="middle">${esc(r.cardinality.replaceAll("_", " "))} →</text>`;
      })
      .join("")}${g.nodes
      .map((n) => {
        const p = positions.get(n.id);
        return `<g><rect x="${p.x}" y="${p.y}" width="270" height="100" rx="10"/><text class="node-title" x="${p.x + 20}" y="${p.y + 30}">${esc(n.id)}</text><text x="${p.x + 20}" y="${p.y + 52}">${esc(n.table)}</text><text class="node-sub" x="${p.x + 20}" y="${p.y + 76}">${n.columns.length} columns · ${n.primary_key.length} primary key columns</text></g>`;
      })
      .join(
        "",
      )}</svg><div class="graph-list">${g.edges.map((r) => `<p><strong>${esc(r.id)}</strong> · ${esc(r.from_model)} (${esc(r.from_columns.join(", "))}) → ${esc(r.to_model)} (${esc(r.to_columns.join(", "))})</p>`).join("") || "<p>No relationships declared.</p>"}</div></section><div class="notice">The compiler follows one direct to-one relationship at a time. Ambiguous routes and joins that can multiply fact rows are rejected. Validate declared uniqueness against your warehouse.</div>`;
}
async function playground() {
  const c = state.catalog.catalog,
    example = {
      metrics: c.metrics.length ? [c.metrics[0].id] : [],
      dimensions: c.metrics[0]?.currency_dimension
        ? [c.metrics[0].currency_dimension]
        : [],
      filters: [],
      limit: 100,
      dialect: "hologres",
    };
  $("#main").innerHTML =
    head(
      "From business intent to SQL.",
      "Compile a structured query against published definitions. No database connection is required.",
    ) +
    `<div class="split"><section class="card panel"><h2>Query specification</h2><p>Use metric IDs and model.column dimensions.</p><div class="notice">Parameters are bound separately. Monetary metrics require an explicit currency.</div><label for="queryInput">JSON query</label><textarea id="queryInput" spellcheck="false">${esc(JSON.stringify(example, null, 2))}</textarea><div class="actions result"><button id="compile">Compile SQL →</button><button id="exampleJoin" class="secondary">Commerce example</button></div></section><section class="card panel"><div class="code-label"><span>COMPILED SQL</span><span>Published v${state.catalog.revision}</span></div><pre id="sqlOutput" class="dark-code">Your parameterized query will appear here.</pre><div id="queryMetadata" class="result"></div></section></div>`;
  $("#exampleJoin").onclick = () =>
    ($("#queryInput").value = JSON.stringify(
      {
        metrics: ["seller_gmv", "units_sold", "order_count"],
        dimensions: ["shops.region", "order_items.currency"],
        filters: [
          { field: "order_items.order_date", op: "gte", value: "2026-11-01" },
        ],
        limit: 100,
        dialect: "hologres",
      },
      null,
      2,
    ));
  $("#compile").onclick = async () => {
    try {
      const result = await post("/compile", JSON.parse($("#queryInput").value));
      $("#sqlOutput").textContent = result.sql;
      $("#queryMetadata").innerHTML =
        `<div class="code-label">PARAMETERS & LINEAGE</div><pre>${esc(JSON.stringify({ parameters: result.parameters, lineage: result.lineage, revision: result.revision }, null, 2))}</pre><div class="notice">${esc(result.warnings.join(" "))}</div>`;
      toast("SQL compiled successfully.");
    } catch (e) {
      $("#sqlOutput").textContent = e.message;
      toast(e.message);
    }
  };
}
async function agentContext() {
  $("#main").innerHTML =
    head(
      "Context your agent can trust.",
      "Retrieve relevant definitions, business rules and joins with a traceable catalog revision.",
    ) +
    `<section class="card panel"><label for="question">Business question / 业务问题</label><div class="toolbar"><input id="question" class="full" value="按地区统计商家折后 GMV" aria-label="Business question"><button id="buildContext">Build context ✧</button></div><p>English + 中文 · lexical matching · permission filtered · published definitions only</p><div id="contextResult" class="result"><pre>Ask a business question to inspect the context sent to an agent.</pre></div></section><div class="notice">This is a semantic retrieval tool. It does not generate an AI answer or execute SQL. An LLM application can consume the same package through REST or MCP.</div>`;
  $("#buildContext").onclick = async () => {
    try {
      const r = await post("/context", {
        question: $("#question").value,
        max_chars: 32000,
      });
      $("#contextResult").innerHTML =
        `<div class="code-label"><span>REVISION ${r.revision} · ${r.characters.toLocaleString()} CHARACTERS</span><span>${r.matched ? "Matches found" : "No matches — refine the question"}</span></div><pre>${esc(JSON.stringify(r.context, null, 2))}</pre>`;
    } catch (e) {
      toast(e.message);
    }
  };
}
async function editor() {
  if (state.session.role === "viewer") {
    $("#main").innerHTML = head(
      "Editor access required",
      "Ask an administrator for an editor token to manage definitions.",
    );
    return;
  }
  state.draft = await api("/catalog?channel=draft");
  const text = await api("/export?channel=draft");
  state.dirty = false;
  $("#main").innerHTML =
    head(
      "Definitions, as code.",
      "Edit the portable YAML contract. Save a validated draft, then publish an immutable revision.",
    ) +
    `<section class="card panel"><div class="code-label"><span>DRAFT v<span id="draftRevision">${state.draft.revision}</span> · PUBLISHED v${state.catalog.revision}</span><span>YAML · schema 1.0</span></div><textarea id="yamlEditor" rows="28" aria-label="Catalog YAML" spellcheck="false">${esc(text)}</textarea><div class="toolbar result"><input id="changeMessage" placeholder="Describe this change…" aria-label="Change message"><button id="validateYaml" class="secondary">Validate</button><button id="saveDraft">Save draft</button><button id="publishDraft" ${state.session.role !== "admin" ? "disabled" : ""}>Publish revision ↗</button></div><div id="validationResult"></div></section>`;
  $("#yamlEditor").oninput = () => {
    state.dirty = true;
    $("#publishDraft").disabled = true;
  };
  const parse = async () => {
    const r = await post("/parse-yaml", { yaml: $("#yamlEditor").value });
    $("#validationResult").innerHTML = r.errors.length
      ? `<pre class="error">${esc(JSON.stringify(r.errors, null, 2))}</pre>`
      : '<div class="notice">Valid schema, references, types and declared join keys.</div>';
    if (r.errors.length)
      throw new Error(
        "Semantic validation failed. Resolve the reported errors.",
      );
    return r.catalog;
  };
  $("#validateYaml").onclick = async () => {
    try {
      await parse();
      toast("Definition is valid.");
    } catch (e) {
      $("#validationResult").innerHTML =
        `<pre class="error">${esc(e.message)}</pre>`;
    }
  };
  $("#saveDraft").onclick = async () => {
    try {
      const c = await parse(),
        message = $("#changeMessage").value.trim();
      if (!message) throw new Error("Describe your change before saving.");
      const r = await api("/draft", {
        method: "PUT",
        body: JSON.stringify({
          catalog: c,
          expected_revision: state.draft.revision,
          message,
        }),
      });
      state.draft.revision = r.revision;
      state.dirty = false;
      $("#draftRevision").textContent = r.revision;
      $("#publishDraft").disabled = state.session.role !== "admin";
      toast("Draft saved. Published definitions are unchanged.");
    } catch (e) {
      toast(e.message);
    }
  };
  $("#publishDraft").onclick = async () => {
    try {
      if (state.dirty) throw new Error("Save the draft before publishing.");
      if (
        !confirm(
          "Publish draft revision " +
            state.draft.revision +
            " for all API and agent consumers?",
        )
      )
        return;
      await post("/publish", { expected_revision: state.draft.revision });
      await refresh();
      toast("Revision published.");
      await editor();
    } catch (e) {
      toast(e.message);
    }
  };
}
async function history() {
  if (state.session.role === "viewer") {
    $("#main").innerHTML = head(
      "Editor access required",
      "Revision history includes drafts.",
    );
    return;
  }
  const h = await api("/history");
  $("#main").innerHTML =
    head(
      "Every change has a history.",
      "Immutable snapshots, optimistic concurrency and an explicit publication step.",
    ) +
    `<section class="card"><div class="table-wrap"><table><thead><tr><th>REVISION</th><th>CHANGE</th><th>AUTHOR</th><th>CREATED · UTC</th><th>ACTION</th></tr></thead><tbody>${h.revisions.map((r) => `<tr><td><strong>v${r.revision}</strong>${h.state.published === r.revision ? '<span class="tag green">Published</span>' : ""}${h.state.draft === r.revision ? '<span class="tag">Draft head</span>' : ""}</td><td>${esc(r.message)}<small>${esc(r.digest.slice(0, 16))}</small></td><td>${esc(r.actor)}</td><td>${esc(r.created_at.replace("T", " ").slice(0, 19))}</td><td><button class="secondary small restore" data-revision="${r.revision}">Restore as draft</button></td></tr>`).join("")}</tbody></table></div></section><section class="card panel result"><h2>Audit trail</h2><pre>${esc(JSON.stringify(h.audit, null, 2))}</pre></section>`;
  document.querySelectorAll(".restore").forEach(
    (b) =>
      (b.onclick = async () => {
        try {
          if (
            !confirm(
              "Restore revision " +
                b.dataset.revision +
                " as a new draft? Publication is a separate step.",
            )
          )
            return;
          await post("/restore", {
            revision: Number(b.dataset.revision),
            expected_revision: h.state.draft,
          });
          toast("Restored as a new draft.");
          await history();
        } catch (e) {
          toast(e.message);
        }
      }),
  );
}
const pages = {
  overview,
  catalog,
  graph,
  playground,
  context: agentContext,
  editor,
  history,
};
async function route() {
  const next = location.hash.slice(1) || "overview";
  if (
    state.dirty &&
    next !== state.page &&
    !confirm("Leave this page and discard unsaved YAML edits?")
  ) {
    window.history.replaceState(null, "", "#" + state.page);
    return;
  }
  state.dirty = false;
  state.page = next;
  if (!pages[state.page]) state.page = "overview";
  $("#breadcrumb").textContent = names[state.page];
  document
    .querySelectorAll("nav a")
    .forEach((a) =>
      a.classList.toggle("active", a.dataset.page === state.page),
    );
  try {
    if (!state.catalog) await refresh();
    await pages[state.page]();
  } catch (e) {
    $("#main").innerHTML = head("Unable to load workspace", esc(e.message));
    toast(e.message);
  }
}
$("#tokenButton").onclick = () => $("#tokenDialog").showModal();
$("#cancelToken").onclick = () => $("#tokenDialog").close();
$("#tokenForm").onsubmit = async (e) => {
  e.preventDefault();
  state.token = $("#tokenInput").value.trim();
  $("#tokenInput").value = "";
  $("#tokenDialog").close();
  state.catalog = null;
  await route();
};
window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => {
  if (state.dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
route();
