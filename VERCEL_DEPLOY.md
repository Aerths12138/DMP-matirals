# Materials DMP 部署到 Vercel

本仓库已经适配为一个 Vercel 项目：

- `frontend/` 构建为 Vite 静态站点。
- `api/index.py` 将 `backend/app/main.py` 暴露为一个 FastAPI Vercel Function。
- 浏览器继续使用同源 `/api/v1`，不需要配置单独的后端域名。
- 本地开发仍然使用 SQLite 和本地附件目录；Vercel 使用外部 PostgreSQL 和私有 Vercel Blob。

## 1. 准备代码仓库

把整个仓库推送到 GitHub、GitLab 或 Bitbucket。必须保留仓库根目录中的：

- `vercel.json`
- `requirements.txt`
- `.python-version`
- `api/`
- `backend/`
- `frontend/`

`.gitignore` 和 `.vercelignore` 已阻止本机数据库、虚拟环境、上传附件和 `.env` 文件进入远程仓库或部署包。

## 2. 在 Vercel 创建项目和存储

1. 在 Vercel 选择 **Add New → Project**，导入代码仓库。
2. **Root Directory 保持仓库根目录**，不要选择 `frontend` 或 `backend`。
3. 在项目的 **Storage** 页面连接一个 PostgreSQL 数据库。可以从 Marketplace 选择 Neon 等服务。
4. 在 **Storage** 页面新建一个 **Private Blob**，并连接到当前项目。

连接 Blob 后，Vercel 会自动注入 `BLOB_READ_WRITE_TOKEN`；新版本也可以使用 Vercel OIDC 认证。

## 3. 配置环境变量

在项目 **Settings → Environment Variables** 中添加：

| 变量 | 必需 | 说明 |
|---|---:|---|
| `DATABASE_URL` | 是 | PostgreSQL 连接地址；建议使用数据库服务提供的 pooled URL |
| `SECRET_KEY` | 是 | JWT 签名密钥，必须是随机长字符串 |
| `DEEPSEEK_API_KEY` | AI 助手必需 | DeepSeek API 密钥，仅配置在后端环境变量中 |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-v4-flash` |
| `ASSISTANT_BACKUP_RETENTION_HOURS` | 否 | AI 修改/删除操作的临时备份保留小时数，默认 `24` |
| `BOOTSTRAP_ADMIN_PASSWORD` | 首次部署 | 初始管理员密码，至少 12 个字符 |
| `BOOTSTRAP_ADMIN_USERNAME` | 否 | 初始管理员用户名，默认 `admin` |
| `BOOTSTRAP_ADMIN_EMAIL` | 否 | 初始管理员邮箱，默认 `admin@materials-dmp.local` |
| `STORAGE_BACKEND` | 否 | Vercel 会自动切换为 `vercel_blob`，也可以显式填写 |
| `VERCEL_SUPPORT_LARGE_FUNCTIONS` | 按需 | 若 `pymatgen` 导致 Function 包超限，设置为 `1` 后重新部署 |

如果数据库集成创建的是 `POSTGRES_URL` 等其他名称，请在 Vercel 中另外创建 `DATABASE_URL`，值使用同一个连接地址。

可以在本机生成 `SECRET_KEY`：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

建议为 Production 和 Preview 使用不同的数据库，避免预览分支的自动迁移影响生产数据。

## 4. 部署

点击 **Deploy**。仓库中的配置会自动执行：

1. 安装前端和 Python 依赖。
2. 对 PostgreSQL 执行 Alembic 数据库迁移。
3. 初始化权限和 `admin / researcher / viewer` 角色。
4. 在数据库为空时创建初始管理员。
5. 构建 Vite 前端，并发布 FastAPI Function。

部署完成后：

- 平台：`https://你的项目.vercel.app`
- API 文档：`https://你的项目.vercel.app/api/v1/docs`
- 健康检查：`https://你的项目.vercel.app/api/health`

确认管理员能够登录后，可以删除 `BOOTSTRAP_ADMIN_PASSWORD`。以后部署检测到管理员已经存在时不会修改密码。

## 5. 本地开发

原有启动方式保持不变：

```batch
start.bat
```

它仍然使用 `backend/materials_dmp.db` 和本地附件目录。不要在本地设置 `VERCEL=1`，除非同时准备好了 PostgreSQL 与 Blob 环境变量。

## 当前 Vercel 限制

Vercel Function 的普通请求体和响应体上限为 4.5 MB。因此当前服务端附件接口适合小文件；超过该大小的 SEM、XRD 原始数据等应在后续改为浏览器直接上传到 Blob，并使用短期授权下载。

现有 SQLite 数据不会自动复制到 PostgreSQL。首次部署默认得到一套空的生产数据库；如需迁移本机已有数据，应在部署前单独执行数据迁移和校验。

## 配置文件

- `vercel.json`：安装、构建、静态路由和 Function 打包规则。
- `api/index.py`：Vercel FastAPI 入口。
- `backend/scripts/deploy_database.py`：生产数据库迁移、角色和管理员初始化。
- `backend/app/config.py`：SQLite/PostgreSQL 与本地/Blob 环境切换。
