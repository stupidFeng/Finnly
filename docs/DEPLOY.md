# 服务器部署手册

目标：把 `ryder-buddy-server`（FastAPI + Postgres 16，Docker Compose 部署）跑在阿里云轻量服务器（2核2G，4M 带宽，Ubuntu 24.04 + Docker 镜像）上。

## 阶段 0：部署前置（本地完成）

- [ ] 服务端代码推送到 GitHub main 分支（服务器要从 GitHub 拉代码）
- [ ] 准备好 `.env` 生产密钥（见 `ryder-buddy-server/.env.production`，本地保存，绝不入库）

## 阶段 1：阿里云控制台（网页操作）

1. **记下公网 IP**：控制台 → 轻量应用服务器 → 概览页
2. **防火墙放行端口**：服务器详情 → 防火墙 → 添加规则
   - TCP 22（SSH，默认已开）
   - TCP 8000（API 服务）
3. **root 密码**：如果购买时没设置，点「重置密码」后重启生效

## 阶段 2：SSH 连上服务器（本机 PowerShell）

```powershell
ssh root@你的公网IP
```

## 阶段 3：服务器上部署（SSH 内照抄）

```bash
# 1. 装基础工具（Docker 镜像自带 Docker，不用装）
apt update && apt install -y git

# 2. 确认 Docker 可用
docker --version && docker compose version

# 3. 拉代码
git clone https://github.com/stupidFeng/Finnly.git
cd Finnly/ryder-buddy-server

# 4. 写生产配置：把本地 .env.production 的内容粘贴进来
#    nano 里 Ctrl+O 保存，Ctrl+X 退出
nano .env
chmod 600 .env

# 5. 构建并启动（首次约 3-5 分钟）
docker compose up -d --build

# 6. 验证：两个容器都是 running / healthy
docker compose ps

# 7. 本机自测
curl http://localhost:8000/health
# 期望输出：{"ok":true}
```

> 若 GitHub 访问慢/失败（大陆机器常见）：改用
> `git clone https://ghproxy.cn/https://github.com/stupidFeng/Finnly.git`

## 阶段 4：外网验证 + 配置

1. 本机浏览器访问 `http://公网IP:8000/health`，看到 `{"ok":true}` 即上线
2. 用 papa 账号登录 App 管理界面，配置 LLM / ASR / TTS（base_url + api_key + 模型名）
3. App 设置里把服务端地址改为 `http://公网IP:8000`
4. 手机关掉 WiFi 用流量，实测一次完整语音对话

## 阶段 5：日常运维

```bash
# 更新代码后重新部署
cd ~/Finnly/ryder-buddy-server && git pull
docker compose up -d --build

# 看实时日志
docker compose logs -f server

# 手动备份数据库
docker exec ryder-db pg_dump -U ryder ryder > backup-$(date +%F).sql
```

建议在服务器上加个每周自动备份（cron）：

```bash
crontab -e
# 加入这行（每周日 4 点备份，保留在 ~/backups）：
0 4 * * 0 mkdir -p ~/backups && docker exec ryder-db pg_dump -U ryder ryder > ~/backups/ryder-$(date +\%F).sql
```

## 阶段 6（后续，不急）：域名 + HTTPS

买域名 → 阿里云 ICP 备案（2-3 周）→ Caddy 反代自动 HTTPS → 防火墙关 8000 只留 443。

## 安全红线

- `.env`（含 JWT_SECRET / DB_PASSWORD / 管理员密码）永不提交 Git、不发聊天
- 只开 22 / 8000 两个端口
- `FATHER_PASSWORD` 首次登录后可改，改完 `docker compose up -d` 重启生效
