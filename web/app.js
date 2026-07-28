// 本地前端独立端口（5173）才打到本机后端；Railway / 同域部署用相对路径
const API_BASE =
  window.location.port === "5173"
    ? "http://127.0.0.1:8000"
    : "";
const ENDPOINTS = {
  health: `${API_BASE}/health`,
  recommend: `${API_BASE}/api/v1/recommend/reviewers`,
  refineKeywords: `${API_BASE}/api/v1/keywords/refine`,
  authorPubs: `${API_BASE}/api/v1/authors/publications/stats`,
};

const ROLE_COLORS = {
  first: "#1a73e8",
  corresponding: "#e37400",
  other: "#9aa0a6",
};

/** @type {any} */
let lastPubsData = null;
/** @type {number | null} */
let pubsFilterYear = null;

const PUBS_LINK_ICON = `
  <svg class="pubs-link-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42L17.59 5H14V3z"/>
    <path d="M5 5h6v2H7v10h10v-4h2v6H5V5z"/>
  </svg>
`;

const form = document.getElementById("recommendForm");
const directSearchBtn = document.getElementById("directSearchBtn");
const refineBtn = document.getElementById("refineBtn");
const newPaperBtn = document.getElementById("newPaperBtn");
const stopBtn = document.getElementById("stopBtn");
const connectionStatus = document.getElementById("connectionStatus");
const stageTabs = document.getElementById("stageTabs");
const modeHint = document.getElementById("modeHint");
const keywordsLabel = document.getElementById("keywordsLabel");
const keywordsTip = document.getElementById("keywordsTip");
const modeDirectBtn = document.getElementById("modeDirectBtn");
const modeRefineBtn = document.getElementById("modeRefineBtn");
const refinedKeywordsPanel = document.getElementById("refinedKeywordsPanel");
const refinedKeywordsToggle = document.getElementById("refinedKeywordsToggle");
const refinedKeywordsToggleLabel = document.getElementById("refinedKeywordsToggleLabel");
const refinedKeywordsTags = document.getElementById("refinedKeywordsTags");
const refinedKeywordsReasoning = document.getElementById("refinedKeywordsReasoning");

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
/** @type {"overlap" | "pubs5" | "hindex"} */
let stage1SortBy = "overlap";
let activePaperKeywords = "";
const stage2Progress = [];
const pubsCache = new Map();
let pubsRequestToken = 0;
/** @type {"direct" | "refine"} */
let formMode = "direct";

/** 阶段一入选不足时自动重新提炼；达标后才展示阶段一 */
const STAGE1_MIN_SELECTED = 14;
const MAX_KEYWORD_AUTO_REFINE = 3;
let autoRefineCount = 0;
let pendingAutoRefine = false;
/** @type {"user" | "low-selected" | null} */
let abortReason = null;
/** 用于重试提炼的论文元信息（原始关键词，非提炼结果） */
let paperMetaForRefine = null;

function setFormBusy(busy) {
  directSearchBtn.disabled = busy;
  refineBtn.disabled = busy;
  if (newPaperBtn) newPaperBtn.disabled = busy;
  modeDirectBtn.disabled = busy;
  modeRefineBtn.disabled = busy;
}

function setFormMode(mode) {
  formMode = mode === "refine" ? "refine" : "direct";
  form.dataset.mode = formMode;

  modeDirectBtn.classList.toggle("active", formMode === "direct");
  modeRefineBtn.classList.toggle("active", formMode === "refine");

  document.querySelectorAll(".refine-only").forEach((el) => {
    el.classList.toggle("hidden", formMode !== "refine");
  });
  directSearchBtn.classList.toggle("hidden", formMode !== "direct");
  refineBtn.classList.toggle("hidden", formMode !== "refine");

  if (formMode === "direct") {
    modeHint.textContent = "填写关键词后直接开始检索";
    keywordsLabel.innerHTML = "检索关键词 <em>*</em>";
    keywordsTip.textContent = "支持逗号、顿号、分号等分隔，例如：混沌系统、同步控制";
    hideRefinedKeywords();
  } else {
    modeHint.textContent = "填写标题、摘要与关键词后，自动提炼并开始检索";
    keywordsLabel.innerHTML = "原始关键词";
    keywordsTip.textContent = "供智能提炼参考；同样支持逗号、顿号、分号等分隔";
  }
}

/** 与后端 parse_keywords / normalize_keywords 一致：分号、逗号、顿号、换行等均可。 */
function parseKeywordList(text) {
  return String(text || "")
    .split(/[;；,，、|\n\r]+/)
    .map((word) => word.trim())
    .filter(Boolean);
}

/** 规范化关键词输入为逗号分隔，便于后端与展示一致。 */
function normalizeKeywordsInput(text) {
  return parseKeywordList(text).join(",");
}

function setRefinedKeywordsCollapsed(collapsed) {
  if (!refinedKeywordsPanel) return;
  refinedKeywordsPanel.classList.toggle("collapsed", collapsed);
  if (refinedKeywordsToggle) {
    refinedKeywordsToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }
  if (refinedKeywordsToggleLabel) {
    refinedKeywordsToggleLabel.textContent = collapsed ? "展开" : "收起";
  }
}

