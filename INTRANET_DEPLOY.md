# 材料数据管理平台内网部署

本方案将平台部署为三个容器：

- `frontend`：Nginx 托管前端，并将 `/api/` 转发给后端；
- `backend`：FastAPI 服务，只在容器网络中暴露；
- `postgres`：生产数据库，只在容器网络中暴露。

大语言模型作为独立的内网服务运行。平台通过 OpenAI 兼容接口调用它，不需要把模型权重打进平台镜像。

## 1. 上线前准备

服务器需要：

- Docker Engine 24+；
- Docker Compose v2；
- 能访问所选基础镜像和 Python/npm 依赖源，或已配置内网镜像仓库；
- 为 PostgreSQL、附件和备份预留持久化磁盘；
- 一个支持工具调用（function/tool calling）的本地模型服务。

模型接口至少需要兼容：

```text
POST <LLM_BASE_URL>/chat/completions
```

并能正确接收 `messages`、`tools`、`tool_choice`，返回 OpenAI 风格的 `tool_calls`。仅支持普通文本对话、但不支持工具调用的模型，不能可靠执行平台的增删查改操作。

如果使用 vLLM，需要按所选模型启用自动工具调用，并配置与模型匹配的 tool-call parser。不同模型的 parser 不相同，部署模型时应先用本文第 5 节的探针验证。

## 2. 配置生产环境

在项目根目录执行：

```bash
cp .env.production.example .env.production
```

编辑 `.env.production`，至少修改：

- `SECRET_KEY`：长随机字符串；
- `POSTGRES_PASSWORD`：数据库强密码；
- `CORS_ORIGINS`：平台的实际内网访问地址；
- `LLM_BASE_URL`：模型服务的 `/v1` 根地址；
- `LLM_MODEL`：模型服务识别的模型名；
- `LLM_API_KEY`：模型网关要求鉴权时填写，否则留空。

生成应用密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

模型运行在同一台 Docker 主机时可使用：

```env
LLM_BASE_URL=http://host.docker.internal:8000/v1
```

模型运行在另一台内网服务器时，应改成该服务器的内网 DNS 名或固定 IP，例如：

```env
LLM_BASE_URL=http://llm.internal:8000/v1
```

不要把 `.env.production`、模型令牌或数据库密码提交到版本库。

## 3. 校验并启动

先让 Compose 展开并检查配置：

```bash
docker compose --env-file .env.production -f compose.production.yml config
```

构建并启动：

```bash
docker compose --env-file .env.production -f compose.production.yml up -d --build
```

初始化容器会自动执行数据库迁移并创建角色和权限，但不会创建弱口令演示账户。

首次部署后，显式创建第一个管理员：

```bash
docker compose --env-file .env.production -f compose.production.yml run --rm \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_EMAIL=admin@internal.example \
  -e ADMIN_PASSWORD='替换为至少12位的强密码' \
  backend python -m scripts.create_admin
```

浏览器访问：

```text
http://<服务器内网地址>:8080
```

端口可通过 `.env.production` 中的 `APP_PORT` 修改。

## 4. 运行维护

查看状态和日志：

```bash
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs -f backend
docker compose --env-file .env.production -f compose.production.yml logs -f frontend
```

停止服务但保留数据：

```bash
docker compose --env-file .env.production -f compose.production.yml down
```

重新启动：

```bash
docker compose --env-file .env.production -f compose.production.yml up -d
```

不要使用 `down -v`，它会删除命名卷中的 PostgreSQL 数据和附件。

生产环境应定期备份：

- PostgreSQL 数据库（推荐 `pg_dump`）；
- `materials_storage` 命名卷；
- `.env.production` 的离线安全副本。

平台内的 AI 临时回退快照不等同于灾难恢复备份。

若内网有统一网关，建议在本 Compose 前增加 HTTPS 反向代理，并在网关实施证书、访问日志、IP 白名单和请求速率限制。PostgreSQL 和后端端口无需直接暴露到用户网络。

## 5. 模型工具调用验收

上线前应直接请求模型接口，确认它会返回 `tool_calls`，而不是只用文字描述“我要调用工具”：

```bash
curl "$LLM_BASE_URL/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -d '{
    "model": "'"$LLM_MODEL"'",
    "messages": [{"role": "user", "content": "查询名称含齐鲁的材料"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "search_materials",
        "description": "搜索材料",
        "parameters": {
          "type": "object",
          "properties": {"query": {"type": "string"}},
          "required": ["query"]
        }
      }
    }],
    "tool_choice": "auto",
    "temperature": 0
  }'
```

