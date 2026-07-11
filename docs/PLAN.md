# Finnly 热点聚合功能 - 规划与进度

> 本文档为项目持久记忆，防止上下文压缩丢失。每完成一项工作项须更新本文档状态。
> 最后更新：2026-07-11

---

## 一、功能目标

每日从多渠道扒取热点新闻，按社会/经济/娱乐分类，用统一评分排优先级，并通过"多样性配额"防止信息茧房——保证用户每天都能看到跨领域的热点，而非被单一领域或单一平台霸屏。

## 二、关键决策（已确认）

| 决策点 | 选择 |
|---|---|
| 数据架构 | 云端后端扒取+评分，APP 只展示 |
| 防茧房策略 | 多样性配额（每领域最低曝光条数） |
| 分类方式 | 渠道映射 + 关键词词典修正 |
| 评分维度 | 热度 × 时效 × 多源印证（三维归一化加权） |
| 部署方案 | GitHub Actions 生成 feed.json, APP 直读 raw.githubusercontent.com (私有仓库, 需 token) |
| 仓库可见性 | 保持私有 (放弃 Pages, 因私有仓库 Pages 需 Enterprise 付费) |
| 沙箱 GitHub 权限 | 用户提供 PAT (repo + workflow scopes), 用于触发 workflow / 读 API |

## 三、系统架构

```
┌──── GitHub 私有仓库 (stupidFeng/Finnly) ────┐
│  .github/workflows/hot-feed.yml              │
│    ↑ cron 每2h + workflow_dispatch            │
│    │ 运行 Node 脚本                           │
│    ▼                                          │
│  scripts/fetch-and-score.mjs                 │
│    扒取 → 去重 → 分类 → 评分 → 配额           │
│    │                                          │
│    ▼ 输出并提交                               │
│  docs/feed.json (git commit 回 main)         │
└──────────────────────────────────────────────┘
              ▲ HTTPS GET (带 Authorization: token)
              │ https://raw.githubusercontent.com/stupidFeng/Finnly/main/docs/feed.json
       ┌──────┴──────┐
       │ Android APP │ Retrofit 拉取, 本地 Room 缓存
       └─────────────┘
```

> 注: 私有仓库的 raw 地址需要带 token 才能访问。
> APP 端通过 BuildConfig 注入只读 token (fine-grained PAT, 仅读 contents)。
> 沙箱侧用经典 PAT (repo + workflow scopes) 触发 workflow 和调 API。

## 四、数据源与领域映射

| 领域 | 主渠道（DailyHotApi 调用名） | 渠道默认权重 |
|---|---|---|
| 社会 | 澎湃 `thepaper`、微博 `weibo`、百度 `baidu`、头条 `toutiao`、腾讯新闻 `qq-news` | 0.9 / 0.7 / 0.8 / 0.8 / 0.8 |
| 经济 | 36氪 `36kr`、虎嗅 `huxiu`、头条 `toutiao` | 0.9 / 0.85 / 0.7 |
| 娱乐 | 抖音 `douyin`、B站 `bilibili`、豆瓣电影 `douban-movie`、微博 `weibo` | 0.8 / 0.7 / 0.75 / 0.6 |

> MVP 先用 5 源：微博 `weibo`、百度 `baidu`、抖音 `douyin`、36氪 `36kr`、澎湃 `thepaper`

## 五、数据流水线

`扒取 → 去重聚类 → 分类 → 评分 → 多样性配额 → 存库 → API`

1. **扒取**：定时拉取各渠道 Top 条目（统一 JSON：title/desc/hot/url/time）
2. **去重聚类**：标题归一化（去 emoji/标点/空格）后用 Jaccard 相似度 ≥0.6 聚为同一事件，合并多源印记，保留最高热度
3. **分类**：渠道默认领域 + 关键词词典修正
4. **评分**：三维归一化加权
5. **配额**：多样性配额约束
6. **输出**：feed.json 提交回仓库
7. **发布**：GitHub Pages 自动发布

## 六、评分模型

三维归一化加权，均在 [0,1]：

| 维度 | 公式 | 说明 |
|---|---|---|
| 热度 H | 渠道内按位次/hot 值 min-max 归一，再乘渠道权重 w | 跨源可比 |
| 时效 T | `T = exp(-Δt / τ)`，τ=6h | 6h 后衰减明显 |
| 多源印证 M | `M = min(1, log2(1+N)/log2(1+N_max))`，N=独立渠道数 | 多源印证的事件更高 |

**总分** `S = 0.4·H + 0.3·T + 0.3·M`（权重可调）

排序按 S 降序。

## 七、多样性配额（防茧房）

评分排序后，对首页 Top-15 做配额约束：
- 社会 ≥ 4 条、经济 ≥ 4 条、娱乐 ≥ 4 条
- 余 3 条留给全场最高分（不论领域）

算法：先按 S 取 Top-N 候选池（如 Top-40）→ 贪心填充各领域最低配额 → 剩余位置按 S 补满。

## 八、feed.json 结构

```json
{
  "generatedAt": "2026-07-11T03:00:00Z",
  "feed": [
    {
      "id": "evt-xxxx",
      "title": "...",
      "category": "society",
      "hotScore": 0.87,
      "freshness": 0.92,
      "crossSource": 0.6,
      "totalScore": 0.81,
      "sources": [
        {"channel":"weibo","rank":3,"hot":1234567,"url":"..."}
      ],
      "summary": "...",
      "url": "..."
    }
  ]
}
```