function hideRefinedKeywords() {
  refinedKeywordsPanel?.classList.add("hidden");
  setRefinedKeywordsCollapsed(true);
  if (refinedKeywordsTags) refinedKeywordsTags.innerHTML = "";
  if (refinedKeywordsReasoning) {
    refinedKeywordsReasoning.textContent = "";
    refinedKeywordsReasoning.classList.add("hidden");
  }
}

function showRefinedKeywords(keywordsText, reasoning = "") {
  if (!refinedKeywordsPanel || !refinedKeywordsTags) return;
  const words = parseKeywordList(keywordsText);
  refinedKeywordsTags.innerHTML = words.length
    ? words.map((kw) => `<span class="kw-tag">${escapeHtml(kw)}</span>`).join("")
    : `<span class="muted">暂无</span>`;
  if (refinedKeywordsReasoning) {
    refinedKeywordsReasoning.textContent = reasoning ? `说明：${reasoning}` : "";
    refinedKeywordsReasoning.classList.toggle("hidden", !reasoning);
  }
  setRefinedKeywordsCollapsed(true);
  refinedKeywordsPanel.classList.remove("hidden");
}


function setConnectionStatus(kind, text) {
  connectionStatus.className = `status-pill ${kind}`;
  connectionStatus.querySelector("span:last-child").textContent = text;
}

function canAutoRefineKeywords() {
  // 仅智能检索模式允许自动重新提炼；直接检索召回不足时提示用户改关键词
  if (formMode !== "refine") return false;
  const meta = paperMetaForRefine || readFormFields();
  return Boolean(meta?.title?.trim()) && autoRefineCount < MAX_KEYWORD_AUTO_REFINE;
}

/** 阶段一空态：未确定入选人数时展示基本界面 */
function renderStage1Empty(statusText = "正在召回候选人…") {
  lastStage1Experts = [];
  setStageCard("stage1", "active");
  setStageLabel(stage1State, "进行中");
  stage1Body.innerHTML = `
    <div class="stage1-toolbar">
      <div class="stats-row stats-row-inline">
        <span class="stat-chip">召回 -</span>
        <span class="stat-chip">COI -</span>
        <span class="stat-chip">入选 -</span>
        <span class="stat-chip">≥ 0.50</span>
      </div>
      <input
        type="search"
        id="stage1Search"
        class="stage1-search"
        placeholder="搜索姓名、职称、机构、学科、简介、关键词…"
        disabled
      />
      <label class="stage1-filter">
        <input type="checkbox" id="stage1SelectedOnly" disabled />
        仅入选
      </label>
      <span class="stage1-count" id="stage1Count">0 / 0</span>
      ${stage1SortControlsHtml({ disabled: true })}
    </div>
    <div class="stage1-scroll">
      <ul class="stage1-list" id="stage1List">
        <li class="author-row">
          <p class="placeholder" style="margin:0;padding-left:0">${escapeHtml(statusText)}</p>
        </li>
      </ul>
    </div>
  `;
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
  const items = (keywords || []).filter(Boolean).slice(0, 5);
  if (!items.length) return "";
  return `
    <div class="kw-tags">
      ${items.map((kw) => `<span class="kw-tag" title="${escapeHtml(kw)}">${escapeHtml(kw)}</span>`).join("")}
    </div>
  `;
}

