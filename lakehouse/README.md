# Materials DMP Lakehouse

这个目录把现有 Materials DMP 扩展为一套可独立展示的数据工程项目。PostgreSQL
仍然是面向 FastAPI 的事务数据库；Spark 将业务数据增量同步到 Apache Iceberg，
生成适合分析的银层宽表、金层指标和数据质量记录。

## 架构

```text
Materials DMP / PostgreSQL
           |
           | Spark JDBC + watermark
           v
Iceberg bronze  ---- 原始业务表、批次号、摄取时间
           |
           | Spark SQL / DataFrame joins
           v
Iceberg silver  ---- 材料性能观测、仪器测量点
           |
           +------> Iceberg gold ---- 项目 KPI、性能统计
           |
           +------> quality rules -- 质量问题、批次汇总

Spark master + worker + history server
Iceberg Hadoop catalog + 共享 warehouse 卷（本地开发）
```

选择 Iceberg 是因为它提供快照、时间旅行、原子提交和表结构演进能力。开发环境使用
Docker 共享卷，因此不依赖已停止维护的对象存储镜像；生产部署可以把
`ICEBERG_WAREHOUSE_URI` 改成 `s3://...`，镜像已经包含 Iceberg 的 S3FileIO 依赖。

固定版本：

- Apache Spark 4.1.3（Scala 2.13、Java 17、Python）
- Apache Iceberg 1.12.0
- PostgreSQL JDBC 42.7.8

官方参考：

- <https://spark.apache.org/docs/4.1.3/>
- <https://iceberg.apache.org/docs/1.12.0/spark-getting-started/>
- <https://iceberg.apache.org/docs/1.12.0/spark-configuration/>

## 五分钟演示

前提是安装 Docker Desktop。第一次构建需要下载 Spark 镜像和 Maven 依赖。

```powershell
.\lakehouse\run_pipeline.ps1 -Source demo
```

该命令会启动：

- Spark Master UI：<http://localhost:8081>
- Spark Worker UI：<http://localhost:8082>
- Spark History Server：<http://localhost:18080>

演示模式会生成一套确定性的 LLZO 材料数据，不需要先启动 DMP。执行成功后会产生：

- `lakehouse.bronze.*`：项目、材料、实验、样品、表征、性能、测量点和分析结果；
- `lakehouse.silver.material_property_observations`：面向分析的材料性能宽表；
- `lakehouse.silver.measurement_observations`：带项目、样品和表征上下文的测量点；
- `lakehouse.gold.property_summary`：按属性、单位和方法分组的统计指标；
- `lakehouse.gold.project_kpis`：项目级材料、实验、样品和表征数量；
- `lakehouse.gold.data_quality_*`：规则明细和批次汇总；
- `lakehouse.ops.*`：增量水位和每阶段运行事件。

示例查询位于 [`sql/portfolio_queries.sql`](sql/portfolio_queries.sql)。

交互式进入 Spark SQL：

```powershell
.\lakehouse\query_lakehouse.ps1
```

一次性执行仓库中的示例查询：

```powershell
.\lakehouse\query_lakehouse.ps1 -SqlFile lakehouse\sql\portfolio_queries.sql
```

## 同步真实 DMP PostgreSQL

开发 Compose 中的 PostgreSQL 默认账号可直接用于演示：

```powershell
.\lakehouse\run_pipeline.ps1 -Source postgres -FullRefresh
```

第一次使用 `-FullRefresh` 建立完整快照。以后省略该参数，作业会读取
`lakehouse.ops.etl_watermarks`，按各表的 `updated_at` 或 `created_at` 增量读取并通过
Iceberg `MERGE INTO` 幂等更新。

需要修改连接信息时，设置环境变量：

```powershell
$env:DMP_JDBC_URL = "jdbc:postgresql://postgres:5432/materials_dmp"
$env:DMP_JDBC_USER = "materials"
$env:DMP_JDBC_PASSWORD = "替换为真实密码"
.\lakehouse\run_pipeline.ps1 -Source postgres
```

认证用户、密码哈希、刷新令牌等表不会进入湖仓。当前增量方案处理新增和更新；源库物理
删除需要周期性全量刷新，或后续接入 Debezium/Kafka 的删除事件。

## 数据质量规则

当前规则覆盖：

- 性能记录必须至少具有数值或文本值；
- 数值性能应该具有单位；
- 附件必须具有合法长度的 SHA-256；
- 材料应该归属项目；
- 测量数据集声明的行数必须和测量点数量一致。

默认把质量问题写入表但不阻断管道。设置
`DMP_FAIL_ON_QUALITY_ERRORS=true` 后，error 级规则会使作业失败，适合 CI 或生产调度。

## 数据工程简历表达

建议按真实完成内容描述：

> 为材料科研 DMP 设计 Spark + Iceberg 湖仓，使用 JDBC watermark 与 MERGE 实现
> PostgreSQL 增量入湖，建设 bronze/silver/gold 分层模型、批次审计、数据质量门禁、
> Spark History Server 和可重复 Docker 演示环境。

不要宣称当前已经实现实时 CDC、Kafka 或生产级 S3；这些是下一阶段扩展项。

## 验证

不安装 Spark 也可以运行配置和 SQL 生成单元测试：

```powershell
C:\Users\Enki\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
  -m unittest discover -s lakehouse/tests -v
```

完整验收需要 Docker Desktop：先运行 demo 管道，再在 History Server 检查 SQL、Stage、
Shuffle 和 executor 指标，并执行 `sql/portfolio_queries.sql` 中的查询。

