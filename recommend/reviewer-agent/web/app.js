// 前端独立运行时（5173）请求后端 API（8000）；与后端同域时留空
const API_BASE =
  window.location.port && window.location.port !== "8000"
    ? "http://127.0.0.1:8000"
    : "";
const ENDPOINTS = {
  health: `${API_BASE}/health`,
  recommend: `${API_BASE}/api/v1/recommend/reviewers`,
  refineKeywords: `${API_BASE}/api/v1/keywords/refine`,
  authorPubs: `${API_BASE}/api/v1/authors/publications/stats`,
};

const ROLE_COLORS = {
  first: "#2563eb",
  corresponding: "#0f766e",
  other: "#94a3b8",
};

const form = document.getElementById("recommendForm");
const submitBtn = document.getElementById("submitBtn");
const stopBtn = document.getElementById("stopBtn");
const keywordConfirm = document.getElementById("keywordConfirm");
const keywordReasoning = document.getElementById("keywordReasoning");
const confirmedKeywordsInput = document.getElementById("confirmedKeywords");
const confirmKeywordsBtn = document.getElementById("confirmKeywordsBtn");
const cancelKeywordsBtn = document.getElementById("cancelKeywordsBtn");
const connectionStatus = document.getElementById("connectionStatus");
const stageTabs = document.getElementById("stageTabs");

const stage1Body = document.getElementById("stage1Body");
const stage2Body = document.getElementById("stage2Body");
const stage3Body = document.getElementById("stage3Body");
const resultBody = document.getElementById("resultBody");
const pubsModal = document.getElementById("pubsModal");
const pubsModalTitle = document.getElementById("pubsModalTitle");
const pubsModalSubtitle = document.getElementById("pubsModalSubtitle");
const pubsModalBody = document.getElementById("pubsModalBody");
const pubsModalClose = document.getElementById("pubsModalClose");

const stage1State = document.getElementById("stage1State");
const stage2State = document.getElementById("stage2State");
const stage3State = document.getElementById("stage3State");
const resultState = document.getElementById("resultState");

let abortController = null;
let pendingPayload = null;
let activeFilter = "all";
let lastReviewers = [];
let lastStage1Experts = [];
let activePaperKeywords = "";
const stage2Progress = [];
const pubsCache = new Map();
let pubsRequestToken = 0;

function setConnectionStatus(kind, text) {
  connectionStatus.className = `status-pill ${kind}`;
  connectionStatus.querySelector("span:last-child").textContent = text;
}

async function checkHealth() {
  try {
    const res = await fetch(ENDPOINTS.health);
    if (!res.ok) throw new Error("health failed");
    setConnectionStatus("ok", "服务正常");
  } catch {
    setConnectionStatus("error", "服务未连接");
  }
}

function setStageCard(stage, status) {
  const card = document.querySelector(`.stage-card[data-stage="${stage}"]`);
  if (!card) return;
  card.classList.remove("idle", "active", "done");
  card.classList.add(status);
}