通过标准：

- HTTP 状态为 200；
- 返回消息包含 `tool_calls`；
- 工具名为 `search_materials`；
- 参数是可解析 JSON，并包含查询词；
- 中文指令能够稳定触发工具；
- 多轮工具调用不会丢失上下文。

然后在平台中依次验证：

1. 查询当前用户有权查看的数据；
2. 尝试查询无权项目，确认结果不可见；
3. 发起新增、修改、删除，确认只生成预览；
4. 用户确认后才真正执行；
5. 修改或删除后可从“可回退版本”恢复；
6. 管理员与普通用户分别验证，确认 AI 权限与页面/API 权限一致。

## 6. 更新与回退

更新代码后：

```bash
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

`initialize` 服务会在后端启动前执行 Alembic 数据库迁移。升级前必须先做数据库和附件备份。应用镜像可以回退，但数据库迁移是否可逆要按对应 Alembic 版本单独确认。

## 7. 从 SQLite 一次性迁移到 PostgreSQL

迁移工具默认只做只读预检。执行模式会清空目标 PostgreSQL 中的平台表，再在一个事务中复制全部数据；任何复制或行数校验失败都会回滚。只应对新建或已完整备份的目标库执行。

先停止旧平台，复制 SQLite 文件和附件目录，避免复制过程中仍有写入：

```bash
# 示例路径，请替换成服务器上的实际位置
mkdir -p /srv/materials-dmp-migration
cp /旧平台/backend/materials_dmp.db /srv/materials-dmp-migration/
cp -a /旧平台/backend/storage /srv/materials-dmp-migration/
sha256sum /srv/materials-dmp-migration/materials_dmp.db
```

启动 PostgreSQL，并创建最新表结构：

```bash
docker compose --env-file .env.production -f compose.production.yml up -d postgres
docker compose --env-file .env.production -f compose.production.yml run --rm initialize
```

第一次只运行预检，不写目标数据库：

```bash
docker compose --env-file .env.production -f compose.production.yml run --rm \
  -v /srv/materials-dmp-migration/materials_dmp.db:/migration/source.db:ro \
  backend python -m scripts.migrate_sqlite_to_postgres \
  --source /migration/source.db
```

预检会确认：

- SQLite 外键没有损坏；
- SQLite 与 PostgreSQL 均为当前 Alembic 版本；
- 两端表结构与当前应用完全匹配；
- 输出迁移前逐表行数；
- 不显示数据库明文密码；
- 不修改任何数据。

核对数据库备份和预检结果后，才执行迁移：

```bash
docker compose --env-file .env.production -f compose.production.yml run --rm \
  -v /srv/materials-dmp-migration/materials_dmp.db:/migration/source.db:ro \
  backend python -m scripts.migrate_sqlite_to_postgres \
  --source /migration/source.db \
  --execute --confirm REPLACE_TARGET
```

安全规则：

- `--execute` 和 `--confirm REPLACE_TARGET` 缺少任意一个都不会写数据库；
- 目标平台表会在同一个 PostgreSQL 事务中替换；
- 目标存在非平台表、版本不同或表结构不完整时会拒绝执行；
- 整数主键序列会在复制后自动校准；
- 旧 `refresh_tokens` 不迁移，所有账号需要重新登录；
- 用户、角色、项目成员、私有项目关系、审计日志和 AI 回退记录均保留。

数据库迁移成功后，将附件复制到 Compose 的持久化卷：

```bash
docker compose --env-file .env.production -f compose.production.yml run --rm \
  -v /srv/materials-dmp-migration/storage:/migration/storage:ro \
  backend sh -c 'cp -a /migration/storage/. /data/materials-dmp/storage/'
```

附件可能大于 1 MB，因此迁移工具不把它们编码进数据库或生成中间文件。复制后应抽查下载，并根据 `files.checksum_sha256` 校验关键附件。

最后启动平台：

```bash
docker compose --env-file .env.production -f compose.production.yml up -d
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 backend
```

迁移完成后，应分别用管理员和普通用户验收总记录数、项目成员关系、私有项目隔离、附件下载、AI 查询权限以及修改/删除回退。

## 8. DeepSeek 兼容

原有 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 配置仍可使用。只要设置了 `LLM_*`，平台会优先使用通用配置，因此同一份代码可以在公网 DeepSeek 和内网 OpenAI 兼容模型之间切换。
