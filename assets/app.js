const state = { data: [], filtered: [], visible: 30, now: new Date() };
const $ = (selector) => document.querySelector(selector);
const typeLabels = { competition: "竞赛", conference: "论文会议", journal_special_issue: "期刊专题", hackathon: "黑客松", summer_camp: "夏令营", pre_admission: "预推免" };
const statusLabels = {
  registration_open: "报名中", registration_upcoming: "即将报名", registration_closed: "报名已截止",
  submission_upcoming: "即将投稿/提交", submission_open: "投稿/提交中", submission_closed: "投稿/提交已截止",
  upcoming: "即将开始", ongoing: "进行中", ended: "已结束", unknown: "待核验"
};
const timelineLabels = {
  registration_start: "报名开始", registration_deadline: "报名截止", abstract_deadline: "摘要截止", submission_deadline: "提交截止",
  competition_start: "比赛开始", competition_end: "比赛结束"
};

function safeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function daysUntil(value) {
  const date = safeDate(value);
  if (!date) return null;
  const diff = date - state.now;
  if (diff < 0) return -Math.max(1, Math.ceil(Math.abs(diff) / 86400000));
  const targetDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const currentDay = new Date(state.now.getFullYear(), state.now.getMonth(), state.now.getDate());
  return Math.round((targetDay - currentDay) / 86400000);
}

function formatDate(value, includeYear = false) {
  const date = safeDate(value);
  if (!date) return "日期待核验";
  const options = { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false };
  if (includeYear) options.year = "numeric";
  return new Intl.DateTimeFormat("zh-CN", options).format(date);
}

function relative(value) {
  const days = daysUntil(value);
  if (days === null) return "请查看来源页";
  if (days < -1) return `已过 ${Math.abs(days)} 天`;
  if (days === -1) return "已截止";
  if (days === 0) return "今天";
  if (days === 1) return "明天";
  return `${days} 天后`;
}

function sourceNames(item) {
  const names = [...(item.sources || []).map((source) => source?.name), item.source?.name].filter(Boolean);
  return [...new Set(names)];
}

function sourceStatus(item) {
  if (item.stale) return "历史缓存 · 需复核";
  if (item.verification_status === "cross_source") return `${item.sources.length} 个来源交叉核验`;
  if (item.verification_status === "maintainer_reviewed") return "维护者已核验";
  return item.source?.name || "来源未知";
}

function ccfRank(item) {
  if (item.event_type !== "conference") return "";
  const tags = item.tags || [];
  const ranked = tags.find((tag) => /^CCF [ABC]$/.test(tag));
  if (ranked) return ranked;
  if (tags.includes("非 CCF")) return "非 CCF";
  const match = String(item.level || "").match(/(?:^|\s|\/)CCF\s+([ABC])(?:\s|\/|$)/);
  if (match) return `CCF ${match[1]}`;
  return String(item.level || "").includes("非 CCF") ? "非 CCF" : "";
}

function httpUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
}

function appendLink(container, label, url) {
  const safe = httpUrl(url);
  if (!safe) return;
  const link = document.createElement("a");
  link.href = safe; link.target = "_blank"; link.rel = "noreferrer"; link.textContent = `${label} ↗`;
  container.append(link);
}

function appendOption(select, value, label) {
  const option = document.createElement("option"); option.value = value; option.textContent = label; select.append(option);
}

