# Finnly 热点聚合功能 - 规划与进度

> 本文档为项目持久记忆，防止上下文压缩丢失。每完成一项工作项须更新本文档状态。
> 最后更新：2026-07-13

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
| 后端部署 | GitHub Actions（cron 每2h + workflow_dispatch），零服务器 |
| 数据发布 | jsDelivr CDN（`cdn.jsdelivr.net/gh/stupidFeng/Finnly@main/`） |
| 仓库可见性 | Public（私有仓库无法用免费 Pages，且 jsDelivr 不支持私有） |
| 数据源接入 | 直接调用各平台原生 API（放弃 DailyHotApi 第三方聚合，公共实例不稳定） |
| APP 网络层 | Retrofit + jsDelivr，无需 token 鉴权（公开仓库） |

## 三、系统架构

```
┌──── GitHub 仓库 (stupidFeng/Finnly, public) ──┐
│  .github/workflows/hot-feed.yml               │
│    ↑ cron 每2h + workflow_dispatch             │
│    │ 运行 Node 脚本                            │
│    ▼                                           │
│  scripts/fetch-and-score.mjs                  │
│    扒取 → 去重 → 分类 → 评分 → 配额            │
│    │                                           │
│    ▼ 输出                                      │
│  docs/feed.json (提交回仓库 main 分支)         │
│    │                                           │
│    ▼ jsDelivr CDN 自动同步                     │
│  https://cdn.jsdelivr.net/gh/stupidFeng/       │
│    Finnly@main/docs/feed.json                 │
│    (国内可访问, HTTPS + CDN 加速)              │
└────────────────────────────────────────────────┘
              ▲ HTTPS GET (无需 token)
       ┌──────┴──────┐
       │ Android APP │ Retrofit 拉取
       └─────────────┘
```

## 四、数据源与领域映射（MVP 实际接入）

| 渠道 | 平台原生 API | 默认领域 | 权重 |
|---|---|---|---|
| `baidu`    | 百度热搜 topboards.baidu.com | society | 0.80 |
| `toutiao`  | 头条热榜 www.toutiao.com/hot-event/hot-board | society | 0.85 |
| `zhihu`    | 知乎热榜 www.zhihu.com/api/v3/feed/topstory/hot-list | society | 0.75 |
| `36kr`     | 36氪 36kr.com/hot-list/catalog | economy | 0.90 |
| `thepaper` | 澎湃热榜 cache.thepaper.cn/search | society | 0.85 |

> 放弃的源：微博/抖音/B站（公共聚合 API 不稳定或需登录）。娱乐源暂缺，导致 `entertainment` 分类为空——Phase 2 待补。

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

## 九、后端部署（GitHub Actions + jsDelivr CDN）

- **扒取+评分脚本**：`scripts/fetch-and-score.mjs`（Node ESM，Node 18+ 内置 fetch，零三方依赖）
- **定时触发**：`schedule: cron: "0 */2 * * *"` + `workflow_dispatch`
- **数据存储**：feed.json 提交回仓库 `docs/` 目录；历史快照可选归档到 `docs/archive/YYYY-MM-DD.json`
- **发布**：直接通过 jsDelivr CDN 访问 main 分支文件，无需 Pages 配置
- **访问**：`https://cdn.jsdelivr.net/gh/stupidFeng/Finnly@main/docs/feed.json`（HTTPS + 国内可访问）
- **为何不用 Pages**：私有仓库免费层不支持 Pages；改 public 后又因 `raw.githubusercontent.com` 国内 DNS 污染（EAI_NODATA），故走 jsDelivr
- **免费额度**：Actions 免费层 2000 分钟/月，每 2h 跑约 1~2 分钟，月耗约 360~720 分钟，够用；jsDelivr 公开仓库免费且无限量

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
| 1 | ✅ 完成 | 后端脚本骨架 | `scripts/fetch-and-score.mjs`（ESM，Node 18+ 内置 fetch，零三方依赖） |
| 2 | ✅ 完成 | 扒取层 | 并发拉 5 源（百度/头条/知乎/36氪/澎湃），平台原生 API 适配 |
| 3 | ✅ 完成 | 去重聚类 | 标题归一化 + Jaccard ≥0.6 聚合，合并多源印记 |
| 4 | ✅ 完成 | 分类模块 | 渠道默认领域映射 + 关键词词典修正 |
| 5 | ✅ 完成 | 评分模型 | 热度 H × 时效 T × 多源印证 M，加权总分 |
| 6 | ✅ 完成 | 多样性配额 | 贪心填充，社会/经济/娱乐配额 |
| 7 | ✅ 完成 | 输出 feed.json | `docs/feed.json`，10 条热点 |

