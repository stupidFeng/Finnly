/**
 * Finnly 热点聚合 - 扒取与评分脚本
 *
 * 流程: 扒取 → 去重聚类 → 分类 → 评分 → 多样性配额 → 输出 feed.json
 *
 * 数据源: 各平台公开热榜接口 (直接扒取, 不依赖第三方聚合 API)
 *   - 百度热搜、今日头条、知乎热榜、36氪快讯、澎湃热榜
 *
 * 用法:
 *   node scripts/fetch-and-score.mjs
 *
 * 环境变量:
 *   FEED_LIMIT     - 输出条数 (默认 15)
 *   FETCH_TOP      - 每源拉取条数 (默认 20)
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FEED_LIMIT = parseInt(process.env.FEED_LIMIT || '15', 10);
const FETCH_TOP = parseInt(process.env.FETCH_TOP || '20', 10);

// ============================================================
// 配置: 渠道定义 (MVP 5 源, 直接扒各平台公开接口)
// ============================================================
const CHANNELS = [
  { name: 'baidu',    field: 'society',        weight: 0.80, adapter: 'baidu' },
  { name: 'toutiao',  field: 'society',        weight: 0.85, adapter: 'toutiao' },
  { name: 'zhihu',    field: 'society',        weight: 0.75, adapter: 'zhihu' },
  { name: '36kr',     field: 'economy',        weight: 0.90, adapter: '36kr' },
  { name: 'thepaper', field: 'society',        weight: 0.85, adapter: 'thepaper' },
];

const FIELD_LABELS = {
  society: '社会',
  economy: '经济',
  entertainment: '娱乐',
};

const KEYWORDS = {
  economy: ['股价', '央行', '营收', '利润', 'GDP', '通胀', '利率', '股市', '基金', '汇率', '债券', '上市', '财报', '市值', '降息', '加息', '贸易', '关税', '经济'],
  entertainment: ['综艺', '明星', '票房', '演唱会', '选秀', '电视剧', '电影', '偶像', '娱乐', '艺人', '演员', '歌手'],
  society: ['事故', '灾害', '天气', '地震', '洪水', '政策', '法院', '警方', '通报', '调查', '社会', '民生', '教育', '医疗'],
};

const SCORE_WEIGHTS = { H: 0.4, T: 0.3, M: 0.3 };
const FRESH_TAU_HOURS = 6;
const QUOTA = { society: 4, economy: 4, entertainment: 4 };
const TOP_N = 40;

// ============================================================
// 模块 1: 扒取层 (各平台原生接口适配器)
// ============================================================
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';

async function fetchJSON(url, headers = {}) {
  const resp = await fetch(url, {
    headers: { 'User-Agent': UA, 'Accept': 'application/json', ...headers },
    signal: AbortSignal.timeout(15000),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

function makeItem(channel, cfg, idx, title, desc, hot, url, time) {
  return {
    title: (title || '').trim(),
    desc: (desc || '').trim(),
    hot: Number(hot) || 0,
    url: url || '',
    time: time || Date.now(),
    channel: cfg.name,
    channelField: cfg.field,
    channelWeight: cfg.weight,
    rank: idx + 1,
  };
}

async function fetchBaidu(cfg) {
  const json = await fetchJSON('https://top.baidu.com/api/board?platform=wise&tab=realtime');
  const list = json?.data?.cards?.[0]?.content?.[0]?.content || json?.data?.cards?.[0]?.content || [];
  return list.slice(0, FETCH_TOP).map((it, i) =>
    makeItem('baidu', cfg, i, it.word, it.desc || '', it.hotScore || 0, it.url, Date.now())
  ).filter(it => it.title);
}

async function fetchToutiao(cfg) {
  const json = await fetchJSON('https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc');
  const list = json?.data || [];
  return list.slice(0, FETCH_TOP).map((it, i) =>
    makeItem('toutiao', cfg, i, it.Title, '', it.HotValue || 0,
      `https://www.toutiao.com/trending/${it.ClusterIdStr}/`, Date.now())
  ).filter(it => it.title);
}

async function fetchZhihu(cfg) {
  const json = await fetchJSON('https://www.zhihu.com/api/v3/feed/topstory/hot-list-web?limit=' + FETCH_TOP);
  const list = json?.data || [];
  return list.map((it, i) => {
    const title = it.target?.title_area?.text || '';
    const excerpt = it.target?.excerpt || '';
    const id = it.target?.id || '';
    const hot = it.detail_text ? parseInt(it.detail_text.replace(/\D/g, ''), 10) : 0;
    return makeItem('zhihu', cfg, i, title, excerpt, hot,
      id ? `https://www.zhihu.com/question/${id}` : '', Date.now());
  }).filter(it => it.title);
}

async function fetch36kr(cfg) {
  const json = await fetchJSON('https://36kr.com/api/newsflash?per_page=' + FETCH_TOP);
  const list = json?.data?.items || [];
  return list.slice(0, FETCH_TOP).map((it, i) =>
    makeItem('36kr', cfg, i, it.title, it.description || '', 0,
      it.news_url_type === 1 ? `https://36kr.com/newsflashes/${it.id}` : '', Date.now())
  ).filter(it => it.title);
}

async function fetchThepaper(cfg) {
  const json = await fetchJSON('https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar');
  const list = json?.data?.hotNews || [];
  return list.slice(0, FETCH_TOP).map((it, i) =>
    makeItem('thepaper', cfg, i, it.name, it.summary || '', 0,
      `https://www.thepaper.cn/newsDetail_forward_${it.contId}`, Date.now())
  ).filter(it => it.title);
}

const ADAPTERS = { baidu: fetchBaidu, toutiao: fetchToutiao, zhihu: fetchZhihu, '36kr': fetch36kr, thepaper: fetchThepaper };

async function fetchChannel(cfg) {
  try {
    const fn = ADAPTERS[cfg.adapter];
    if (!fn) throw new Error(`未知适配器: ${cfg.adapter}`);
    return await fn(cfg);
  } catch (err) {
    console.error(`[扒取] ${cfg.name} 失败: ${err.message}`);
    return [];
  }
}

async function fetchAllChannels() {
  const results = await Promise.all(CHANNELS.map(fetchChannel));
  const all = results.flat();
  console.log(`[扒取] 共拉取 ${all.length} 条 (各源: ${results.map((r, i) => `${CHANNELS[i].name}:${r.length}`).join(', ')})`);
  return all;
}

// ============================================================
// 模块 2: 去重聚类
// ============================================================
function normalizeTitle(title) {
  return title
    .replace(/[\u{1F000}-\u{1FAFF}]/gu, '')
    .replace(/[\p{P}\p{S}]/gu, '')
    .replace(/\s+/g, '')
    .toLowerCase();
}

function bigrams(str) {
  const set = new Set();
  for (let i = 0; i < str.length - 1; i++) set.add(str.slice(i, i + 2));
  return set;
}

function jaccard(a, b) {
  const sa = bigrams(a), sb = bigrams(b);
  if (sa.size === 0 || sb.size === 0) return 0;
  let inter = 0;
  for (const x of sa) if (sb.has(x)) inter++;
  return inter / (sa.size + sb.size - inter);
}

function clusterEvents(items) {
  const events = [];
  for (const item of items) {
    const norm = normalizeTitle(item.title);
    let merged = false;
    for (const ev of events) {
      if (jaccard(norm, ev.normKey) >= 0.6) {
        ev.sources.push(item);
        if (item.hot > ev.maxHot) ev.maxHot = item.hot;
        if (item.time < ev.minTime) ev.minTime = item.time;
        if (norm.length > ev.normKey.length) ev.normKey = norm;
        merged = true;
        break;
      }
    }
    if (!merged) {
      events.push({
        normKey: norm,
        sources: [item],
        maxHot: item.hot,
        minTime: item.time,
      });
    }
  }
  console.log(`[去重] ${items.length} 条 → ${events.length} 个事件 (合并 ${items.length - events.length} 条)`);
  return events;
}

// ============================================================
// 模块 3: 分类
// ============================================================
function classify(ev) {
  const text = ev.sources.map(s => s.title + ' ' + s.desc).join(' ');
  for (const field of ['economy', 'entertainment', 'society']) {
    if (KEYWORDS[field].some(kw => text.includes(kw))) return field;
  }
  const sorted = [...ev.sources].sort((a, b) => b.channelWeight - a.channelWeight);
  return sorted[0]?.channelField || 'society';
}

// ============================================================
// 模块 4: 评分模型
// ============================================================
function hotScore(ev) {
  let maxH = 0;
  for (const s of ev.sources) {
    const rankNorm = 1 - (s.rank - 1) / FETCH_TOP;
    const h = rankNorm * s.channelWeight;
    if (h > maxH) maxH = h;
  }
  return Math.min(1, maxH);
}

function freshnessScore(ev) {
  const deltaHours = (Date.now() - ev.minTime) / 3600000;
  return Math.exp(-deltaHours / FRESH_TAU_HOURS);
}

function crossSourceScore(ev, maxN) {
  const n = new Set(ev.sources.map(s => s.channel)).size;
  if (maxN <= 1) return n >= 1 ? 1 : 0;
  return Math.min(1, Math.log2(1 + n) / Math.log2(1 + maxN));
}

function totalScore(H, T, M) {
  return SCORE_WEIGHTS.H * H + SCORE_WEIGHTS.T * T + SCORE_WEIGHTS.M * M;
}

// ============================================================
// 模块 5: 多样性配额
// ============================================================
function applyQuota(scored, limit) {
  const pool = [...scored].sort((a, b) => b.totalScore - a.totalScore).slice(0, TOP_N);
  const result = [];
  const used = new Set();
  const counts = { society: 0, economy: 0, entertainment: 0 };

  for (const field of ['society', 'economy', 'entertainment']) {
    for (const ev of pool) {
      if (counts[field] >= QUOTA[field]) break;
      if (used.has(ev.id)) continue;
      if (ev.category === field) {
        result.push(ev); used.add(ev.id); counts[field]++;
      }
    }
  }

  for (const ev of pool) {
    if (result.length >= limit) break;
    if (!used.has(ev.id)) {
      result.push(ev); used.add(ev.id);
      counts[ev.category] = (counts[ev.category] || 0) + 1;
    }
  }

  console.log(`[配额] 最终 ${result.length} 条: 社会 ${counts.society}, 经济 ${counts.economy}, 娱乐 ${counts.entertainment}`);
  return result;
}

// ============================================================
// 模块 6: 输出
// ============================================================
function buildFeed(events) {
  const maxN = Math.max(1, ...events.map(ev => new Set(ev.sources.map(s => s.channel)).size));

  const scored = events.map(ev => {
    const H = hotScore(ev);
    const T = freshnessScore(ev);
    const M = crossSourceScore(ev, maxN);
    const S = totalScore(H, T, M);
    const category = classify(ev);
    return {
      id: 'evt-' + ev.normKey.slice(0, 12).replace(/[^a-z0-9]/gi, '').padEnd(8, '0'),
      title: ev.sources[0].title,
      category,
      hotScore: +H.toFixed(4),
      freshness: +T.toFixed(4),
      crossSource: +M.toFixed(4),
      totalScore: +S.toFixed(4),
      sources: ev.sources
        .sort((a, b) => b.channelWeight - a.channelWeight)
        .map(s => ({ channel: s.channel, rank: s.rank, hot: s.hot, url: s.url })),
      summary: ev.sources[0].desc || '',
      url: ev.sources[0].url,
    };
  });

  const feed = applyQuota(scored, FEED_LIMIT);

  return {
    generatedAt: new Date().toISOString(),
    fields: FIELD_LABELS,
    feed,
  };
}

// ============================================================
// 主流程
// ============================================================
async function main() {
  console.log('=== Finnly 热点聚合 开始 ===');
  console.log(`渠道: ${CHANNELS.map(c => c.name).join(', ')}`);

  const raw = await fetchAllChannels();
  if (raw.length === 0) {
    throw new Error('所有渠道扒取失败, 无数据');
  }

  const events = clusterEvents(raw);
  const output = buildFeed(events);

  const outPath = resolve(__dirname, '..', 'docs', 'feed.json');
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, JSON.stringify(output, null, 2), 'utf-8');
  console.log(`[输出] 已写入 ${outPath} (${output.feed.length} 条)`);

  console.log('=== 完成 ===');
}

main().catch(err => {
  console.error('失败:', err);
  process.exit(1);
});
