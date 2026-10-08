# Materials DMP agent guide

本文件适用于整个仓库。以下命令均从仓库根目录、在 PowerShell 中执行。

## 已验证的运行路径

完整启动：

```powershell
.\start.bat
```

该脚本创建或复用根目录 `venv`，安装依赖、初始化开发数据库，并启动后端
`http://localhost:8000` 与 Vite 前端。前端端口被占用时，以 Vite 实际输出为准。

只启动后端：

```powershell
Push-Location backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Pop-Location
```

只启动前端：

```powershell
Push-Location frontend
npm run dev
Pop-Location
```

项目 Python 一律使用 `.\venv\Scripts\python.exe`。导入 `app` 的后端命令必须在
`backend` 目录中运行，不要从仓库根目录直接调用系统 Python 或 pytest。

## 已验证的聚焦检查

从仓库根目录检查 AI 确认阶段会重新校验项目权限：

```powershell
Push-Location backend
..\venv\Scripts\python.exe -m pytest tests/test_assistant.py::test_confirmation_rechecks_project_membership -q
$code = $LASTEXITCODE
Pop-Location
exit $code
```

运行完整 AI 助手后端测试时，将测试目标替换为 `tests/test_assistant.py`。
前端单一验证入口会先检查 AI 写操作确认状态，再执行 TypeScript 与 Vite 构建：

```powershell
Push-Location frontend
npm run validate
$code = $LASTEXITCODE
Pop-Location
exit $code
```

## Owner / affected-check 映射

| 区域 | 最小 owner 路径 | 修改后至少运行 |
| --- | --- | --- |
| 后端 API、模型、服务 | `backend/app/` | `backend/tests/` 中与改动同域的测试文件；无法确定时运行对应完整文件 |
| 前端页面、组件、API 客户端 | `frontend/src/` | `frontend` 目录的 `npm run validate`；未覆盖的交互行为仍需浏览器人工验证 |
| AI 助手对话、Excel 读取与写工具 | `backend/app/api/v1/assistant.py`、`backend/app/services/assistant_service.py`、`backend/app/services/assistant_excel_service.py`、`frontend/src/api/assistant.ts`、`frontend/src/pages/Assistant/AIAssistantPage.tsx` | `backend/tests/test_assistant.py` 与 `backend/tests/test_assistant_excel.py`；前端改动另运行 `npm run validate` |
| AI 修改、删除与回退 | `backend/app/api/v1/assistant.py`、`backend/app/services/assistant_backup_service.py`、`backend/app/models/assistant_backup.py` | `test_update_backup_can_be_restored_once`；涉及级联删除时再运行对应 graph restore 测试 |

## AI 写操作风险边界

- 新增、修改、删除必须保持“生成预览 → 用户确认 → 执行”流程；不得让对话请求直接落库。
- 确认执行必须重新检查用户全局权限和当前项目成员权限，不能只信任预览阶段的结果。
- 修改、删除必须在执行前创建临时备份；回退仍要检查当前权限、过期状态、重复恢复和较新版本冲突。
- 改动确认或权限逻辑时，至少运行
  `test_confirmation_rechecks_project_membership`。
- 改动备份或恢复逻辑时，至少运行
  `test_update_backup_can_be_restored_once`；涉及材料或项目级联关系时，运行
  `test_deleted_material_graph_can_be_restored_once` 或
  `test_deleted_project_graph_can_be_restored_once`。