/** CSCD 学科常以 ;; / ; / 、 / ， 等分隔。 */
function parseSubjectList(subject) {
  return String(subject || "")
    .split(/[;；、,，/|]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

/** 学科展示：去掉多余标点，顿号分隔 */
function formatSubjectText(subject) {
  const items = parseSubjectList(subject);
  return items.length ? items.join("、") : "-";
}

function renderSubjectTags(subject) {
  const items = parseSubjectList(subject);
  if (!items.length) {
    return `<span class="author-subject-empty">-</span>`;
  }
  const full = items.join(" · ");
  return `
    <div class="subject-tags" title="${escapeHtml(full)}">
      ${items
        .map((name) => `<span class="subject-tag">${escapeHtml(name)}</span>`)
        .join("")}
    </div>
  `;
}

function overlapTone(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return { tone: "", label: "-", pct: 0 };
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  let tone = "low";
  if (value >= 0.8) tone = "high";
  else if (value >= 0.5) tone = "mid";
  return { tone, label: value.toFixed(2), pct };
}

function renderStage1Row(item) {
  const hasEmail = Boolean(item.email?.trim());
  const canViewPubs = Boolean(item.name?.trim() && activePaperKeywords);
  const org = item.org || "-";
  const position = String(item.position || "").trim();
  const resume = String(item.resume || "").trim();
  const overlap = overlapTone(item.overlap_score);
  const subjectsHtml = renderSubjectTags(item.subject);
  const keywordsHtml = renderKeywordTags(item.research_keywords);
  const hasSubjects = parseSubjectList(item.subject).length > 0;
  const hasKeywords = Boolean(keywordsHtml);
  return `
    <li class="author-row ${item.selected ? "is-selected" : ""}">
      <div class="author-main">
        <div class="author-identity">
          <span class="author-rank">#${String(item.rank).padStart(2, "0")}</span>
          <strong class="author-name" title="${escapeHtml(item.name || "")}">${escapeHtml(item.name || "-")}</strong>
          ${
            position
              ? `<span class="author-position" title="${escapeHtml(position)}">${escapeHtml(position)}</span>`
              : ""
          }
          <span class="author-org" title="${escapeHtml(org)}">${escapeHtml(org)}</span>
        </div>
        ${
          resume
            ? `<p class="author-resume" title="悬停查看全部">${escapeHtml(resume)}</p>`
            : ""
        }
        ${
          hasSubjects || hasKeywords
            ? `<div class="author-research">
                ${hasSubjects ? `<div class="author-meta">${subjectsHtml}</div>` : ""}
                ${hasKeywords ? `<div class="author-keywords">${keywordsHtml}</div>` : ""}
              </div>`
            : ""
        }
      </div>
      <div class="author-side">
        <div class="author-metrics">
          <div class="metric metric-overlap" title="关键词重合度 ${overlap.label}">
            <div class="metric-row">
              <span class="metric-label">关键词重合度</span>
              <span class="metric-value ${overlap.tone ? `tone-${overlap.tone}` : ""}">${overlap.label}</span>
            </div>
            ${
              overlap.tone
                ? `<span class="overlap-mini"><i style="width:${overlap.pct}%"></i></span>`
                : ""
            }
          </div>
          <div class="metric-pair">
            <div class="metric metric-cell" title="H 指数">
              <div class="metric-row metric-row-end">
                <span class="metric-label">H 指数</span>
                <span class="metric-value">${item.hindex ?? "-"}</span>
              </div>
            </div>
            <div class="metric metric-cell" title="近 5 年发文量（CSCD numAllpaper）">
              <div class="metric-row metric-row-end">
                <span class="metric-label">近5年发文</span>
                <span class="metric-value">${
                  item.pubs_last_5_years != null && item.pubs_last_5_years !== ""
                    ? item.pubs_last_5_years
                    : "-"
                }</span>
              </div>
            </div>
          </div>
        </div>
        <div class="author-side-foot">
          ${
            item.selected
              ? '<span class="badge-selected">入选</span>'
              : '<span class="badge-muted">未入选</span>'
          }
          <button
            type="button"
            class="table-action-btn stage1-pubs-btn"
            data-rank="${item.rank}"
            ${canViewPubs ? "" : "disabled"}
          >历史发文</button>
          <button
            type="button"
            class="table-action-btn stage1-copy-btn"
            data-rank="${item.rank}"
            title="${hasEmail ? escapeHtml(item.email) : "无邮箱"}"
            ${hasEmail ? "" : "disabled"}
          >复制邮箱</button>
          <button
            type="button"
            class="table-action-btn stage1-copy-all-btn"
            data-rank="${item.rank}"
            title="复制姓名、职称、邮箱、单位、研究方向"
          >复制全部信息</button>
        </div>
      </div>
    </li>
  `;
}

function stage1SortControlsHtml({ disabled = false } = {}) {
  const opts = [
    { value: "overlap", label: "关键词重合度" },
    { value: "pubs5", label: "近5年发文" },
    { value: "hindex", label: "H指数" },
  ];
  return `
    <div class="stage1-sort" role="group" aria-label="排序规则">
      <span class="stage1-sort-label">排序</span>
      ${opts
        .map(
          (opt) => `
        <label class="stage1-sort-option">
          <input
            type="radio"
            name="stage1Sort"
            value="${opt.value}"
            ${stage1SortBy === opt.value ? "checked" : ""}
            ${disabled ? "disabled" : ""}
          />
          ${opt.label}
        </label>
      `
        )
        .join("")}
    </div>
  `;
}

function stage1MetricValue(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : Number.NEGATIVE_INFINITY;
}

function getFilteredStage1Experts() {
  const query = (document.getElementById("stage1Search")?.value || "").trim().toLowerCase();
  const selectedOnly = document.getElementById("stage1SelectedOnly")?.checked;
  const sortInput = document.querySelector('input[name="stage1Sort"]:checked');
  if (sortInput?.value) {
    stage1SortBy = sortInput.value;
  }

  const filtered = lastStage1Experts.filter((item) => {
    if (selectedOnly && !item.selected) return false;
    if (!query) return true;
    const haystack = [
      item.name,
      item.position,
      item.org,
      item.subject,
      item.resume,
      ...(item.research_keywords || []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });

  const sorted = filtered.slice();
  sorted.sort((a, b) => {
    if (stage1SortBy === "pubs5") {
      return stage1MetricValue(b.pubs_last_5_years) - stage1MetricValue(a.pubs_last_5_years);
    }
    if (stage1SortBy === "hindex") {
      return stage1MetricValue(b.hindex) - stage1MetricValue(a.hindex);
    }
    return stage1MetricValue(b.overlap_score) - stage1MetricValue(a.overlap_score);
  });
  return sorted;
}

function updateStage1TableBody() {
  const list = document.getElementById("stage1List");
  const countEl = document.getElementById("stage1Count");
  if (!list) return;

  const filtered = getFilteredStage1Experts();
  list.innerHTML = filtered.length
    ? filtered.map(renderStage1Row).join("")
    : `<li class="author-row"><p class="placeholder" style="margin:0;padding-left:0">没有匹配的作者</p></li>`;
  if (countEl) {
    countEl.textContent = `${filtered.length} / ${lastStage1Experts.length}`;
  }
}

function renderStage1(thinking) {
  lastStage1Experts = thinking.experts || thinking.selected || [];
  pubsCache.clear();
  setStageCard("stage1", "done");
  setStageLabel(stage1State, `${lastStage1Experts.length} 位`);

  const selectedCount = thinking.selected_count ?? 0;

  stage1Body.innerHTML = `
    <div class="stage1-toolbar">
      <div class="stats-row stats-row-inline">
        <span class="stat-chip">召回 ${thinking.total_from_api ?? 0}</span>
        <span class="stat-chip">COI ${thinking.after_coi ?? 0}</span>
        <span class="stat-chip">入选 ${selectedCount}</span>
        <span class="stat-chip">≥ ${(thinking.min_overlap_threshold ?? 0.5).toFixed?.(2) ?? thinking.min_overlap_threshold ?? "0.5"}</span>
      </div>
      <input
        type="search"
        id="stage1Search"
        class="stage1-search"
        placeholder="搜索姓名、职称、机构、学科、简介、关键词…"
      />
      <label class="stage1-filter">
        <input type="checkbox" id="stage1SelectedOnly" />
        仅入选
      </label>
      <span class="stage1-count" id="stage1Count"></span>
      ${stage1SortControlsHtml()}
    </div>
    <div class="stage1-scroll">
      <ul class="stage1-list" id="stage1List"></ul>
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
  return "-";
}

function renderResult(reviewers) {
  lastReviewers = reviewers;
  setStageCard("stage3", "done");
  setStageLabel(stage3State, "已完成");
  setStageCard("result", "done");
  setStageLabel(resultState, `${reviewers.length} 位`);

  resultBody.innerHTML = `
    <div class="reviewer-grid">
      ${reviewers
        .map((item, index) => {
          const canViewPubs = Boolean(item.name?.trim() && activePaperKeywords);
          return `
            <article class="reviewer-card">
              <div class="reviewer-head">
                <div>
                  <h4 class="reviewer-name-row">
                    <span>${escapeHtml(item.name)}</span>
                    ${
                      String(item.position || "").trim()
                        ? `<span class="author-position" title="${escapeHtml(item.position)}">${escapeHtml(item.position)}</span>`
                        : ""
                    }
                  </h4>
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
                    class="copy-btn result-copy-email-btn"
                    data-index="${index}"
                    ${item.email?.trim() ? "" : "disabled"}
                  >复制邮箱</button>
                  <button
                    type="button"
                    class="copy-all-btn result-copy-all-btn"
                    data-index="${index}"
                    title="复制姓名、职称、邮箱、单位、研究方向"
                  >复制全部信息</button>
                </div>
              </div>
              <dl class="reviewer-meta-grid">
                <div>
                  <dt>学科</dt>
                  <dd>${escapeHtml(formatSubjectText(item.subject))}</dd>
                </div>
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

async function copyText(text, button, { successLabel = "已复制", toastMessage = "" } = {}) {
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
    button.textContent = successLabel;
    button.classList.add("copied");
    window.setTimeout(() => {
      button.textContent = original;
      button.classList.remove("copied");
    }, 2000);
  }
  if (toastMessage) showCopyToast(toastMessage);
  return true;
}

function showCopyToast(message) {
  let toast = document.getElementById("copyToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "copyToast";
    toast.className = "copy-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(showCopyToast._timer);
  showCopyToast._timer = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 2200);
}

function formatExpertCopyText(expert) {
  const name = String(expert?.name || "").trim() || "-";
  const title = String(expert?.position || "").trim() || "-";
  const email = String(expert?.email || "").trim() || "-";
  const org = String(expert?.org || "").trim() || "-";
  const keywords = (expert?.research_keywords || []).filter(Boolean);
  const field =
    keywords.length > 0
      ? keywords.join("、")
      : formatSubjectText(expert?.subject) !== "-"
        ? formatSubjectText(expert?.subject)
        : renderResearchField(expert);
  return [
    `姓名：${name}`,
    `职称：${title}`,
    `邮箱：${email}`,
    `单位：${org}`,
    `研究方向：${field}`,
  ].join("\n");
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

  renderStage1Empty("正在召回候选人…");
  stage2Body.innerHTML = `<p class="placeholder">等待候选专家完成…</p>`;
  stage3Body.innerHTML = `<p class="placeholder">等待背景补全完成…</p>`;
  resultBody.innerHTML = `<p class="placeholder">精荐完成后展示…</p>`;
  applyStageFilter("all");
}

/** 换下一篇稿：清空论文字段与结果区，默认保留机构。 */
function startNewPaper({ keepAuthorOrg = false } = {}) {
  if (abortController) {
    abortReason = "user";
    pendingAutoRefine = false;
    abortController.abort();
  }

  const authorOrgInput = form.elements.namedItem("author_org");
  const keptOrg = keepAuthorOrg ? String(authorOrgInput?.value || "").trim() : "";

  form.elements.namedItem("title").value = "";
  form.elements.namedItem("abstract").value = "";
  form.elements.namedItem("keywords").value = "";
  if (authorOrgInput) authorOrgInput.value = keptOrg;

  hideRefinedKeywords();
  paperMetaForRefine = null;
  pendingPayload = null;
  activePaperKeywords = "";
  autoRefineCount = 0;
  pendingAutoRefine = false;
  abortReason = null;
  pubsCache.clear();

  lastReviewers = [];
  lastStage1Experts = [];
  stage2Progress.length = 0;
  ["stage1", "stage2", "stage3", "result"].forEach((stage) => {
    setStageCard(stage, "idle");
  });
  setStageLabel(stage1State, "等待中");
  setStageLabel(stage2State, "等待中");
  setStageLabel(stage3State, "等待中");
  setStageLabel(resultState, "等待中");
  stage1Body.innerHTML = `<p class="placeholder">提交后开始召回…</p>`;
  stage2Body.innerHTML = `<p class="placeholder">等待候选匹配…</p>`;
  stage3Body.innerHTML = `<p class="placeholder">等待背景补全…</p>`;
  resultBody.innerHTML = `<p class="placeholder">精荐完成后展示…</p>`;
  applyStageFilter("all");

  setFormBusy(false);
  stopBtn.disabled = true;
  setConnectionStatus("ok", keptOrg ? "已清空论文信息（机构已保留）" : "已清空，可填写下一篇");

  const focusName = formMode === "refine" ? "title" : "keywords";
  form.elements.namedItem(focusName)?.focus();
}

function applyStageFilter(filter) {
  const allowed = new Set(["all", "stage1", "stage2", "stage3", "result"]);
  const next = allowed.has(filter) ? filter : "all";
  activeFilter = next;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.stage === next);
  });
  document.querySelectorAll(".stage-card").forEach((card) => {
    const stage = card.dataset.stage;
    const visible = next === "all" || stage === next;
    card.classList.toggle("hidden", !visible);
  });
}

function handleEvent(event) {
  switch (event.event) {
    case "stage1_thinking": {
      const thinking = event.thinking || {};
      const selectedCount = Number(thinking.selected_count ?? 0);

      if (selectedCount < STAGE1_MIN_SELECTED) {
        if (canAutoRefineKeywords()) {
          pendingAutoRefine = true;
          abortReason = "low-selected";
          setConnectionStatus("running", "正在重新提炼关键词…");
          renderStage1Empty("正在重新提炼关键词…");
          abortController?.abort();
          break;
        }

        abortReason = "low-selected";
        pendingAutoRefine = false;
        const recalled = Number(thinking.total_from_api ?? 0);
        const passed = Number(
          thinking.passed_min_overlap_count ?? thinking.selected_count ?? 0
        );
        const threshold = Number(thinking.min_overlap_threshold ?? 0.5);
        // 仍展示阶段一列表，便于对照重合度；不是「API 没召回」
        renderStage1(thinking);
        setConnectionStatus("error", "入选不足，请调整关键词后重试");
        if (formMode === "direct") {
          resultBody.innerHTML = `<div class="error-box">CSCD 已召回 ${recalled} 人，但关键词重合度 ≥ ${threshold.toFixed(2)} 仅入选 ${passed} 人（需至少 ${STAGE1_MIN_SELECTED} 人）。请修改检索关键词后重试。</div>`;
        } else if (autoRefineCount > 0) {
          resultBody.innerHTML = `<div class="error-box">已召回 ${recalled} 人，重合度筛选后仅入选 ${passed} 人；已自动重新提炼 ${autoRefineCount} 次仍未达标，请调整标题、摘要或原始关键词后重试。</div>`;
        } else {
          resultBody.innerHTML = `<div class="error-box">已召回 ${recalled} 人，重合度筛选后仅入选 ${passed} 人（需至少 ${STAGE1_MIN_SELECTED} 人）。请调整标题、摘要与关键词后重试。</div>`;
        }
        setStageCard("stage1", "done");
        setStageLabel(stage1State, "未达标");
        abortController?.abort();
        break;
      }

      renderStage1(thinking);
      setConnectionStatus("running", "候选匹配完成，正在补全学者背景…");
      setStageCard("stage2", "active");
      setStageLabel(stage2State, "进行中");
      stage2Body.innerHTML = `<p class="placeholder">正在补全学者背景…</p>`;
      break;
    }

    case "stage2_thinking": {
      const thinking = event.thinking || {};
      if (thinking.progress) {
        renderStage2Progress(thinking);
        setStageCard("stage2", "active");
        setStageLabel(stage2State, "进行中");
        setConnectionStatus("running", "正在补全学者背景…");
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
        setConnectionStatus("running", "正在语义精筛…");
        setStageCard("stage3", "active");
        setStageLabel(stage3State, "进行中");
        stage3Body.innerHTML = `<div id="stage3Stream" class="thinking-stream"></div>`;
      }
      break;
    }

    case "stage3_thinking":
      if (event.thinking?.summary) {
        renderStage3Summary(event.thinking);
        setConnectionStatus("running", "正在语义精筛…");
      } else if (event.chunk) {
        appendStage3Text(event.chunk);
        setConnectionStatus("running", "正在语义精筛…");
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
  setConnectionStatus("running", "检索进行中…");
  setFormBusy(true);
  stopBtn.disabled = false;
  pendingAutoRefine = false;
  abortReason = null;

  abortController = new AbortController();
  let shouldAutoRefine = false;

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
        if (pendingAutoRefine || abortReason === "low-selected") {
          try {
            await reader.cancel();
          } catch {
            /* ignore */
          }
          throw Object.assign(new Error("pipeline-stop"), { name: "AbortError" });
        }
      }
    }

    if (buffer.trim() && !pendingAutoRefine && abortReason !== "low-selected") {
      handleEvent(JSON.parse(buffer));
    }
  } catch (err) {
    if (err.name === "AbortError" && pendingAutoRefine && abortReason === "low-selected") {
      pendingAutoRefine = false;
      shouldAutoRefine = true;
    } else if (err.name === "AbortError" && abortReason === "low-selected") {
      // 入选不足且无法再重试，错误信息已在 handleEvent 中展示
    } else if (err.name !== "AbortError") {
      renderError(err.message || String(err));
      setConnectionStatus("error", "运行失败");
    } else {
      setConnectionStatus("ok", "已停止");
    }
  } finally {
    abortController = null;
    if (!shouldAutoRefine) {
      setFormBusy(false);
      stopBtn.disabled = true;
    }
  }

  if (shouldAutoRefine) {
    await retryByReRefineKeywords(payload);
  }
}

function readFormFields() {
  const data = new FormData(form);
  return {
    title: (data.get("title") || "").trim(),
    abstract: (data.get("abstract") || "").trim(),
    keywords: (data.get("keywords") || "").trim(),
    author_org: (data.get("author_org") || "").trim(),
    extra: (data.get("extra") || "").trim(),
  };
}

function buildRecommendPayload(keywords, { includePaperMeta = true } = {}) {
  const fields = readFormFields();
  return {
    title: includePaperMeta ? fields.title : "",
    abstract: includePaperMeta ? fields.abstract : "",
    keywords: keywords || fields.keywords,
    author_org: fields.author_org,
    extra: includePaperMeta ? fields.extra : "",
  };
}

function validateDirectForm() {
  const fields = readFormFields();
  const keywords = normalizeKeywordsInput(fields.keywords);
  if (!keywords) {
    form.elements.namedItem("keywords")?.focus();
    setConnectionStatus("error", "请填写检索关键词");
    return null;
  }
  // 写回规范化结果，避免后续展示/发文查询仍带混杂分隔符
  const keywordsInput = form.elements.namedItem("keywords");
  if (keywordsInput) keywordsInput.value = keywords;
  return { ...fields, keywords };
}

function validateRefineForm() {
  const fields = readFormFields();
  if (!fields.title) {
    form.elements.namedItem("title")?.focus();
    setConnectionStatus("error", "请填写论文标题");
    return null;
  }
  const keywords = normalizeKeywordsInput(fields.keywords);
  const keywordsInput = form.elements.namedItem("keywords");
  if (keywordsInput && keywords) keywordsInput.value = keywords;
  return { ...fields, keywords };
}

async function refineAndSearch(payload) {
  setFormBusy(true);
  refineBtn.textContent = "智能检索中…";
  const isRetry = Boolean(payload.previous_keywords);
  setConnectionStatus(
    "running",
    isRetry ? `正在重新提炼关键词（第 ${autoRefineCount} 次）…` : "正在提炼关键词…"
  );

  try {
    const res = await fetch(ENDPOINTS.refineKeywords, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: payload.title,
        abstract: payload.abstract || "",
        keywords: payload.keywords || "",
        previous_keywords: payload.previous_keywords || "",
        retry_note: payload.retry_note || "",
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
    const keywordList = (data.keywords || [])
      .map((word) => String(word).trim())
      .filter(Boolean);
    const keywords = keywordList.join(",");
    if (!keywords) throw new Error("提炼结果为空");

    const recommendPayload = {
      title: payload.title || "",
      abstract: payload.abstract || "",
      keywords,
      author_org: payload.author_org || "",
      extra: payload.extra || "",
    };
    pendingPayload = recommendPayload;
    activePaperKeywords = keywords;
    showRefinedKeywords(
      keywords,
      isRetry
        ? `重新提炼（第 ${autoRefineCount} 次）：${data.reasoning || ""}`
        : data.reasoning || ""
    );
    setConnectionStatus("running", "已提炼，开始检索…");
    setFormBusy(false);
    refineBtn.textContent = "开始智能检索";
    await startRecommend(recommendPayload);
  } catch (err) {
    renderError(`智能检索失败：${err.message || err}`);
    setConnectionStatus("error", "智能检索失败");
    setFormBusy(false);
    stopBtn.disabled = true;
    refineBtn.textContent = "开始智能检索";
  }
}

async function retryByReRefineKeywords(payload) {
  const meta = paperMetaForRefine || readFormFields();
  if (!meta?.title?.trim()) {
    setConnectionStatus("error", "入选不足且无法自动提炼（缺少论文标题）");
    resultBody.innerHTML = `<div class="error-box">阶段一入选不足 ${STAGE1_MIN_SELECTED} 人，但缺少论文标题，无法自动重新提炼。请切换到智能检索或补充标题后重试。</div>`;
    setFormBusy(false);
    stopBtn.disabled = true;
    return;
  }

  autoRefineCount += 1;
  await refineAndSearch({
    title: meta.title,
    abstract: meta.abstract || "",
    keywords: meta.keywords || "",
    author_org: meta.author_org || payload.author_org || "",
    extra: meta.extra || payload.extra || "",
    previous_keywords: payload.keywords || "",
    retry_note: `上次检索关键词入选不足 ${STAGE1_MIN_SELECTED} 人，请略放宽粒度或更换过细词后重新提炼恰好 3 个关键词`,
  });
}

function startDirectRecommend() {
  hideRefinedKeywords();
  const fields = validateDirectForm();
  if (!fields) return;
  autoRefineCount = 0;
  // 直接检索不保留标题/摘要，避免误触发自动提炼
  paperMetaForRefine = null;
  const payload = buildRecommendPayload(fields.keywords, { includePaperMeta: false });
  pendingPayload = payload;
  activePaperKeywords = fields.keywords;
  startRecommend(payload);
}

function startSmartRecommend() {
  hideRefinedKeywords();
  const fields = validateRefineForm();
  if (!fields) return;
  autoRefineCount = 0;
  paperMetaForRefine = {
    title: fields.title,
    abstract: fields.abstract,
    keywords: fields.keywords,
    author_org: fields.author_org,
    extra: fields.extra,
  };
  refineAndSearch(fields);
}

function openPubsModal(expert) {
  pubsFilterYear = null;
  lastPubsData = null;
  pubsModalTitle.textContent = "历史发文统计";
  pubsModalSubtitle.textContent = `${expert.name}${expert.org ? ` · ${expert.org}` : ""} · 关键词 ${activePaperKeywords}`;
  pubsModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closePubsModal() {
  pubsModal.classList.add("hidden");
  document.body.style.overflow = "";
  pubsFilterYear = null;
  lastPubsData = null;
}

function setPubsYearFilter(year) {
  const next = year == null || Number.isNaN(Number(year)) ? null : Number(year);
  pubsFilterYear = pubsFilterYear === next ? null : next;
  if (lastPubsData) renderPubsStats(lastPubsData);
}

function renderPubsChartSvg(series, selectedYear = null) {
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
  const hitW = Math.max(barW + 10, gap * 0.85);

  const ticks = 4;
  const grid = [];
  for (let t = 0; t <= ticks; t += 1) {
    const value = Math.round((maxY * t) / ticks);
    const y = pad.top + chartH - (value / maxY) * chartH;
    grid.push(`
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" stroke="#dce3eb" />
      <text x="${pad.left - 8}" y="${y + 4}" text-anchor="end" fill="#6b7c90" font-size="11">${value}</text>
    `);
  }

  const bars = years
    .map((year, i) => {
      const x = pad.left + gap * i + (gap - barW) / 2;
      const hitX = pad.left + gap * i + (gap - hitW) / 2;
      let y = pad.top + chartH;
      const selected = selectedYear != null && Number(year) === Number(selectedYear);
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
          return `<rect class="pubs-bar-seg" x="${x}" y="${y}" width="${barW}" height="${h}" fill="${seg.color}" rx="2">
            <title>${year} · ${label}：${seg.value}（点击筛选）</title>
          </rect>`;
        })
        .join("");
      return `
        <g class="pubs-bar-group${selected ? " is-selected" : ""}" data-year="${year}" role="button" tabindex="0">
          <rect class="pubs-bar-hit" x="${hitX}" y="${pad.top}" width="${hitW}" height="${chartH}" rx="4" />
          ${rects}
          <text x="${x + barW / 2}" y="${height - 14}" text-anchor="middle" fill="${selected ? "#174ea6" : "#6b7c90"}" font-size="11" font-weight="${selected ? "700" : "400"}">${year}</text>
        </g>
      `;
    })
    .join("");

  return `
    <div class="pubs-chart-wrap">
      <p class="pubs-chart-hint">点击柱子可按年份筛选论文列表${selectedYear != null ? ` · 当前：${selectedYear}` : ""}</p>
      <svg class="pubs-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="历史发文柱状图">
        ${grid.join("")}
        ${bars}
      </svg>
    </div>
  `;
}

function renderAuthorNames(authors, targetName, sequence, role = "other") {
  const names = authors || [];
  if (!names.length) return `<span class="muted">作者信息缺失</span>`;
  const shouldHighlight = role === "first" || role === "corresponding";
  return names
    .map((name, index) => {
      const isTarget =
        String(name).replace(/\s+/g, "") === String(targetName || "").replace(/\s+/g, "") ||
        (sequence != null && index + 1 === Number(sequence));
      if (!isTarget) {
        return `<span>${escapeHtml(name)}</span>`;
      }
      if (!shouldHighlight) {
        return `<span class="author-plain">${escapeHtml(name)}</span>`;
      }
      const roleTag =
        role === "first"
          ? "第一作者"
          : "通讯作者";
      return `<strong class="author-highlight role-${role}">${escapeHtml(name)}</strong><span class="author-seq-tag role-${role}">${roleTag}</span>`;
    })
    .join('<span class="author-sep">，</span>');
}

function renderPubsPaperList(papers, authorName, filterYear = null) {
  const all = papers || [];
  const items =
    filterYear == null
      ? all
      : all.filter((paper) => Number(paper.year) === Number(filterYear));
  const filterLabel =
    filterYear == null
      ? `<span class="muted">（最近优先 · 点击柱状图按年筛选）</span>`
      : `<span class="pubs-year-filter">
          ${filterYear} 年
          <button type="button" class="pubs-year-clear" data-clear-year>全部年份</button>
        </span>`;

  if (!items.length) {
    return `
      <div class="pubs-paper-list">
        <h4 class="pubs-paper-title">论文列表 ${filterLabel}</h4>
        <p class="placeholder">${filterYear == null ? "暂无论文列表" : `${filterYear} 年暂无匹配论文`}</p>
      </div>
    `;
  }
  return `
    <div class="pubs-paper-list">
      <h4 class="pubs-paper-title">论文列表 ${filterLabel} · ${items.length} 篇</h4>
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
          const linkHtml = paper.article_url
            ? `<a class="pubs-paper-link" href="${escapeHtml(paper.article_url)}" target="_blank" rel="noopener noreferrer" title="打开原文" aria-label="打开原文">${PUBS_LINK_ICON}</a>`
            : "";
          return `
            <article class="pubs-paper-item ${roleClass}">
              <div class="pubs-paper-head">
                <span class="pubs-role-badge ${roleClass}">${escapeHtml(paper.role_label || "作者")}</span>
                <span class="pubs-paper-meta">${escapeHtml(meta || "-")}</span>
              </div>
              <div class="pubs-paper-name-row">
                <h5 class="pubs-paper-name">${escapeHtml(paper.title || "无标题")}</h5>
                ${linkHtml}
              </div>
              <p class="pubs-paper-authors">${renderAuthorNames(paper.authors, authorName, paper.author_sequence, paper.role)}</p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPubsStats(data) {
  lastPubsData = data;
  const totalMatched =
    (data.totals?.first || 0) +
    (data.totals?.corresponding || 0) +
    (data.totals?.other || 0);
  pubsModalTitle.textContent = `历史发文 · 共 ${totalMatched} 篇`;
  pubsModalSubtitle.textContent = `${data.author}${data.institute ? ` · ${data.institute}` : ""} · ${(data.keywords || []).join("、")}`;
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
    ${renderPubsChartSvg(data.series || {}, pubsFilterYear)}
    <p class="pubs-note">${escapeHtml(data.role_note || "")}</p>
    ${renderPubsPaperList(data.papers || [], data.author, pubsFilterYear)}
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
        institute: expert.org || "",
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
    const raw = String(err.message || err);
    let tip = raw;
    if (/AppCode|ApiCode|申请失败/i.test(raw)) {
      tip = `${raw}（CSCD 鉴权失败：请确认 .env 中 CSCD_USER/CSCD_PASSWORD 可用；静态 CSCD_API_CODE 约 10 分钟过期，有账号密码时建议留空。若刚频繁请求，请稍后再试。）`;
    }
    pubsModalBody.innerHTML = `<div class="error-box">${escapeHtml(tip)}</div>`;
    setConnectionStatus("error", "发文查询失败");
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  if (formMode === "direct") startDirectRecommend();
  else startSmartRecommend();
});

modeDirectBtn.addEventListener("click", () => setFormMode("direct"));
modeRefineBtn.addEventListener("click", () => setFormMode("refine"));
directSearchBtn.addEventListener("click", () => startDirectRecommend());
refineBtn.addEventListener("click", () => startSmartRecommend());
newPaperBtn?.addEventListener("click", () => startNewPaper({ keepAuthorOrg: false }));

stopBtn.addEventListener("click", () => {
  pendingAutoRefine = false;
  abortReason = "user";
  abortController?.abort();
});

pubsModalClose.addEventListener("click", closePubsModal);
pubsModal.addEventListener("click", (e) => {
  if (e.target === pubsModal) closePubsModal();
});
pubsModalBody.addEventListener("click", (e) => {
  if (e.target.closest("[data-clear-year]")) {
    pubsFilterYear = null;
    if (lastPubsData) renderPubsStats(lastPubsData);
    return;
  }
  const bar = e.target.closest(".pubs-bar-group");
  if (bar?.dataset.year) {
    setPubsYearFilter(bar.dataset.year);
  }
});
pubsModalBody.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const bar = e.target.closest(".pubs-bar-group");
  if (!bar?.dataset.year) return;
  e.preventDefault();
  setPubsYearFilter(bar.dataset.year);
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

  const copyAllBtn = e.target.closest(".result-copy-all-btn");
  if (copyAllBtn) {
    const index = Number(copyAllBtn.dataset.index);
    const reviewer = lastReviewers[index];
    if (!reviewer) return;
    await copyText(formatExpertCopyText(reviewer), copyAllBtn, {
      successLabel: "已复制全部",
      toastMessage: "全部信息已经复制到粘贴板",
    });
    return;
  }

  const copyBtn = e.target.closest(".result-copy-email-btn");
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
  if (e.target.id === "stage1SelectedOnly" || e.target.name === "stage1Sort") {
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

  const copyAllBtn = e.target.closest(".stage1-copy-all-btn");
  if (copyAllBtn) {
    const rank = Number(copyAllBtn.dataset.rank);
    const expert = lastStage1Experts.find((item) => item.rank === rank);
    if (!expert) return;
    await copyText(formatExpertCopyText(expert), copyAllBtn, {
      successLabel: "已复制全部",
      toastMessage: "全部信息已经复制到粘贴板",
    });
  }
});

refinedKeywordsToggle?.addEventListener("click", () => {
  const collapsed = !refinedKeywordsPanel?.classList.contains("collapsed");
  setRefinedKeywordsCollapsed(collapsed);
});

checkHealth();
setFormMode("direct");
applyStageFilter("all");
renderStage1Empty("提交论文信息后开始召回…");
setStageCard("stage1", "idle");
setStageLabel(stage1State, "等待中");
stage2Body.innerHTML = `<p class="placeholder">等待候选专家完成…</p>`;
stage3Body.innerHTML = `<p class="placeholder">等待背景补全完成…</p>`;
resultBody.innerHTML = `<p class="placeholder">精荐完成后展示…</p>`;
