# Materials DMP — 材料科学数据管理平台

## Vercel 部署

本仓库已支持 Vite + FastAPI 单项目部署，配置步骤见 [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md)。

## 内网生产部署

本仓库提供 PostgreSQL、FastAPI、Nginx 前端的生产 Compose 配置，并支持 OpenAI 兼容的本地大模型。详见 [INTRANET_DEPLOY.md](INTRANET_DEPLOY.md)。

通用的材料科学数据管理平台，管理材料配方、晶体结构、性能参数、实验流程和表征数据的全生命周期。

## 一键启动

**只需 Python 3.10+ 和 Node.js 已安装即可，无需 Docker、无需配置数据库！**

```batch
start.bat
```

脚本自动完成：创建虚拟环境 → 安装依赖 → 初始化 SQLite 数据库 → 创建演示数据 → 同时启动前后端

启动后访问：
- **前端界面**: http://localhost:5173
- **API 文档**: http://localhost:8000/api/v1/docs
- **默认账号**: `admin` / `admin123`

## 手动启动

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端（新终端）
cd frontend
npm install
npm run dev
```

数据库默认使用 **SQLite**（零配置，文件存储在 `backend/materials_dmp.db`）。
如需切换 PostgreSQL，设置环境变量 `USE_SQLITE=false` 并配置数据库连接。

右上角的 **AI 助手** 支持材料知识问答、权限内数据查询，以及材料和项目的新增、修改、删除。写操作只会先生成预览，必须由用户确认后才会落库。AI 修改或删除数据时，服务器会在执行前保存临时快照；操作者可在 AI 助手的“可回退版本”中恢复，默认保留 24 小时且每份快照只能恢复一次。备份保留时间可通过 `ASSISTANT_BACKUP_RETENTION_HOURS` 调整。

启用前请复制 `backend/.env.example` 为 `backend/.env`，并填写：

```env
LLM_BASE_URL=https://你的模型服务地址/v1
LLM_MODEL=支持工具调用的模型名称
LLM_API_KEY=模型服务_API_Key
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| 前端 | React 18 + TypeScript + Ant Design 5 |
| 构建 | Vite 5 |
| 状态管理 | TanStack React Query + Zustand |

## Phase 1 已实现功能

- [x] 用户认证 (JWT + RBAC：admin / researcher / viewer)
- [x] 材料管理 (CRUD + 搜索 + 类型筛选 + 分页)
- [x] 属性管理 (通用属性 + 类型专用表)
- [x] 晶体结构管理 (手动创建 + CIF 文件导入解析)
- [x] 文件上传/下载
- [x] 审计日志
- [x] 一键启动脚本