function setStageLabel(el, text) {
  if (el) el.textContent = text;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pubsCacheKey(item) {
  return `${item.id || ""}|${item.name || ""}|${activePaperKeywords}`;
}

function renderKeywordTags(keywords) {
  const items = (keywords || []).filter(Boolean).slice(0, 6);
  if (!items.length) return `<span class="muted">-</span>`;
  return `
    <div class="kw-tags">
      ${items.map((kw) => `<span class="kw-tag" title="${escapeHtml(kw)}">${escapeHtml(kw)}</span>`).join("")}
    </div>
  `;
}

function renderOverlapCell(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return `<span class="muted">-</span>`;
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  let tone = "low";
  if (value >= 0.8) tone = "high";
  else if (value >= 0.5) tone = "mid";
  return `
    <div class="overlap-cell" title="重合度 ${value.toFixed(2)}">
      <span class="overlap-value tone-${tone}">${value.toFixed(2)}</span>
      <span class="overlap-bar"><i style="width:${pct}%"></i></span>
    </div>
  `;
}

function renderStage1Row(item) {
  const hasEmail = Boolean(item.email?.trim());
  const canViewPubs = Boolean(item.name?.trim() && activePaperKeywords);
  const org = item.org || "-";
  const subject = item.subject || "-";
  return `
    <tr class="${item.selected ? "row-selected" : ""}">
      <td class="col-name">
        <div class="name-cell">
          <span class="rank-pill">#${item.rank}</span>
          <strong class="name-text" title="${escapeHtml(item.name || "")}">${escapeHtml(item.name || "-")}</strong>
        </div>
      </td>
      <td class="col-org" title="${escapeHtml(org)}">${escapeHtml(org)}</td>
      <td class="col-subject" title="${escapeHtml(subject)}">${escapeHtml(subject)}</td>
      <td class="col-overlap">${renderOverlapCell(item.overlap_score)}</td>
      <td class="col-hindex">${item.hindex ?? "-"}</td>
      <td class="col-keywords">${renderKeywordTags(item.research_keywords)}</td>
      <td class="col-stage2">
        ${
          item.selected
            ? '<span class="badge-selected">入选</span>'
            : '<span class="badge-muted">未入选</span>'
        }
      </td>
      <td class="col-actions">
        <button
          type="button"
          class="table-action-btn stage1-pubs-btn"
          data-rank="${item.rank}"
          ${canViewPubs ? "" : "disabled"}
        >发文</button>
      </td>
      <td class="col-actions">
        <button
          type="button"
          class="table-action-btn stage1-copy-btn"
          data-rank="${item.rank}"
          title="${hasEmail ? escapeHtml(item.email) : "无邮箱"}"
          ${hasEmail ? "" : "disabled"}
        >邮箱</button>
      </td>
    </tr>
  `;
}

function getFilteredStage1Experts() {
  const query = (document.getElementById("stage1Search")?.value || "").trim().toLowerCase();
  const selectedOnly = document.getElementById("stage1SelectedOnly")?.checked;
  return lastStage1Experts.filter((item) => {
    if (selectedOnly && !item.selected) return false;
    if (!query) return true;
    const haystack = [
      item.name,
      item.org,
      item.subject,
      ...(item.research_keywords || []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function updateStage1TableBody() {
  const tbody = document.getElementById("stage1TableBody");
  const countEl = document.getElementById("stage1Count");
  if (!tbody) return;

  const filtered = getFilteredStage1Experts();
  tbody.innerHTML = filtered.map(renderStage1Row).join("");
  if (countEl) {
    countEl.textContent = `显示 ${filtered.length} / ${lastStage1Experts.length} 人`;
  }
}

function renderStage1(thinking) {
  lastStage1Experts = thinking.experts || thinking.selected || [];
  pubsCache.clear();
  setStageCard("stage1", "done");
  setStageLabel(stage1State, `${lastStage1Experts.length} 位专家`);

  const hasAnyEmail = lastStage1Experts.some((item) => item.email?.trim());

  stage1Body.innerHTML = `
    <div class="stats-row">
      <span class="stat-chip">API 召回 ${thinking.total_from_api ?? 0} 人</span>
      <span class="stat-chip">COI 后 ${thinking.after_coi ?? 0} 人</span>
      <span class="stat-chip">排序 ${thinking.ranked_count ?? lastStage1Experts.length} 人</span>
      <span class="stat-chip">阈值 ≥ ${(thinking.min_overlap_threshold ?? 0.5).toFixed?.(2) ?? thinking.min_overlap_threshold ?? "0.5"}</span>
      <span class="stat-chip">入选 ${thinking.selected_count ?? 0} 人</span>
    </div>
    <pre class="summary-block">${escapeHtml(thinking.summary || "")}</pre>
    <div class="stage1-toolbar">
      <input
        type="search"
        id="stage1Search"
        class="stage1-search"
        placeholder="搜索姓名、机构、学科、关键词…"
      />
      <label class="stage1-filter">
        <input type="checkbox" id="stage1SelectedOnly" />
        仅看入选（${thinking.selected_count ?? 0} 人）
      </label>
      ${
        hasAnyEmail
          ? `<button type="button" class="copy-all-btn" id="copyAllStage1Emails">复制全部邮箱</button>`
          : ""
      }
      <span class="stage1-count" id="stage1Count"></span>
    </div>
    <div class="table-scroll stage1-scroll">
      <table class="candidate-table stage1-table">
        <thead>
          <tr>
            <th class="col-name">姓名</th>
            <th class="col-org">机构</th>
            <th class="col-subject">学科</th>
            <th class="col-overlap">重合度</th>
            <th class="col-hindex">H 指数</th>
            <th class="col-keywords">研究方向</th>
            <th class="col-stage2">阶段二</th>
            <th class="col-actions">发文</th>
            <th class="col-actions">邮箱</th>
          </tr>
        </thead>
        <tbody id="stage1TableBody"></tbody>
      </table>
    </div>
  `;
  updateStage1TableBody();
}

function renderStage2Progress(thinking) {
  if (thinking.progress) {
    stage2Progress.push(thinking);
  }
}

function renderStage2Summary(thinking) {
  setStageCard("stage2", "done");
  setStageLabel(stage2State, "已完成");

  const progressHtml = stage2Progress
    .map(
      (item) => `
        <div class="progress-item">
          <span><strong>${escapeHtml(item.name)}</strong> · ${escapeHtml(item.org)}</span>
          <span>${escapeHtml(item.progress)} · score ${item.activity_score}</span>
        </div>
      `
    )
    .join("");

  const candidateRows = (thinking.candidates || [])
    .map(
      (item) => `
        <tr>
          <td>${item.rank}</td>
          <td><strong>${escapeHtml(item.name)}</strong><br/><span class="muted">${escapeHtml(item.org)}</span></td>
          <td>${item.pubs_last_2_years ?? 0}</td>
          <td>${item.activity_score ?? "-"}</td>
          <td>${escapeHtml(item.top_paper || "-")}</td>
        </tr>
      `
    )
    .join("");

  stage2Body.innerHTML = `
    <div class="progress-list">${progressHtml}</div>
    <pre class="summary-block">${escapeHtml(thinking.summary || "")}</pre>
    <table class="candidate-table">
      <thead>
        <tr>
          <th>#</th>
          <th>学者</th>
          <th>近2年发文</th>
          <th>活跃度</th>
          <th>代表作</th>
        </tr>
      </thead>
      <tbody>${candidateRows}</tbody>
    </table>
  `;
}

function ensureStage3Stream() {
  if (!document.getElementById("stage3Stream")) {
    stage3Body.innerHTML = `<div id="stage3Stream" class="thinking-stream"></div>`;
  }
}

function appendStage3Text(text) {
  ensureStage3Stream();
  const stream = document.getElementById("stage3Stream");
  stream.textContent += text;
  stream.scrollTop = stream.scrollHeight;
}

function renderStage3Summary(thinking) {
  setStageCard("stage3", "active");
  setStageLabel(stage3State, "进行中");
  ensureStage3Stream();
  if (thinking?.summary) {
    appendStage3Text(`${thinking.summary}\n\n`);
  }
}

function renderRecentPapers(papers) {
  const items = (papers || []).filter((p) => p?.title?.trim());
  if (!items.length) {
    return `<p class="reviewer-meta muted">暂无近期发文记录</p>`;
  }
  return `
    <ul class="recent-paper-list">
      ${items
        .slice(0, 5)
        .map(
          (paper) => `
            <li>
              ${paper.year ? `<span class="paper-year">${escapeHtml(paper.year)}</span>` : ""}
              ${escapeHtml(paper.title)}
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

function renderResearchField(item) {
  const keywords = (item.research_keywords || []).filter(Boolean);
  if (keywords.length) {
    return keywords.slice(0, 8).join("、");
  }
  return item.subject || "-";
}

function renderResult(reviewers) {
  lastReviewers = reviewers;
  setStageCard("stage3", "done");
  setStageLabel(stage3State, "已完成");
  setStageCard("result", "done");
  setStageLabel(resultState, `${reviewers.length} 位推荐`);

  resultBody.innerHTML = `
    <div class="reviewer-grid">
      ${reviewers
        .map((item, index) => {
          const canViewPubs = Boolean(item.name?.trim() && activePaperKeywords);
          return `
            <article class="reviewer-card">
              <div class="reviewer-head">
                <div>
                  <h4>${escapeHtml(item.name)}</h4>
                  <p class="reviewer-org">${escapeHtml(item.org || "-")}</p>
                </div>
                <div class="reviewer-actions">
                  <button
                    type="button"
                    class="copy-btn result-pubs-btn"
                    data-index="${index}"
                    ${canViewPubs ? "" : "disabled"}
                  >查看发文</button>
                  <button
                    type="button"
                    class="copy-btn"
                    data-index="${index}"
                    ${item.email?.trim() ? "" : "disabled"}
                  >复制邮箱</button>
                </div>
              </div>
              <dl class="reviewer-meta-grid">
                <div>
                  <dt>研究领域</dt>
                  <dd>${escapeHtml(renderResearchField(item))}</dd>
                </div>
                <div>
                  <dt>H 指数</dt>
                  <dd>${item.hindex ?? "-"}</dd>
                </div>
                <div>
                  <dt>近 2 年发文</dt>
                  <dd>${item.pubs_last_2_years ?? 0} 篇</dd>
                </div>
              </dl>
              <div class="reviewer-section">
                <p class="reviewer-section-title">最近发文</p>
                ${renderRecentPapers(item.recent_papers)}
              </div>
              ${
                item.matched_paper?.trim()
                  ? `<p class="reviewer-paper">匹配论文：${escapeHtml(item.matched_paper)}</p>`
                  : ""
              }
              <p class="reviewer-reason">${escapeHtml(item.reason || "")}</p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

async function copyText(text, button) {
  const value = text?.trim();
  if (!value) return false;

  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }

  if (button) {
    const original = button.textContent;
    button.textContent = "已复制";
    button.classList.add("copied");
    window.setTimeout(() => {
      button.textContent = original;
      button.classList.remove("copied");
    }, 2000);
  }
  return true;
}

function renderError(message) {
  const box = `<div class="error-box">${escapeHtml(message)}</div>`;
  if (!stage1Body.querySelector(".error-box")) stage1Body.innerHTML = box;
  else if (!resultBody.querySelector(".reviewer-card")) resultBody.innerHTML = box;
}

function resetUI() {
  lastReviewers = [];
  lastStage1Experts = [];
  stage2Progress.length = 0;
  ["stage1", "stage2", "stage3", "result"].forEach((stage) => {
    setStageCard(stage, stage === "stage1" ? "active" : "idle");
  });
  setStageLabel(stage1State, "进行中");
  setStageLabel(stage2State, "等待中");
  setStageLabel(stage3State, "等待中");
  setStageLabel(resultState, "等待中");

  stage1Body.innerHTML = `<p class="placeholder">正在拉取候选人…</p>`;
  stage2Body.innerHTML = `<p class="placeholder">等待阶段一完成…</p>`;
  stage3Body.innerHTML = `<p class="placeholder">等待阶段二完成…</p>`;
  resultBody.innerHTML = `<p class="placeholder">推荐完成后展示…</p>`;
}

function applyStageFilter(filter) {
  activeFilter = filter;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.stage === filter);
  });
  document.querySelectorAll(".stage-card").forEach((card) => {
    const stage = card.dataset.stage;
    const visible = filter === "all" || filter === stage;
    card.classList.toggle("hidden", !visible);
  });
}

function handleEvent(event) {
  switch (event.event) {
    case "stage1_thinking":
      renderStage1(event.thinking || {});
      setStageCard("stage2", "active");
      setStageLabel(stage2State, "进行中");
      stage2Body.innerHTML = `<p class="placeholder">正在补全学者背景…</p>`;
      break;

    case "stage2_thinking": {
      const thinking = event.thinking || {};
      if (thinking.progress) {
        renderStage2Progress(thinking);
        stage2Body.innerHTML = `
          <div class="progress-list">
            ${stage2Progress
              .map(
                (item) => `
                  <div class="progress-item">
                    <span><strong>${escapeHtml(item.name)}</strong> · ${escapeHtml(item.org)}</span>
                    <span>${escapeHtml(item.progress)} · score ${item.activity_score}</span>
                  </div>
                `
              )
              .join("")}
          </div>
        `;
      } else if (thinking.summary) {
        renderStage2Summary(thinking);
        setStageCard("stage3", "active");
        setStageLabel(stage3State, "进行中");
        stage3Body.innerHTML = `<div id="stage3Stream" class="thinking-stream"></div>`;
      }
      break;
    }

    case "stage3_thinking":
      if (event.thinking?.summary) {
        renderStage3Summary(event.thinking);
      } else if (event.chunk) {
        appendStage3Text(event.chunk);
      }
      break;

    case "stage3_done":
      renderResult(event.reviewers || []);
      setConnectionStatus("ok", "推荐完成");
      break;

    case "error":
      renderError(event.message || "未知错误");
      setConnectionStatus("error", "运行失败");
      break;

    default:
      break;
  }
}

async function startRecommend(payload) {
  resetUI();
  setConnectionStatus("running", "推荐进行中…");
  submitBtn.disabled = true;
  stopBtn.disabled = false;

  abortController = new AbortController();

  try {
    const res = await fetch(ENDPOINTS.recommend, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: abortController.signal,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          handleEvent(JSON.parse(line));
        } catch (err) {
          console.warn("跳过无法解析的行:", line, err);
        }
      }
    }

    if (buffer.trim()) {
      handleEvent(JSON.parse(buffer));
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      renderError(err.message || String(err));
      setConnectionStatus("error", "运行失败");
    } else {
      setConnectionStatus("ok", "已停止");
    }
  } finally {
    submitBtn.disabled = false;
    stopBtn.disabled = true;
    abortController = null;
  }
}

function showKeywordConfirm(keywords, reasoning) {
  confirmedKeywordsInput.value = keywords.join(",");
  keywordReasoning.textContent = reasoning ? `提炼说明：${reasoning}` : "";
  keywordReasoning.classList.toggle("hidden", !reasoning);
  keywordConfirm.classList.remove("hidden");
  confirmedKeywordsInput.focus();
}

function hideKeywordConfirm() {
  keywordConfirm.classList.add("hidden");
  pendingPayload = null;
}

async function refineKeywords(payload) {
  submitBtn.disabled = true;
  submitBtn.textContent = "提炼中…";
  setConnectionStatus("running", "关键词提炼中…");

  try {
    const res = await fetch(ENDPOINTS.refineKeywords, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: payload.title,
        abstract: payload.abstract,
        keywords: payload.keywords,
      }),
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        /* keep */
      }
      throw new Error(detail);
    }
    const data = await res.json();
    pendingPayload = payload;
    showKeywordConfirm(data.keywords || [], data.reasoning || "");
    setConnectionStatus("ok", "请确认关键词");
  } catch (err) {
    renderError(`关键词提炼失败：${err.message || err}`);
    setConnectionStatus("error", "提炼失败");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "提炼关键词";
  }
}

