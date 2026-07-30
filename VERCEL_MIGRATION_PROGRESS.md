# Vercel 适配进度

状态：代码适配和本地验证已完成。

已完成：

- Vite 静态前端与 FastAPI Python Function 单项目入口。
- 外部 PostgreSQL `DATABASE_URL` 和 Serverless 连接管理。
- 本地文件系统/私有 Vercel Blob 双存储后端。
- Alembic、角色权限和首次管理员自动初始化。
- Vercel 构建、路由、忽略文件与 Python 运行时配置。
- 中文部署说明、配置测试和附件存储回归测试。

验证结果：后端测试 40/40，通过前端生产构建，FastAPI Vercel 入口和路由导入正常；生成的前端单文件均小于 1 MB。

实际发布前仍需按照 `VERCEL_DEPLOY.md` 在 Vercel 创建 PostgreSQL、Private Blob，并设置环境变量。当前本机 SQLite 数据不会被上传或自动迁移。
