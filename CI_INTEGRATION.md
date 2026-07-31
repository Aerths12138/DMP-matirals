# 验收与 CI 接入

项目根目录提供一个非交互、平台无关的验收入口：

```text
node scripts/acceptance.mjs
```

该入口不会安装依赖、启动服务或修改数据库。运行前应由本地环境或 CI 的准备阶段完成：

- 创建根目录 `venv` 并安装后端依赖；
- 在 `frontend` 目录安装锁文件指定的前端依赖；
- 提供 `git`、Node.js 和 npm。

验收入口固定按以下顺序运行：

1. 后端完整测试：`venv` 中的 Python 执行 `python -m pytest -q`；
2. 前端类型检查：`npm exec -- tsc --noEmit`；
3. 前端构建：`npm run build`；
4. 前端聚焦检查：`npm run test:assistant-confirmation`。

输出开头包含当前 `Git revision`，每一步结束后打印对应退出码，末尾打印汇总和整体退出码。所有步骤都会执行，以保留完整的验收状态；任一步非零时，整体返回首个非零退出码。

## 接入内网 CI

仓库当前没有可确认供应商的流水线配置，因此不添加 GitHub Actions、GitLab CI、Jenkins、Azure Pipelines 或其他供应商专用文件。

确定实际内网 CI 后，在其检出代码和安装依赖的阶段之后，从仓库根目录直接执行：

```text
node scripts/acceptance.mjs
```

将该命令的进程退出码直接作为流水线任务结果，不要用忽略错误或强制返回成功的包装命令。流水线日志应保留脚本输出，以便把 Git revision、各步骤退出码和整体结果绑定到同一次验收。
