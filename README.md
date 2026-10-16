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

### 可复现科研 Data Agent

AI 助手可对权限范围内的同名材料性能或测试测量值进行受限分析。例如，可以问“按材料比较 tensile_strength，并检查异常值”或“按温度汇总 ionic_conductivity”。后端不会让模型直接执行 SQL：它使用固定的 SQLAlchemy 查询计划，并输出可追溯的记录引用、数据范围、单位换算、缺失值提示、IQR 异常值检查和图表数据。对不能可靠换算的单位、不同测试方法或不同实验条件，系统会分开统计并明确提示比较边界。

### 科研文档 RAG（全文检索 v1）

上传 `.txt`、`.md`、`.csv`、`.json`、`.xml`、`.cif`、`.docx`、`.xlsx/.xlsm` 或可解析 PDF 后，系统会在保留原附件的同时抽取文本并生成带出处的检索片段。AI 可回答“我的附件里离子电导率是多少？”这类问题；结果卡片会给出原文件下载链接和 PDF 页码或 Excel 工作表。检索时会重新检查文件的材料/项目父级权限，因此私有项目附件不会因已建立索引而被其他用户召回。

当前 RAG v1 采用受权限约束的全文 BM25 召回，**不宣称已启用向量语义检索**。扫描型 PDF 和图片还需要 OCR；生产环境若要接入嵌入模型或 pgvector，应先建立中文/英文材料问答、出处准确率与跨项目越权的评测集。已有附件可由有编辑权限的用户调用 `POST /api/v1/files/{file_id}/knowledge/reindex` 重建索引。

首次升级后，如要为历史附件批量创建索引，可在 `backend` 目录执行 `python -m scripts.reindex_research_knowledge`；修改分块配置或解析器后执行 `python -m scripts.reindex_research_knowledge --all`。

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
| 分析湖仓 | Apache Spark 4.1 + Apache Iceberg 1.12 |

## Spark / Iceberg 数据工程湖仓

`lakehouse/` 提供独立的数据工程演示环境：通过 Spark JDBC 将 PostgreSQL 增量同步到
Iceberg bronze 层，再生成材料性能与仪器测量的 silver 宽表、gold 项目指标和数据
质量记录。它包含 Spark Master/Worker、History Server、watermark、幂等 MERGE、
数据质量门禁和无需业务数据库的确定性 demo 数据。

```powershell
.\lakehouse\run_pipeline.ps1 -Source demo
```

完整架构、真实 PostgreSQL 同步方式和简历表达见
[`lakehouse/README.md`](lakehouse/README.md)。

## Phase 1 已实现功能

- [x] 用户认证 (JWT + RBAC：admin / researcher / viewer)
- [x] 材料管理 (CRUD + 搜索 + 类型筛选 + 分页)
- [x] 属性管理 (通用属性 + 类型专用表)
- [x] 晶体结构管理 (手动创建 + CIF 文件导入解析)
- [x] 文件上传/下载
- [x] 审计日志
- [x] 一键启动脚本