function renderOptions(items) {
  const types = [...new Set(items.map((item) => item.event_type))].sort();
  const categories = [...new Set(items.flatMap((item) => item.categories || []))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  const sources = [...new Set(items.flatMap(sourceNames))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  types.forEach((type) => appendOption($("#typeFilter"), type, typeLabels[type] || type));
  categories.forEach((category) => appendOption($("#categoryFilter"), category, category));
  sources.forEach((source) => appendOption($("#sourceFilter"), source, source));
}

function primaryLabel(item) {
  for (const [field, label] of Object.entries(timelineLabels)) {
    if (item[field] && item[field] === item.primary_deadline) return label;
  }
  for (const stage of (item.schedule || [])) {
    if (stage.start === item.primary_deadline) return `${stage.name || "赛程"}开始`;
    if (stage.end === item.primary_deadline) return /截止/.test(stage.name || "") ? stage.name : `${stage.name || "赛程"}结束`;
  }
  return "最近节点";
}

function renderDetails(node, item) {
  const details = node.querySelector(".event-details");
  let hasDetails = false;

  const description = node.querySelector(".description-block");
  if (item.description) {
    description.hidden = false; description.querySelector("p").textContent = item.description; hasDetails = true;
  }
  const eligibility = node.querySelector(".eligibility-block");
  if (item.eligibility) {
    eligibility.hidden = false; eligibility.querySelector("p").textContent = item.eligibility; hasDetails = true;
  }

  const timeline = node.querySelector(".timeline-block");
  const timelineList = timeline.querySelector("dl");
  Object.entries(timelineLabels).forEach(([field, label]) => {
    if (!item[field]) return;
    const term = document.createElement("dt"); term.textContent = label;
    const value = document.createElement("dd"); value.textContent = formatDate(item[field], true);
    timelineList.append(term, value); hasDetails = true;
  });
  timeline.hidden = timelineList.children.length === 0;

  const schedule = node.querySelector(".schedule-block");
  const scheduleList = schedule.querySelector("div");
  (item.schedule || []).forEach((stage) => {
    const entry = document.createElement("article");
    const title = document.createElement("strong"); title.textContent = stage.name || "赛程阶段";
    const time = document.createElement("span");
    time.textContent = [stage.start && formatDate(stage.start, true), stage.end && formatDate(stage.end, true)].filter(Boolean).join(" → ");
    const text = document.createElement("p"); text.textContent = stage.content || "";
    entry.append(title, time); if (stage.content) entry.append(text); scheduleList.append(entry); hasDetails = true;
  });
  schedule.hidden = scheduleList.children.length === 0;

  const attachments = node.querySelector(".attachments-block");
  const attachmentList = attachments.querySelector("div");
  (item.attachments || []).forEach((attachment) => appendLink(attachmentList, attachment.name || "活动附件", attachment.url));
  attachments.hidden = attachmentList.children.length === 0;
  if (!attachments.hidden) hasDetails = true;

  const evidence = node.querySelector(".evidence-block");
  const evidenceLinks = evidence.querySelector("div");
  const sources = item.sources?.length ? item.sources : (item.source ? [item.source] : []);
  sources.forEach((source) => appendLink(evidenceLinks, source.name || "来源", source.url));
  if (item.catalog_listed) appendLink(evidenceLinks, `赛事目录：${item.catalog_name || "已收录"}`, item.catalog_reference_url);
  appendLink(evidenceLinks, "活动页面", item.official_url);
  evidence.querySelector("p").textContent = item.notes || "日期可能变化，提交前请复核来源原文。";
  evidence.hidden = evidenceLinks.children.length === 0 && !item.notes;
  if (!evidence.hidden) hasDetails = true;

  details.hidden = !hasDetails;
}

function filterData(reset = true) {
  if (reset) state.visible = 30;
  const query = $("#searchInput").value.trim().toLowerCase();
  const type = $("#typeFilter").value;
  const category = $("#categoryFilter").value;
  const source = $("#sourceFilter").value;
  const windowDays = $("#windowFilter").value;
  const showExpired = $("#expiredToggle").checked;
  state.filtered = state.data.filter((item) => {
    const haystack = [item.name, item.organizer, item.level, item.location, item.description, item.eligibility, item.notes, ...(item.categories || []), ...(item.tags || []), ...(item.university_tiers || []), ...sourceNames(item)].join(" ").toLowerCase();
    const days = daysUntil(item.primary_deadline);
    return (!query || haystack.includes(query))
      && (type === "all" || item.event_type === type)
      && (category === "all" || item.categories?.includes(category))
      && (source === "all" || sourceNames(item).includes(source))
      && (windowDays === "all" || (days !== null && days >= 0 && days <= Number(windowDays)))
      && (showExpired || (days !== null && days >= 0 && !item.archived));
  }).sort((a, b) => (safeDate(a.primary_deadline)?.getTime() || Infinity) - (safeDate(b.primary_deadline)?.getTime() || Infinity));
  renderList();
}

function renderList() {
  const list = $("#eventList");
  list.replaceChildren();
  const template = $("#eventTemplate");
  state.filtered.slice(0, state.visible).forEach((item) => {
    const node = template.content.cloneNode(true);
    const row = node.querySelector(".event-row");
    const link = node.querySelector("h3 a");
    link.textContent = item.name; link.href = httpUrl(item.official_url) || "#";
    if (item.catalog_listed) {
      const star = document.createElement("span");
      star.className = "catalog-star"; star.textContent = "★";
      star.title = `已收录于指定赛事目录：${item.catalog_name || item.name}`;
      star.setAttribute("aria-label", "已收录于指定赛事目录");
      link.append(document.createTextNode(" "), star);
    }
    node.querySelector(".event-kicker").textContent = `${typeLabels[item.event_type] || item.event_type} / ${(item.region || "global").toUpperCase()}`;
    node.querySelector(".event-meta").textContent = [item.organizer, item.level, item.location, item.mode].filter(Boolean).join(" · ") || sourceStatus(item);
    const categories = node.querySelector(".event-categories");
    const rank = ccfRank(item);
    if (rank) {
      const tag = document.createElement("span");
      const rankClass = rank === "非 CCF" ? "none" : rank.slice(-1).toLowerCase();
      tag.className = `tag rank-tag rank-ccf-${rankClass}`;
      tag.textContent = rank;
      tag.title = `会议评级：${rank}`;
      categories.append(tag);
    }
    (item.categories || []).slice(0, 3).forEach((category) => {
      const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = category; categories.append(tag);
    });
    (item.university_tiers || []).forEach((tier) => {
      const tag = document.createElement("span");
      tag.className = `tag tier-tag tier-${tier === "双一流" ? "double-first" : tier}`;
      tag.textContent = tier; tag.title = `院校标签：${tier}`; categories.append(tag);
    });
    node.querySelector(".deadline strong").textContent = formatDate(item.primary_deadline);
    node.querySelector(".deadline span").textContent = `${primaryLabel(item)} · ${relative(item.primary_deadline)}`;
    const pill = node.querySelector(".status-pill");
    const days = daysUntil(item.primary_deadline);
    pill.textContent = statusLabels[item.status] || item.status;
    if (["registration_open", "submission_upcoming", "submission_open", "upcoming", "ongoing"].includes(item.status)) pill.classList.add("open");
    if (days !== null && days >= 0 && days <= 3) pill.classList.add("urgent");
    node.querySelector(".event-state small").textContent = sourceStatus(item);
    renderDetails(node, item);
    if (item.stale) row.classList.add("stale");
    list.append(node);
  });
  $("#resultCount").textContent = `${state.filtered.length} 条结果 · 显示 ${Math.min(state.visible, state.filtered.length)} 条`;
  $("#emptyState").hidden = state.filtered.length !== 0;
  $("#loadMore").hidden = state.visible >= state.filtered.length;
}

function renderMetrics(payload, sourceStatusPayload) {
  $("#totalMetric").textContent = payload.stats.total;
  $("#activeMetric").textContent = payload.stats.active;
  $("#weekMetric").textContent = payload.items.filter((item) => { const d = daysUntil(item.primary_deadline); return d !== null && d >= 0 && d <= 7; }).length;
  const sources = sourceStatusPayload?.sources || [];
  $("#sourceMetric").textContent = sources.filter((source) => source.ok).length || "—";
  $("#healthText").textContent = payload.source_health === "healthy" ? "所有数据源运行正常" : "部分数据源降级 · 历史记录已保留";
  $("#updatedAt").textContent = `LAST SYNC / ${new Date(payload.generated_at).toLocaleString("zh-CN", { hour12: false })} / ASIA·SHANGHAI`;
}

async function init() {
  try {
    const [dataResponse, sourceResponse] = await Promise.all([fetch("./data/competitions.json", { cache: "no-store" }), fetch("./data/source-status.json", { cache: "no-store" })]);
    if (!dataResponse.ok) throw new Error(`data HTTP ${dataResponse.status}`);
    const payload = await dataResponse.json();
    const sourcePayload = sourceResponse.ok ? await sourceResponse.json() : null;
    state.data = payload.items || [];
    renderOptions(state.data); renderMetrics(payload, sourcePayload); filterData();
  } catch (error) {
    $("#healthText").textContent = "数据暂时无法载入";
    $("#updatedAt").textContent = error.message;
    $("#emptyState").hidden = false;
  }
}

["#searchInput", "#typeFilter", "#categoryFilter", "#sourceFilter", "#windowFilter", "#expiredToggle"].forEach((selector) => {
  $(selector).addEventListener(selector === "#searchInput" ? "input" : "change", () => filterData());
});
$("#loadMore").addEventListener("click", () => { state.visible += 30; renderList(); });
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== $("#searchInput")) { event.preventDefault(); $("#searchInput").focus(); }
  if (event.key === "Escape") { $("#searchInput").value = ""; $("#searchInput").blur(); filterData(); }
});
setInterval(() => { state.now = new Date(); if (state.data.length) renderList(); }, 60000);
init();
