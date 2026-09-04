# Aeon

个人管家 · 手机控制中心

在线地址：https://aeon.org.cn（服务器：腾讯云首尔，Caddy 自动 HTTPS）

## 功能模块（v3）

| 模块 | 说明 |
|------|------|
| 📅 日程 schedule | 周期性任务 + cron 表达式 |
| 📒 记账 ledger | 收支流水 + 分类 |
| ✅ 习惯 habits | 勾选/计数/数值三种打卡 |
| 🌟 愿望 wishlist | 想要/需要/观望分级 |
| 📚 书架 books | txt/epub 上传解析章节 + 阅读进度 |
| 🎬 书影音 media | 想看/进行中/看完 |
| 💰 余额 balance | DeepSeek 等模型余额查询 |
| 📰 简报 briefing | 每日早报内容 |
| 📁 文件 files | 服务器目录浏览 |
| 🧠 Wiki | 知识图谱可视化 |
| 🏠 生活 life | 生活记录 |
| 📥 导入 import_data | 数据导入 |

## 技术栈

- 后端：Python FastAPI + SQLite(SQLAlchemy) + JWT + APScheduler
- 前端：HTML/CSS/JS → Capacitor 打包 APK（server.url → https://aeon.org.cn）
- 部署：腾讯云首尔 + Caddy 反代 127.0.0.1:8902（systemd: aeon.service）

## 目录结构

```
aeon/
├── backend/            # FastAPI 后端（v3 架构，12 路由模块）
│   ├── main.py         # 入口：挂载全部路由 + 前端页面服务
│   ├── db.py           # SQLAlchemy 引擎（data/aeon.db 项目自包含）
│   ├── models/         # 8 张业务表（带 user_id 多用户预留）
│   ├── services/       # auth.py：JWT 签发 + 登录注册
│   └── routes/         # ledger/habits/schedule/wishes/media/books/balance/briefing/files/wiki/life/import_data
├── frontend/           # 13 个页面 + common 组件 + 主题 + 资产
├── data/               # aeon.db（运行时数据，git 忽略）+ books/ 书籍
├── assets/             # 设计素材源文件（纹身素材 + 月相）
├── backups/            # 数据库/代码备份（git 忽略）
├── tutor*.py           # Aeon Tutor 飞书高数家教（独立 WebSocket 服务）
└── .github/workflows/  # push 自动构建 APK
```

## 部署

```bash
# systemd 服务（后端）
sudo systemctl enable --now aeon      # uvicorn main:app @ 127.0.0.1:8902

# Caddy（/etc/caddy/Caddyfile）：aeon.org.cn 全站反代 8902
# /downloads/* 目录提供打包文件下载（/home/ubuntu/aeon-downloads）
```

环境变量（/home/ubuntu/aeon/.env）：`AEON_SECRET`（JWT 密钥）、`DEEPSEEK_API_KEY`、`TUTOR_APP_ID`、`TUTOR_APP_SECRET`

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/login | 登录/注册（管理员 Y 免邀请码） |
| GET | /api/me | 当前用户 |
| GET | /health | 健康检查 |
| WS | /ws | WebSocket（tutor） |

业务 API 见各 route：/api/ledger /api/habits /api/schedule /api/wishes /api/media /api/books /api/balance /api/briefing /api/files /api/wiki /api/life

## 邀请码

当前有效邀请码：`AEON-2026` `ZERO-DEGREE` `PHILOSOPHY-144`

管理员账号 `Y` 无需邀请码。
