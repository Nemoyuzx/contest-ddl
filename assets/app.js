const state = { data: [], filtered: [], visible: 30, now: new Date() };
const $ = (selector) => document.querySelector(selector);
const typeLabels = { competition: "竞赛", hackathon: "黑客松", summer_camp: "夏令营", pre_admission: "预推免" };
const statusLabels = {
  registration_open: "报名中", registration_upcoming: "即将报名", registration_closed: "报名已截止",
  submission_open: "提交中", upcoming: "即将开始", ongoing: "进行中", ended: "已结束", unknown: "待核验"
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
  return diff < 0 ? -1 : Math.ceil(diff / 86400000);
}

function formatDate(value) {
  const date = safeDate(value);
  if (!date) return "日期待核验";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

function relative(value) {
  const days = daysUntil(value);
  if (days === null) return "请查看官方页";
  if (days < -1) return `已过 ${Math.abs(days)} 天`;
  if (days === -1) return "已截止";
  if (days === 0) return "今天截止";
  if (days === 1) return "明天截止";
  return `${days} 天后`;
}

function sourceStatus(item) {
  if (item.stale) return "历史缓存 · 需复核";
  if (item.verification_status === "cross_source") return `${item.sources.length} 个来源交叉核验`;
  if (item.verification_status === "maintainer_reviewed") return "维护者已核验";
  return item.source?.name || "来源未知";
}

function renderOptions(items) {
  const types = [...new Set(items.map((item) => item.event_type))].sort();
  const categories = [...new Set(items.flatMap((item) => item.categories || []))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  types.forEach((type) => $("#typeFilter").insertAdjacentHTML("beforeend", `<option value="${type}">${typeLabels[type] || type}</option>`));
  categories.forEach((category) => {
    const option = document.createElement("option"); option.value = category; option.textContent = category; $("#categoryFilter").append(option);
  });
}

function filterData(reset = true) {
  if (reset) state.visible = 30;
  const query = $("#searchInput").value.trim().toLowerCase();
  const type = $("#typeFilter").value;
  const category = $("#categoryFilter").value;
  const windowDays = $("#windowFilter").value;
  const showExpired = $("#expiredToggle").checked;
  state.filtered = state.data.filter((item) => {
    const haystack = [item.name, item.organizer, item.location, item.notes, ...(item.categories || []), ...(item.tags || [])].join(" ").toLowerCase();
    const days = daysUntil(item.primary_deadline);
    return (!query || haystack.includes(query))
      && (type === "all" || item.event_type === type)
      && (category === "all" || item.categories?.includes(category))
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
    link.textContent = item.name; link.href = item.official_url;
    node.querySelector(".event-kicker").textContent = `${typeLabels[item.event_type] || item.event_type} / ${(item.region || "global").toUpperCase()}`;
    node.querySelector(".event-meta").textContent = [item.organizer, item.location, item.mode].filter(Boolean).join(" · ") || sourceStatus(item);
    const categories = node.querySelector(".event-categories");
    (item.categories || []).slice(0, 3).forEach((category) => {
      const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = category; categories.append(tag);
    });
    node.querySelector(".deadline strong").textContent = formatDate(item.primary_deadline);
    node.querySelector(".deadline span").textContent = relative(item.primary_deadline);
    const pill = node.querySelector(".status-pill");
    const days = daysUntil(item.primary_deadline);
    pill.textContent = statusLabels[item.status] || item.status;
    if (["registration_open", "submission_open", "upcoming", "ongoing"].includes(item.status)) pill.classList.add("open");
    if (days !== null && days >= 0 && days <= 3) pill.classList.add("urgent");
    node.querySelector(".event-state small").textContent = sourceStatus(item);
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

["#searchInput", "#typeFilter", "#categoryFilter", "#windowFilter", "#expiredToggle"].forEach((selector) => {
  $(selector).addEventListener(selector === "#searchInput" ? "input" : "change", () => filterData());
});
$("#loadMore").addEventListener("click", () => { state.visible += 30; renderList(); });
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== $("#searchInput")) { event.preventDefault(); $("#searchInput").focus(); }
  if (event.key === "Escape") { $("#searchInput").value = ""; $("#searchInput").blur(); filterData(); }
});
setInterval(() => { state.now = new Date(); if (state.data.length) renderList(); }, 60000);
init();