### 第二块：CI/CD 与发布

| # | 状态 | 工作项 | 说明 |
|---|---|---|---|
| 8 | ✅ 完成 | GitHub Actions workflow | `.github/workflows/hot-feed.yml`，cron 每2h + workflow_dispatch |
| 9 | ✅ 完成 | 数据发布（改用 jsDelivr） | 原 Pages 方案废弃；改 jsDelivr CDN，已验证 200 OK |

### 第三块：Android APP 端

| # | 状态 | 工作项 | 说明 |
|---|---|---|---|
| 10 | ✅ 完成 | APP 数据层 | Retrofit + Room + Moshi，`NetworkClient.kt` 走 jsDelivr |
| 11 | ✅ 完成 | APP UI | MaterialToolbar + TabLayout + SwipeRefresh + RecyclerView 卡片 |
| 12 | ✅ 完成 | 端到端联调 | Actions 生成 → jsDelivr 发布 → APP 拉取，闭环跑通 |
| 13 | ✅ 完成 | CI 集成 | Android CI 保持绿，hot-feed workflow 已就位 |

### Phase 2 待办（未来增强）

| # | 状态 | 工作项 | 说明 |
|---|---|---|---|
| 14 | ⬜ 待办 | 补充娱乐源 | 抖音/B站/豆瓣电影等，当前 `entertainment` 分类为空 |
| 15 | ⬜ 待办 | 历史归档 | `docs/archive/YYYY-MM-DD.json` 每日快照 |
| 16 | ⬜ 待办 | 每日推送 | APP 端 WorkManager 定时通知 |

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
- 2026-07-12：完成 Android 项目初始化与 CI（launcher 图标修复）；后端脚本改用各平台原生 API（放弃 DailyHotApi 公共实例）
- 2026-07-12：配置 PAT（FINNLY_GITHUB_TOKEN Secret），CI 注入 token 至 local.properties；Room 崩溃修复（补 KSP 注解处理器 `com.google.devtools.ksp` 1.9.22-1.0.17 + `ksp("androidx.room:room-compiler:2.6.1")`）
- 2026-07-12：merge 冲突误用 `--ours` 导致 MainActivity/activity_main 回退为 Hello 版本，已重写恢复
- 2026-07-13：私有仓库无法用免费 Pages → 用户选择"仓库改 public + jsDelivr"
- 2026-07-13：APP 报 `EAI_NODATA`（raw.githubusercontent.com 国内 DNS 污染）→ `NetworkClient.kt` 改 `https://cdn.jsdelivr.net/gh/stupidFeng/Finnly@main/`
- 2026-07-13：jsDelivr 404（feed.json 与 scripts 在 merge 中丢失）→ 重建 `scripts/fetch-and-score.mjs` + `.github/workflows/hot-feed.yml` + 本地跑通生成 10 条；推送 main，jsDelivr 已返回 200
- 2026-07-13：13 个工作项全部完成，端到端闭环跑通。Phase 2 待办已列出（补充娱乐源/历史归档/推送）
- 2026-07-13：修复 APK 签名不一致问题 — 新增 `app/finnly.keystore`（项目级固定 keystore），`build.gradle.kts` 配 `signingConfigs.shared`，debug/release 共用。`.gitignore` 加例外 `!app/finnly.keystore`。此后新 APK 可直接覆盖安装，无需卸载旧版本
