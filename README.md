# Aeon

个人管家 · 手机控制中心

## 功能

- 📅 日程管理 — 周期性任务 + cron 表达式
- ✅ 待办推送 — 微信/飞书双端提醒
- 📁 文件浏览 — 服务器目录实时查看
- 🧠 Wiki 知识图谱 — 144 页可视化
- 💬 Agent 对话 — 内置 Hermes 聊天
- 📰 每日早报 — 苏菲的世界连载 + 哲学名言
- 🌙 月相指示 — 右上角月相每日自动切换

## 技术栈

- 后端：Python FastAPI + SQLite + APScheduler + JWT
- 前端：HTML/CSS/JS → Capacitor 打包 APK
- 部署：阿里云 ECS 香港

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/login | 登录（管理员免邀请码，普通用户需邀请码） |
| GET | /api/me | 当前用户信息 |
| GET | /api/todos | 待办列表 |
| POST | /api/todos | 新建待办 |
| PUT | /api/todos/:id/done | 标记完成 |
| DELETE | /api/todos/:id | 删除待办 |
| GET | /api/schedules | 日程列表 |
| POST | /api/schedules | 新建日程 |
| PUT | /api/schedules/:id/toggle | 启用/停用日程 |
| WS | /ws | WebSocket 实时通信 |

## 邀请码

当前有效邀请码：`AEON-2026` `ZERO-DEGREE` `PHILOSOPHY-144`

管理员账号 `Y` 无需邀请码。