## 九、后端部署（GitHub Actions + raw 直读）

- **扒取+评分脚本**：`scripts/fetch-and-score.mjs`（Node ESM，零依赖，用 Node18+ 内置 fetch）
- **定时触发**：`schedule: cron: "0 */2 * * *"` + `workflow_dispatch`
- **数据存储**：feed.json 提交回仓库 `docs/` 目录；历史快照可选归档到 `docs/archive/YYYY-MM-DD.json`
- **发布方式**：不部署到 Pages（私有仓库需 Enterprise），改为 APP 直读 raw 地址
- **访问**：`https://raw.githubusercontent.com/stupidFeng/Finnly/main/docs/feed.json`（需 Authorization header 带 token）
- **免费额度**：Actions 免费层 2000 分钟/月（私有仓库），每 2h 跑约 1~2 分钟，月耗约 360~720 分钟，够用
- **deploy-pages.yml 已弃用**：保留文件但不再需要, 后续可删除

## 十、APP 端职责

- 栈：Kotlin + MVVM + Retrofit + Room + ViewBinding（当前工程已开启 viewBinding）
- 界面：首页热点流（卡片：标题/领域标签/热度/多源数）+ 领域 Tab（全部/社会/经济/娱乐）+ 下拉刷新 + 点击跳转原链接
- 本地 Room 缓存上次结果，离线可看

## 十一、实施分期

- **Phase 1（MVP）**：后端扒 5 源 → 渠道映射分类 → 热度+时效评分 → API → APP 首页流跑通
- **Phase 2**：多源去重 + 多源印证分 + 多样性配额 + 领域 Tab
- **Phase 3**：逆偏好加权(可选)、历史回顾、每日推送

---

## 工作项进度

### 第一块：后端数据生成（脚本）

| # | 状态 | 工作项 | 说明 |
|---|---|---|---|
| 1 | ⬜ 待办 | 后端脚本骨架 | 搭 `scripts/fetch-and-score.mjs`（ESM），定目录结构、依赖、入口 |
| 2 | ⬜ 待办 | 扒取层 | 并发拉 5 源（微博/百度/抖音/36氪/澎湃），统一成 `{title,desc,hot,url,time,channel}` |
| 3 | ⬜ 待办 | 去重聚类 | 标题归一化 + Jaccard ≥0.6 聚合，合并多源印记 |
| 4 | ⬜ 待办 | 分类模块 | 渠道默认领域映射 + 关键词词典修正（社会/经济/娱乐） |
| 5 | ⬜ 待办 | 评分模型 | 热度 H × 时效 T × 多源印证 M，加权总分 |
| 6 | ⬜ 待办 | 多样性配额 | Top-15 配额（社会≥4/经济≥4/娱乐≥4，余3按总分），贪心填充 |
| 7 | ⬜ 待办 | 输出 feed.json | 生成结构化 JSON（generatedAt + feed 数组 + 各分项分） |

### 第二块：CI/CD 与发布

| # | 状态 | 工作项 | 说明 |
|---|---|---|---|
| 8 | ⬜ 待办 | GitHub Actions workflow | 定时 cron 每2h + workflow_dispatch，运行脚本并提交回仓库 |
| 9 | ⬜ 待办 | GitHub Pages 配置 | docs/ 目录发布，验证 feed.json HTTPS+CDN 可访问 |

### 第三块：Android APP 端

| # | 状态 | 工作项 | 说明 |
|---|---|---|---|
| 10 | ⬜ 待办 | APP 数据层 | Retrofit GET /Finnly/feed.json + Room 缓存 + 数据模型 |
| 11 | ⬜ 待办 | APP UI | 首页热点流卡片 + 领域Tab + 下拉刷新 + 点击跳转 |
| 12 | ⬜ 待办 | 端到端联调 | Actions 生成 → Pages 发布 → APP 拉取展示，跑通闭环 |
| 13 | ⬜ 待办 | CI 集成 | 现有 Android CI 保持绿，新增数据生成 workflow 验证脚本可跑 |

### 推进顺序

```
第一块(1→7)  脚本写完，本地能生成 feed.json
   ↓
第二块(8→9)  workflow 自动跑，Pages 发布成功
   ↓
第三块(10→12) APP 拉到数据并展示
   ↓
(13) CI 守护，保持两条流水线都绿
```

---

## 变更记录

- 2026-07-11：初始规划，13 个工作项全部待办
- 2026-07-11：第一块(#1~#7)完成。数据源调整为百度/头条/知乎/36氪/澎湃(原生接口),放弃第三方聚合 API。脚本本地验证通过。
- 2026-07-11：第二块(#8)完成, #9 待用户开启 Pages。hot-feed.yml + deploy-pages.yml 就位。
- 2026-07-11：第三块(#10/#11/#13)完成, #12 待联调。APP 编译通过(8c49e19)。
- 2026-07-11：方案调整。私有仓库 Pages 需 Enterprise 付费, 放弃 Pages。改为 APP 直读 raw.githubusercontent.com (带 token)。用户选择给沙箱配 PAT(repo+workflow scopes)。
- 2026-07-11：PAT 配置完成。git remote 更新为经典 PAT; APP 通过 BuildConfig 注入 fine-grained PAT(只读 contents)。NetworkClient 添加 Authorization header。
- 2026-07-11：APP 编译通过 (commit 3b98a39)。端到端闭环完成: hot-feed workflow 自动生成 feed.json → APP 通过 raw URL + token 拉取。
