// 前端独立运行时（5173）请求后端 API（8000）；与后端同域时留空
const API_BASE =
  window.location.port && window.location.port !== "8000"
    ? "http://127.0.0.1:8000"
    : "";
const ENDPOINTS = {
  health: `${API_BASE}/health`,
  recommend: `${API_BASE}/api/v1/recommend/reviewers`,
};

const form = document.getElementById("recommendForm");
const submitBtn = document.getElementById("submitBtn");
const stopBtn = document.getElementById("stopBtn");
const connectionStatus = document.getElementById("connectionStatus");
const stageTabs = document.getElementById("stageTabs");

const stage1Body = document.getElementById("stage1Body");
const stage2Body = document.getElementById("stage2Body");
const stage3Body = document.getElementById("stage3Body");
const resultBody = document.getElementById("resultBody");

const stage1State = document.getElementById("stage1State");
const stage2State = document.getElementById("stage2State");
const stage3State = document.getElementById("stage3State");
const resultState = document.getElementById("resultState");

let abortController = null;
let activeFilter = "all";
let lastReviewers = [];
let lastStage1Experts = [];
const stage2Progress = [];

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

function renderStage1Row(item) {
  const keywords = (item.research_keywords || []).join("、");
  const hasEmail = Boolean(item.email?.trim());
  return `
    <tr class="${item.selected ? "row-selected" : ""}">
      <td>${item.rank}</td>
      <td><strong>${escapeHtml(item.name)}</strong></td>
      <td>${escapeHtml(item.org || "-")}</td>
      <td>${escapeHtml(item.subject || "-")}</td>
      <td>${item.overlap_score?.toFixed?.(2) ?? item.overlap_score ?? "-"}</td>
      <td>${item.hindex ?? "-"}</td>
      <td class="keywords-cell">${escapeHtml(keywords || "-")}</td>
      <td>${item.selected ? '<span class="badge-selected">入选</span>' : ""}</td>
      <td>
        <button
          type="button"
          class="copy-btn copy-btn-sm stage1-copy-btn"
          data-rank="${item.rank}"
          ${hasEmail ? "" : "disabled"}
        >复制邮箱</button>
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
    <div class="table-scroll">
      <table class="candidate-table stage1-table">
        <thead>
          <tr>
            <th>#</th>
            <th>姓名</th>
            <th>机构</th>
            <th>学科</th>
            <th>重合度</th>
            <th>H 指数</th>
            <th>研究方向</th>
            <th>阶段二</th>
            <th>邮箱</th>
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

  const hasAnyEmail = reviewers.some((item) => item.email?.trim());

  resultBody.innerHTML = `
    ${
      hasAnyEmail
        ? `<div class="result-toolbar">
             <button type="button" class="copy-all-btn" id="copyAllEmails">复制全部邮箱</button>
           </div>`
        : ""
    }
    <div class="reviewer-grid">
      ${reviewers
        .map(
          (item, index) => `
            <article class="reviewer-card">
              <div class="reviewer-head">
                <div>
                  <h4>${escapeHtml(item.name)}</h4>
                  <p class="reviewer-org">${escapeHtml(item.org || "-")}</p>
                </div>
                <button
                  type="button"
                  class="copy-btn"
                  data-index="${index}"
                  ${item.email?.trim() ? "" : "disabled"}
                >复制邮箱</button>
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
          `
        )
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

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const data = new FormData(form);
  startRecommend({
    title: data.get("title").trim(),
    keywords: data.get("keywords").trim(),
    author_org: data.get("author_org").trim(),
    extra: data.get("extra").trim(),
  });
});

stopBtn.addEventListener("click", () => {
  abortController?.abort();
});

stageTabs.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (!tab) return;
  applyStageFilter(tab.dataset.stage);
});

resultBody.addEventListener("click", async (e) => {
  const copyBtn = e.target.closest(".copy-btn");
  if (copyBtn) {
    const index = Number(copyBtn.dataset.index);
    const email = lastReviewers[index]?.email;
    await copyText(email, copyBtn);
    return;
  }

  const copyAllBtn = e.target.closest("#copyAllEmails");
  if (copyAllBtn) {
    const emails = lastReviewers
      .map((item) => item.email?.trim())
      .filter(Boolean)
      .join("\n");
    await copyText(emails, copyAllBtn);
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
