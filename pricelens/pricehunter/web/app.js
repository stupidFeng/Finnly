(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const PLATFORM = {
    jd: { name: "京东", color: "#ef4444" },
    tb: { name: "淘宝", color: "#f59e0b" },
    pdd: { name: "拼多多", color: "#f472b6" },
  };

  const TREND_COLORS = ["#34d399", "#60a5fa", "#fbbf24", "#f472b6", "#a78bfa", "#22d3ee"];

  const axisMoney = (value) => "¥" + Math.round(Math.max(0, value)).toLocaleString("zh-CN");

  const state = {
    data: null,
    backend: false,
    running: false,
    range: 90,
    hidden: new Set(),
    sort: { key: "price", dir: 1 },
    filter: "",
    sampleTab: "clean",
  };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  const money = (value) => {
    const num = Number(value) || 0;
    return "¥" + num.toLocaleString("zh-CN", {
      minimumFractionDigits: Number.isInteger(num) ? 0 : 2,
      maximumFractionDigits: 2,
    });
  };

  const compact = (value) => {
    const num = Number(value) || 0;
    if (num >= 100000) return (num / 10000).toFixed(1) + "万";
    if (num >= 10000) return (num / 10000).toFixed(1) + "万";
    return num.toLocaleString("zh-CN");
  };

  const pct = (value, total) => total > 0 ? Math.max(1.5, Math.min(100, value / total * 100)) : 0;

  /* ------------------------------------------------------------ 状态 */

  function setStatus(kind, text) {
    const el = $("#status");
    el.className = "status" + (kind === "ok" ? "" : kind === "busy" ? " busy" : " demo");
    $("span", el).textContent = text;
  }

  function setRunning(running) {
    state.running = running;
    const btn = $("#run");
    btn.disabled = running;
    btn.classList.toggle("loading", running);
    $(".btn-label", btn).textContent = running ? "采集中" : "开始采集";
    if (running) setStatus("busy", "正在采集 …");
  }

  function progress(value) {
    $("#progressBar").style.width = Math.max(0, Math.min(100, value)) + "%";
  }

  /* ------------------------------------------------------------ 初始化 */

  async function init() {
    const payload = $("#sample-data").textContent.trim();
    if (payload) {
      try { state.data = JSON.parse(payload); } catch (err) { state.data = null; }
    }

    bindEvents();
    if (state.data) {
      renderAll();
      setStatus("demo", "内置示例 · " + state.data.keyword);
    } else {
      $(".logbar").innerHTML = '<span class="muted">暂无示例数据，请输入关键词后运行采集</span>';
    }

    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      if (res.ok) {
        state.backend = true;
        setStatus("ok", state.data ? `已连接 · 示例「${state.data.keyword}」` : "本地服务已连接 · 可现场采集");
        if (state.data && state.data.report_url) $("#reportLink").hidden = false;
        if (state.data) $("#reportLink").href = state.data.report_url;
      }
    } catch (err) {
      state.backend = false;
    }
  }

  /* ------------------------------------------------------------ 渲染总入口 */

  function renderAll() {
    if (!state.data) return;
    const data = state.data;

    $("#heroCount").textContent = data.stats.unique;
    $("#heroGroups").textContent = data.stats.groups;
    $("#heroTime").textContent = data.elapsed_ms;

    renderKpis(data);
    renderPlatform(data);
    renderTrend(data);
    renderScatter(data);
    renderGroups(data);
    renderRecs(data);
    renderTable();
    renderSample();
  }

  function renderKpis(data) {
    const s = data.stats;
    const cards = [
      { label: "有效商品", value: s.unique, note: `原始 ${s.raw} 条 · 去重 ${s.removed} 条`, cls: "" },
      { label: "最低到手价", value: money(s.min_price), note: `中位价 ${money(s.median_price)}`, cls: "accent" },
      { label: "同款分组", value: s.groups, note: `覆盖 ${s.platforms} 个平台`, cls: "" },
      { label: "价格区间", value: money(s.max_price), note: `均价 ${money(s.avg_price)}`, cls: "" },
      { label: "总销量", value: compact(s.total_sales), note: "各平台近 30 天", cls: "" },
      { label: "最高性价比", value: s.best_value, note: "价格45% + 销量30% + 口碑25%", cls: "amber" },
    ];
    $("#overview").innerHTML = cards.map((card) => `
      <article class="kpi ${card.cls}">
        <span>${esc(card.label)}</span>
        <b>${esc(card.value)}</b>
        <small>${esc(card.note)}</small>
      </article>`).join("");
  }

  function renderPlatform(data) {
    const stats = data.platform_stats || [];
    const max = Math.max(...stats.map((item) => item.avg_price), 1);
    $("#platformBars").innerHTML = stats.map((item) => `
      <div class="pbar-row">
        <div class="pbar-name"><i style="background:${item.color}"></i>${esc(item.name)}</div>
        <div class="pbar-track">
          <div class="pbar-fill" style="width:${pct(item.avg_price, max)}%;background:linear-gradient(90deg,${item.color},${item.color}55)"></div>
        </div>
        <div class="pbar-price">${money(item.avg_price)}</div>
      </div>`).join("");

    $("#platformMeta").innerHTML = stats.map((item) => `
      <div>
        <b style="color:${item.color}">${item.count}</b>
        <span>${esc(item.name)} · 均销 ${compact(item.avg_sales)}</span>
      </div>`).join("");
  }

  /* ------------------------------------------------------------ 趋势图 */

  function renderTrend(data) {
    const el = $("#trendChart");
    const trend = data.trend;
    if (!trend || !trend.series.length) {
      el.innerHTML = '<div class="empty">该批数据暂无价格历史</div>';
      $("#trendLegend").innerHTML = "";
      return;
    }
    const allSeries = trend.series.map((item, index) => ({
      ...item,
      color: TREND_COLORS[index % TREND_COLORS.length],
    }));
    renderTrendLegend(allSeries);

    const range = state.range;
    const dates = trend.dates.slice(-range);
    const series = allSeries
      .filter((item) => !state.hidden.has(item.id))
      .map((item) => ({ ...item, values: item.values.slice(-range) }));

    if (!series.length) {
      el.innerHTML = '<div class="empty">已隐藏全部曲线，点击下方图例恢复</div>';
      return;
    }

    const W = Math.max(el.clientWidth || 680, 320);
    const H = 300;
    const pad = { l: 58, r: 14, t: 16, b: 28 };
    const plotW = W - pad.l - pad.r;
    const plotH = H - pad.t - pad.b;
    const values = series.flatMap((item) => item.values);
    let low = Math.min(...values);
    let high = Math.max(...values);
    const span = (high - low) || Math.max(high * 0.05, 1);
    low = Math.max(0, low - span * 0.2);
    high += span * 0.12;
    const n = dates.length;
    const step = n > 1 ? plotW / (n - 1) : plotW;
    const px = (i) => pad.l + step * i;
    const py = (v) => pad.t + plotH * (1 - (v - low) / (high - low));

    let grid = "";
    for (let i = 0; i <= 4; i++) {
      const value = low + (high - low) * i / 4;
      const y = py(value);
      grid += `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${W - pad.r}" y2="${y.toFixed(1)}" stroke="rgba(255,255,255,.06)"/>`;
      grid += `<text x="${pad.l - 10}" y="${(y + 3.5).toFixed(1)}" fill="#5b6879" font-size="10" text-anchor="end" font-family="ui-monospace,monospace">${axisMoney(value)}</text>`;
    }
    let xLabels = "";
    [0, Math.floor((n - 1) / 3), Math.floor((n - 1) * 2 / 3), n - 1].forEach((index) => {
      if (index < 0 || index >= n) return;
      xLabels += `<text x="${px(index).toFixed(1)}" y="${H - 8}" fill="#5b6879" font-size="10" text-anchor="middle" font-family="ui-monospace,monospace">${dates[index].slice(5)}</text>`;
    });

    const lines = series.map((item) => {
      const points = item.values.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(" ");
      return `<polyline points="${points}" fill="none" stroke="${item.color}" stroke-width="2"
        stroke-linejoin="round" stroke-linecap="round" opacity=".88"/>
        <circle cx="${px(n - 1).toFixed(1)}" cy="${py(item.values[n - 1]).toFixed(1)}" r="3.2" fill="${item.color}"/>`;
    }).join("");

    el.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="价格趋势">
        <defs>
          <linearGradient id="areaFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${series[0].color}" stop-opacity=".22"/>
            <stop offset="1" stop-color="${series[0].color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        ${grid}${xLabels}
        <path d="M ${px(0)},${py(series[0].values[0])} ${series[0].values.map((v, i) => `L ${px(i)},${py(v)}`).join(" ")}
          L ${px(n - 1)},${pad.t + plotH} L ${px(0)},${pad.t + plotH} Z" fill="url(#areaFade)" opacity=".5"/>
        ${lines}
        <line class="crosshair" x1="0" y1="${pad.t}" x2="0" y2="${pad.t + plotH}" stroke="rgba(255,255,255,.22)" stroke-dasharray="3 3" opacity="0"/>
        <g class="hoverDots"></g>
        <rect class="hitArea" x="${pad.l}" y="${pad.t}" width="${plotW}" height="${plotH}" fill="transparent"/>
      </svg>
      <div class="tooltip"></div>`;

    const svg = $("svg", el);
    const tip = $(".tooltip", el);
    const cross = $(".crosshair", el);
    const dots = $(".hoverDots", el);

    const move = (event) => {
      const rect = svg.getBoundingClientRect();
      const scale = W / rect.width;
      const x = (event.clientX - rect.left) * scale;
      let index = Math.round((x - pad.l) / step);
      index = Math.max(0, Math.min(n - 1, index));
      const cx = px(index);
      cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("opacity", "1");
      dots.innerHTML = series.map((item) =>
        `<circle cx="${cx}" cy="${py(item.values[index]).toFixed(1)}" r="3.4" fill="${item.color}" stroke="#070a0f" stroke-width="1.5"/>`
      ).join("");
      tip.innerHTML = `<div class="tt-date">${dates[index]}</div>` + series.map((item) => `
        <div class="tt-row"><span><em style="display:inline-block;width:6px;height:6px;border-radius:2px;background:${item.color};margin-right:5px"></em>${esc(item.name)}</span>
        <b>${money(item.values[index])}</b></div>`).join("");
      const left = Math.min(Math.max(cx / scale + 16, 8), rect.width - 170);
      const top = Math.min(Math.max(event.clientY - rect.top - 30, 6), rect.height - 130);
      tip.style.left = left + "px";
      tip.style.top = top + "px";
      tip.classList.add("show");
    };

    const leave = () => {
      tip.classList.remove("show");
      cross.setAttribute("opacity", "0");
      dots.innerHTML = "";
    };

    svg.addEventListener("mousemove", move);
    svg.addEventListener("mouseleave", leave);
  }

  function renderTrendLegend(series) {
    $("#trendLegend").innerHTML = series.map((item) => `
      <button data-series="${esc(item.id)}" class="${state.hidden.has(item.id) ? "off" : ""}">
        <em style="background:${item.color}"></em>${esc(item.name)}
        <span class="lv">${money(item.current)}</span>
      </button>`).join("");
  }

  /* ------------------------------------------------------------ 散点图 */

  function renderScatter(data) {
    const el = $("#scatterChart");
    const products = data.products || [];
    if (!products.length) {
      el.innerHTML = '<div class="empty">暂无数据</div>';
      return;
    }
    $("#scatterLegend").innerHTML = Object.values(PLATFORM).map((item) =>
      `<span><i style="background:${item.color}"></i>${item.name}</span>`).join("");

    const W = Math.max(el.clientWidth || 900, 320);
    const H = 320;
    const pad = { l: 58, r: 18, t: 18, b: 34 };
    const plotW = W - pad.l - pad.r;
    const plotH = H - pad.t - pad.b;
    const prices = products.map((item) => item.price);
    const logs = products.map((item) => Math.log10(item.sales + 10));
    let pMin = Math.min(...prices);
    let pMax = Math.max(...prices);
    const pPad = (pMax - pMin) * 0.08 || 1;
    pMin -= pPad; pMax += pPad;
    const lMin = Math.min(...logs);
    const lMax = Math.max(...logs) + 0.12;

    const px = (price) => pad.l + plotW * (price - pMin) / (pMax - pMin);
    const py = (logValue) => pad.t + plotH * (1 - (logValue - lMin) / (lMax - lMin));

    let grid = "";
    for (let i = 0; i <= 4; i++) {
      const price = pMin + (pMax - pMin) * i / 4;
      const x = px(price);
      grid += `<line x1="${x.toFixed(1)}" y1="${pad.t}" x2="${x.toFixed(1)}" y2="${pad.t + plotH}" stroke="rgba(255,255,255,.05)"/>`;
      grid += `<text x="${x.toFixed(1)}" y="${H - 12}" fill="#5b6879" font-size="10" text-anchor="middle" font-family="ui-monospace,monospace">${Math.round(price)}</text>`;
    }
    for (let i = 0; i <= 3; i++) {
      const logValue = lMin + (lMax - lMin) * i / 3;
      const y = py(logValue);
      grid += `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${pad.l + plotW}" y2="${y.toFixed(1)}" stroke="rgba(255,255,255,.05)"/>`;
      grid += `<text x="${pad.l - 10}" y="${(y + 3.5).toFixed(1)}" fill="#5b6879" font-size="10" text-anchor="end" font-family="ui-monospace,monospace">${compact(Math.round(10 ** logValue))}</text>`;
    }

    const points = products.map((item) => {
      const color = (PLATFORM[item.platform] || {}).color || "#94a3b8";
      const x = px(item.price);
      const y = py(Math.log10(item.sales + 10));
      const r = 4 + Math.max(0, (item.rating || 4.3) - 4) * 7;
      return { item, x, y, r, color };
    });

    const bubbles = points.map((point) => `
      <g class="bubble">
        <circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="${point.r.toFixed(1)}" fill="${point.color}" opacity=".24"/>
        <circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="2.6" fill="${point.color}"/>
      </g>`).join("");

    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="价格销量分布">
      ${grid}${bubbles}
      <text x="${pad.l + plotW / 2}" y="${H - 1}" fill="#465262" font-size="10" text-anchor="middle">价格 →</text>
    </svg><div class="tooltip"></div>`;

    const svg = $("svg", el);
    const tip = $(".tooltip", el);
    svg.addEventListener("mousemove", (event) => {
      const rect = svg.getBoundingClientRect();
      const scale = W / rect.width;
      const x = (event.clientX - rect.left) * scale;
      const y = (event.clientY - rect.top) * (H / rect.height);
      let nearest = null;
      let distance = 20;
      points.forEach((point) => {
        const d = Math.hypot(point.x - x, point.y - y);
        if (d < distance) { distance = d; nearest = point; }
      });
      if (!nearest) { tip.classList.remove("show"); return; }
      const meta = PLATFORM[nearest.item.platform] || { name: nearest.item.platform_name, color: "#94a3b8" };
      tip.innerHTML = `<div class="tt-date">${esc(nearest.item.platform_name)}</div>
        <div class="tt-row"><span>${esc(nearest.item.title_clean.slice(0, 26))}</span></div>
        <div class="tt-row"><span>价格</span><b>${money(nearest.item.price)}</b></div>
        <div class="tt-row"><span>销量</span><b>${compact(nearest.item.sales)}</b></div>
        <div class="tt-row"><span>店铺评分</span><b>${nearest.item.rating ?? "—"}</b></div>
        <div class="tt-row"><span>性价比</span><b style="color:${meta.color}">${nearest.item.value_index}</b></div>`;
      tip.style.left = Math.min(Math.max(nearest.x / scale + 14, 8), rect.width - 220) + "px";
      tip.style.top = Math.min(Math.max(nearest.y - 10, 8), rect.height - 130) + "px";
      tip.classList.add("show");
    });
    svg.addEventListener("mouseleave", () => tip.classList.remove("show"));
  }

  /* ------------------------------------------------------------ 同款对比 */

  function renderGroups(data) {
    const groups = (data.groups || []).filter((group) => group.count > 1);
    groups.sort((a, b) => b.spread_pct - a.spread_pct);
    $("#groupCounter").textContent = `展示 ${Math.min(9, groups.length)} / ${groups.length} 组同款（共 ${data.stats.groups} 组）`;
    if (!groups.length) {
      $("#groups").innerHTML = '<div class="empty">本批数据没有跨平台同款，试试更换关键词</div>';
      return;
    }
    $("#groups").innerHTML = groups.slice(0, 9).map((group) => {
      const rows = group.items.map((row) => `
        <div class="grow ${row.id === group.cheapest_id ? "best" : ""}">
          <div class="gleft">
            <span class="pill p-${row.platform}">${esc(PLATFORM[row.platform]?.name || row.platform_name)}</span>
            <span class="shop" title="${esc(row.shop)}">${esc(row.shop || "—")}</span>
          </div>
          <a href="${esc(row.url)}" target="_blank" rel="noopener"><span class="gp">${money(row.price)}</span></a>
        </div>`).join("");
      return `<article class="group">
        <h3>${esc(group.title)}</h3>
        <div class="meta">
          <span>${esc(group.brand)} ${esc(group.model)}</span>
          <span><b>${group.count}</b> 条报价</span>
          <span><b>${group.platform_count}</b> 平台</span>
          <span class="spread">价差 ${group.spread_pct}%</span>
        </div>
        ${rows}
      </article>`;
    }).join("");
  }

  /* ------------------------------------------------------------ 推荐 */

  const REC_COLORS = { value: "#34d399", budget: "#fbbf24", sales: "#60a5fa", quality: "#c084fc" };

  function renderRecs(data) {
    const recs = data.recommendations || [];
    if (!recs.length) {
      $("#recs").innerHTML = '<div class="empty">暂无推荐</div>';
      return;
    }
    $("#recs").innerHTML = recs.map((rec) => `
      <article class="rec" style="--accent:${REC_COLORS[rec.type] || "#34d399"}">
        <span class="rlabel">${esc(rec.label)}</span>
        <h3>${esc(rec.title)}</h3>
        <div class="rprice">
          <b>${money(rec.price)}</b>
          <span>${esc(rec.platform_name)} · 销量 ${compact(rec.sales)}</span>
        </div>
        <p>${esc(rec.reason)}</p>
        <div class="rfoot">
          <span>性价比 ${data.products.find((item) => item.id === rec.product_id)?.value_index ?? "—"}</span>
          <a href="${esc(rec.url)}" target="_blank" rel="noopener">查看商品 →</a>
        </div>
      </article>`).join("");
  }

  /* ------------------------------------------------------------ 明细表 */

  function sortedProducts() {
    const products = (state.data.products || []).slice();
    const { key, dir } = state.sort;
    const weight = (item) => {
      if (key === "rating") return item.rating ?? -1;
      if (key === "title") return item.title_clean;
      if (key === "platform") return item.platform_name;
      if (key === "sales") return item.sales;
      if (key === "value") return item.value_index;
      return item.price;
    };
    products.sort((a, b) => {
      const av = weight(a);
      const bv = weight(b);
      if (typeof av === "string") return av.localeCompare(bv, "zh-CN") * dir;
      return (av - bv) * dir;
    });
    return products;
  }

  function renderTable() {
    if (!state.data) return;
    const keyword = state.filter.trim().toLowerCase();
    const products = sortedProducts().filter((item) => {
      if (!keyword) return true;
      return [item.title_clean, item.brand, item.model, item.shop, item.platform_name]
        .join(" ").toLowerCase().includes(keyword);
    });

    $$("#table thead th").forEach((th) => {
      const key = th.dataset.sort;
      th.classList.toggle("sorted", key === state.sort.key);
      const icon = $("i", th);
      if (icon) icon.textContent = state.sort.dir === 1 ? "↑" : "↓";
    });

    if (!products.length) {
      $("#tableBody").innerHTML = '<tr><td colspan="9"><div class="empty">没有匹配的商品</div></td></tr>';
      return;
    }

    $("#tableBody").innerHTML = products.map((item, index) => {
      const tags = item.tags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join("")
        + item.flags.map((flag) => `<span class="tag warn">${esc(flag)}</span>`).join("");
      return `<tr>
        <td class="mono-cell">${String(index + 1).padStart(2, "0")}</td>
        <td><span class="pill p-${item.platform}">${esc(item.platform_name)}</span></td>
        <td class="title">
          <a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title_clean.slice(0, 54))}</a>
          <div class="t-meta">${esc(item.brand)} ${esc(item.model)} · ${esc(item.shop || "—")}</div>
        </td>
        <td class="price-cell">${money(item.price)}${item.list_price ? `<s>${money(item.list_price)}</s>` : ""}</td>
        <td class="mono-cell">${item.sales.toLocaleString("zh-CN")}</td>
        <td class="mono-cell">${item.rating ?? "—"}</td>
        <td>
          <span class="mono-cell" style="color:var(--text)">${item.value_index}</span>
          <div class="vbar"><i style="width:${item.value_index}%"></i></div>
        </td>
        <td>${tags || '<span class="muted">—</span>'}</td>
        <td><a class="link-icon" href="${esc(item.url)}" target="_blank" rel="noopener" title="打开商品页">↗</a></td>
      </tr>`;
    }).join("");
  }

  /* ------------------------------------------------------------ 数据示例 */

  function renderSample() {
    const data = state.data;
    const body = $("#sampleBody");
    const tab = state.sampleTab;

    $$("#sampleTabs button").forEach((button) => {
      button.classList.toggle("on", button.dataset.tab === tab);
    });

    if (tab === "raw") {
      const rows = data.raw_sample || [];
      body.innerHTML = `<p class="sample-note">适配器原样返回的字段：价格与销量保留平台文本形态（如「2.3万+人付款」「¥1,299.00」），由清洗层统一解析。</p>
        <div class="table-wrap" style="max-height:320px"><table class="data-table">
        <thead><tr><th>平台</th><th>原始标题</th><th>价格(原)</th><th>销量(原)</th><th>评分(原)</th><th>店铺</th></tr></thead>
        <tbody>${rows.map((row) => `<tr>
          <td><span class="pill p-${row.platform}">${esc(row.platform_name)}</span></td>
          <td class="title">${esc(String(row.title).slice(0, 46))}</td>
          <td class="mono-cell">${esc(row.price)}</td>
          <td class="mono-cell">${esc(row.sales)}</td>
          <td class="mono-cell">${esc(row.rating ?? "—")}</td>
          <td class="t-meta">${esc(row.shop)}</td>
        </tr>`).join("")}</tbody></table></div>`;
      return;
    }

    if (tab === "clean") {
      const rows = (data.products || []).slice(0, 8);
      body.innerHTML = `<p class="sample-note">清洗后统一为数值字段，并抽取品牌 / 型号用于同款归组（group_id）。价格已按数值升序排列。</p>
        <div class="table-wrap" style="max-height:320px"><table class="data-table">
        <thead><tr><th>ID</th><th>平台</th><th>清洗标题</th><th>品牌</th><th>型号</th><th>价格</th><th>销量</th><th>评分</th><th>分组</th></tr></thead>
        <tbody>${rows.map((row) => `<tr>
          <td class="mono-cell">${esc(row.id)}</td>
          <td><span class="pill p-${row.platform}">${esc(row.platform_name)}</span></td>
          <td class="title">${esc(row.title_clean.slice(0, 40))}</td>
          <td class="mono-cell">${esc(row.brand || "—")}</td>
          <td class="mono-cell">${esc(row.model || "—")}</td>
          <td class="price-cell">${money(row.price)}</td>
          <td class="mono-cell">${row.sales.toLocaleString("zh-CN")}</td>
          <td class="mono-cell">${row.rating ?? "—"}</td>
          <td class="mono-cell">${esc(row.group_id)}</td>
        </tr>`).join("")}</tbody></table></div>`;
      return;
    }

    const sample = {
      stats: data.stats,
      platform_stats: data.platform_stats,
      trend: {
        dates: [data.trend.dates[0], data.trend.dates.at(-1)],
        series: data.trend.series.map((item) => ({
          name: item.name, platform: item.platform, current: item.current,
          low: item.low, signal: item.signal, change_30d: item.change_30d,
        })),
      },
      groups: (data.groups || []).slice(0, 2),
      recommendations: data.recommendations,
    };
    body.innerHTML = `<p class="sample-note">分析层输出的结构化结果，直接用于前端图表与静态报告渲染；完整 JSON 同时写入 out/ 目录。</p>
      <pre class="code">${esc(JSON.stringify(sample, null, 2))}</pre>`;
  }

  /* ------------------------------------------------------------ 采集 */

  async function runSearch() {
    if (state.running) return;
    const keyword = $("#keyword").value.trim();
    if (!keyword) {
      $("#logs").innerHTML = '<span class="warn">请先输入关键词</span>';
      $("#keyword").focus();
      return;
    }

    const platforms = $$(".chip input:checked").map((input) => input.value);
    if (!platforms.length) {
      $("#logs").innerHTML = '<span class="warn">至少选择一个平台</span>';
      return;
    }

    setRunning(true);
    $("#logs").innerHTML = '<span class="muted">正在连接采集适配器 …</span>';
    progress(12);
    const ticker = setInterval(() => {
      const current = parseFloat($("#progressBar").style.width) || 12;
      if (current < 86) progress(current + Math.random() * 9);
    }, 220);

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword,
          platforms,
          limit: Number($("#limit").value),
          source: $("#source").value,
        }),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.error || ("HTTP " + res.status));

      clearInterval(ticker);
      progress(100);
      await playLogs(payload.logs || []);

      state.data = payload;
      state.hidden.clear();
      state.filter = "";
      $("#filter").value = "";
      state.sort = { key: "price", dir: 1 };
      renderAll();
      setStatus("ok", "本地服务 · " + payload.keyword);
      $("#reportLink").hidden = !payload.report_url;
      if (payload.report_url) $("#reportLink").href = payload.report_url;
    } catch (err) {
      clearInterval(ticker);
      progress(0);
      const hint = state.backend
        ? esc(err.message)
        : "未检测到本地服务。请在项目目录执行 <b>python -m pricehunter serve --open</b> 后重试；当前展示的是内置示例数据。";
      $("#logs").innerHTML = `<span class="error">采集未执行：${hint}</span>`;
      setStatus("demo", "内置示例数据");
    } finally {
      setRunning(false);
      setTimeout(() => progress(0), 1200);
    }
  }

  async function playLogs(logs) {
    const el = $("#logs");
    el.innerHTML = "";
    if (!logs.length) return;
    const delay = Math.min(70, 1500 / logs.length);
    for (const line of logs) {
      const span = document.createElement("span");
      const level = line.level === "ok" ? "ok" : line.level === "warn" ? "warn" : line.level === "error" ? "error" : "muted";
      span.className = level;
      span.textContent = line.text;
      el.appendChild(span);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  /* ------------------------------------------------------------ 事件 */

  function bindEvents() {
    $("#run").addEventListener("click", runSearch);
    $("#keyword").addEventListener("keydown", (event) => {
      if (event.key === "Enter") runSearch();
    });

    $$(".chip").forEach((chip) => {
      chip.addEventListener("click", (event) => {
        event.preventDefault();
        const input = $("input", chip);
        input.checked = !input.checked;
        chip.classList.toggle("on", input.checked);
      });
    });

    $$(".suggest button").forEach((button) => {
      button.addEventListener("click", () => {
        $("#keyword").value = button.dataset.kw;
        runSearch();
      });
    });

    $("#rangeSeg").addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      state.range = Number(button.dataset.range);
      $$("#rangeSeg button").forEach((item) => item.classList.toggle("on", item === button));
      renderTrend(state.data);
    });

    $("#trendLegend").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-series]");
      if (!button) return;
      const id = button.dataset.series;
      if (state.hidden.has(id)) state.hidden.delete(id);
      else state.hidden.add(id);
      renderTrend(state.data);
    });

    $("#table thead").addEventListener("click", (event) => {
      const th = event.target.closest("th[data-sort]");
      if (!th) return;
      const key = th.dataset.sort;
      if (key === "rank") {
        state.sort = { key: "price", dir: 1 };
      } else if (state.sort.key === key) {
        state.sort.dir *= -1;
      } else {
        state.sort = { key, dir: key === "price" || key === "rating" ? 1 : -1 };
      }
      renderTable();
    });

    $("#filter").addEventListener("input", (event) => {
      state.filter = event.target.value;
      renderTable();
    });

    $("#sampleTabs").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-tab]");
      if (!button) return;
      state.sampleTab = button.dataset.tab;
      renderSample();
    });

    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (!state.data) return;
        renderTrend(state.data);
        renderScatter(state.data);
      }, 180);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