function openPubsModal(expert) {
  pubsModalTitle.textContent = "历史发文统计";
  pubsModalSubtitle.textContent = `${expert.name}${expert.org ? ` · ${expert.org}` : ""} · 关键词 ${activePaperKeywords}`;
  pubsModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closePubsModal() {
  pubsModal.classList.add("hidden");
  document.body.style.overflow = "";
}

function renderPubsChartSvg(series) {
  const years = series.years || [];
  const first = series.first || [];
  const corresponding = series.corresponding || [];
  const other = series.other || [];
  if (!years.length) {
    return `<p class="placeholder">该条件下未匹配到发文</p>`;
  }

  const width = Math.max(420, years.length * 48 + 64);
  const height = 280;
  const pad = { top: 20, right: 16, bottom: 40, left: 40 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;
  const totals = years.map(
    (_, i) => (first[i] || 0) + (corresponding[i] || 0) + (other[i] || 0)
  );
  const maxY = Math.max(...totals, 1);
  const barW = Math.min(36, (chartW / years.length) * 0.62);
  const gap = chartW / years.length;

  const ticks = 4;
  const grid = [];
  for (let t = 0; t <= ticks; t += 1) {
    const value = Math.round((maxY * t) / ticks);
    const y = pad.top + chartH - (value / maxY) * chartH;
    grid.push(`
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" stroke="#e2e8f0" />
      <text x="${pad.left - 8}" y="${y + 4}" text-anchor="end" fill="#94a3b8" font-size="11">${value}</text>
    `);
  }

  const bars = years
    .map((year, i) => {
      const x = pad.left + gap * i + (gap - barW) / 2;
      let y = pad.top + chartH;
      const segments = [
        { key: "other", value: other[i] || 0, color: ROLE_COLORS.other },
        { key: "corresponding", value: corresponding[i] || 0, color: ROLE_COLORS.corresponding },
        { key: "first", value: first[i] || 0, color: ROLE_COLORS.first },
      ];
      const rects = segments
        .filter((seg) => seg.value > 0)
        .map((seg) => {
          const h = (seg.value / maxY) * chartH;
          y -= h;
          const label =
            seg.key === "first" ? "一作" : seg.key === "corresponding" ? "通讯" : "其他";
          return `<rect x="${x}" y="${y}" width="${barW}" height="${h}" fill="${seg.color}" rx="2">
            <title>${year} · ${label}：${seg.value}</title>
          </rect>`;
        })
        .join("");
      return `
        ${rects}
        <text x="${x + barW / 2}" y="${height - 14}" text-anchor="middle" fill="#64748b" font-size="11">${year}</text>
      `;
    })
    .join("");

  return `
    <div class="pubs-chart-wrap">
      <svg class="pubs-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="历史发文柱状图">
        ${grid.join("")}
        ${bars}
      </svg>
    </div>
  `;
}

function renderAuthorNames(authors, targetName, sequence) {
  const names = authors || [];
  if (!names.length) return `<span class="muted">作者信息缺失</span>`;
  return names
    .map((name, index) => {
      const isTarget =
        String(name).replace(/\s+/g, "") === String(targetName || "").replace(/\s+/g, "") ||
        (sequence != null && index + 1 === Number(sequence));
      return isTarget
        ? `<strong class="author-highlight">${escapeHtml(name)}</strong><span class="author-seq-tag">第${sequence ?? index + 1}作者</span>`
        : `<span>${escapeHtml(name)}</span>`;
    })
    .join('<span class="author-sep">，</span>');
}

function renderPubsPaperList(papers, authorName) {
  const items = papers || [];
  if (!items.length) {
    return `<p class="placeholder">暂无论文列表</p>`;
  }
  return `
    <div class="pubs-paper-list">
      <h4 class="pubs-paper-title">论文列表 <span class="muted">（最近优先）</span></h4>
      ${items
        .map((paper) => {
          const roleClass =
            paper.role === "first"
              ? "role-first"
              : paper.role === "corresponding"
                ? "role-corresponding"
                : "role-other";
          const meta = [
            paper.year ? `${paper.year}` : "",
            paper.journal || "",
          ]
            .filter(Boolean)
            .join(" · ");
          const titleHtml = paper.article_url
            ? `<a href="${escapeHtml(paper.article_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(paper.title || "无标题")}</a>`
            : escapeHtml(paper.title || "无标题");
          return `
            <article class="pubs-paper-item ${roleClass}">
              <div class="pubs-paper-head">
                <span class="pubs-role-badge ${roleClass}">${escapeHtml(paper.role_label || "作者")}</span>
                <span class="pubs-paper-meta">${escapeHtml(meta || "-")}</span>
              </div>
              <h5 class="pubs-paper-name">${titleHtml}</h5>
              <p class="pubs-paper-authors">${renderAuthorNames(paper.authors, authorName, paper.author_sequence)}</p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPubsStats(data) {
  const totalMatched =
    (data.totals?.first || 0) +
    (data.totals?.corresponding || 0) +
    (data.totals?.other || 0);
  pubsModalTitle.textContent = `历史发文 · 共 ${totalMatched} 篇`;
  pubsModalSubtitle.textContent = `${data.author}${data.org ? ` · ${data.org}` : ""} · ${(data.keywords || []).join("、")}`;
  pubsModalBody.innerHTML = `
    <div class="stats-row">
      <span class="stat-chip">拉取 ${data.fetched ?? 0}</span>
      <span class="stat-chip">关键词命中 ${data.keyword_matched ?? 0}</span>
      <span class="stat-chip">一作 ${data.totals?.first ?? 0}</span>
      <span class="stat-chip">通讯 ${data.totals?.corresponding ?? 0}</span>
      <span class="stat-chip">其他 ${data.totals?.other ?? 0}</span>
    </div>
    <div class="pubs-legend">
      <span class="pubs-legend-item"><span class="pubs-legend-swatch" style="background:${ROLE_COLORS.first}"></span>一作</span>
      <span class="pubs-legend-item"><span class="pubs-legend-swatch" style="background:${ROLE_COLORS.corresponding}"></span>通讯</span>
      <span class="pubs-legend-item"><span class="pubs-legend-swatch" style="background:${ROLE_COLORS.other}"></span>其他</span>
    </div>
    ${renderPubsChartSvg(data.series || {})}
    <p class="pubs-note">${escapeHtml(data.role_note || "")}</p>
    ${renderPubsPaperList(data.papers || [], data.author)}
  `;
}

async function queryAuthorPubs(expert) {
  openPubsModal(expert);
  const cacheKey = pubsCacheKey(expert);
  const cached = pubsCache.get(cacheKey);
  if (cached) {
    renderPubsStats(cached);
    return;
  }

  const token = ++pubsRequestToken;
  pubsModalBody.innerHTML = `<p class="placeholder">正在按姓名 + 关键词拉取历史发文…</p>`;
  setConnectionStatus("running", "发文查询中…");

  try {
    const res = await fetch(ENDPOINTS.authorPubs, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        author: expert.name,
        keywords: activePaperKeywords,
        org: expert.org || "",
        author_id: expert.id || "",
        pub_year: "",
      }),
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        /* keep */
      }
      throw new Error(detail);
    }
    const data = await res.json();
    if (token !== pubsRequestToken) return;
    pubsCache.set(cacheKey, data);
    renderPubsStats(data);
    setConnectionStatus("ok", "发文查询完成");
  } catch (err) {
    if (token !== pubsRequestToken) return;
    pubsModalBody.innerHTML = `<div class="error-box">${escapeHtml(err.message || String(err))}</div>`;
    setConnectionStatus("error", "发文查询失败");
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  hideKeywordConfirm();
  const data = new FormData(form);
  refineKeywords({
    title: data.get("title").trim(),
    abstract: data.get("abstract").trim(),
    keywords: data.get("keywords").trim(),
    author_org: data.get("author_org").trim(),
    extra: data.get("extra").trim(),
  });
});

confirmKeywordsBtn.addEventListener("click", () => {
  if (!pendingPayload) return;
  const keywords = confirmedKeywordsInput.value
    .split(/[,，]/)
    .map((word) => word.trim())
    .filter(Boolean)
    .join(",");
  if (!keywords) {
    confirmedKeywordsInput.focus();
    return;
  }
  const payload = { ...pendingPayload, keywords };
  activePaperKeywords = keywords;
  hideKeywordConfirm();
  startRecommend(payload);
});

cancelKeywordsBtn.addEventListener("click", () => {
  hideKeywordConfirm();
  setConnectionStatus("ok", "服务正常");
});

stopBtn.addEventListener("click", () => {
  abortController?.abort();
});

pubsModalClose.addEventListener("click", closePubsModal);
pubsModal.addEventListener("click", (e) => {
  if (e.target === pubsModal) closePubsModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !pubsModal.classList.contains("hidden")) {
    closePubsModal();
  }
});

stageTabs.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (!tab) return;
  applyStageFilter(tab.dataset.stage);
});

resultBody.addEventListener("click", async (e) => {
  const pubsBtn = e.target.closest(".result-pubs-btn");
  if (pubsBtn) {
    const index = Number(pubsBtn.dataset.index);
    const reviewer = lastReviewers[index];
    if (!reviewer) return;
    pubsBtn.disabled = true;
    const original = pubsBtn.textContent;
    pubsBtn.textContent = "加载中…";
    try {
      await queryAuthorPubs({
        id: reviewer.candidate_id || reviewer.id || "",
        name: reviewer.name,
        org: reviewer.org || "",
      });
    } finally {
      pubsBtn.disabled = !(reviewer.name?.trim() && activePaperKeywords);
      pubsBtn.textContent = original;
    }
    return;
  }

  const copyBtn = e.target.closest(".copy-btn");
  if (copyBtn) {
    const index = Number(copyBtn.dataset.index);
    const email = lastReviewers[index]?.email;
    await copyText(email, copyBtn);
  }
});

stage1Body.addEventListener("input", (e) => {
  if (e.target.id === "stage1Search") {
    updateStage1TableBody();
  }
});

stage1Body.addEventListener("change", (e) => {
  if (e.target.id === "stage1SelectedOnly") {
    updateStage1TableBody();
  }
});

stage1Body.addEventListener("click", async (e) => {
  const pubsBtn = e.target.closest(".stage1-pubs-btn");
  if (pubsBtn) {
    const rank = Number(pubsBtn.dataset.rank);
    const expert = lastStage1Experts.find((item) => item.rank === rank);
    if (!expert) return;
    pubsBtn.disabled = true;
    const original = pubsBtn.textContent;
    pubsBtn.textContent = "加载中…";
    try {
      await queryAuthorPubs(expert);
    } finally {
      pubsBtn.disabled = !(expert.name?.trim() && activePaperKeywords);
      pubsBtn.textContent = original;
    }
    return;
  }

  const copyBtn = e.target.closest(".stage1-copy-btn");
  if (copyBtn) {
    const rank = Number(copyBtn.dataset.rank);
    const expert = lastStage1Experts.find((item) => item.rank === rank);
    await copyText(expert?.email, copyBtn);
    return;
  }

  const copyAllBtn = e.target.closest("#copyAllStage1Emails");
  if (copyAllBtn) {
    const emails = lastStage1Experts
      .map((item) => item.email?.trim())
      .filter(Boolean)
      .join("\n");
    await copyText(emails, copyAllBtn);
  }
});

checkHealth();
