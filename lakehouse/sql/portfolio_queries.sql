-- Run these statements from spark-sql after the demo pipeline completes.
-- All analytical tables are Apache Iceberg tables and retain snapshot history.

SELECT *
FROM lakehouse.gold.project_kpis
ORDER BY project_name;

SELECT
  material_name,
  property_name,
  unit,
  value_number,
  uncertainty,
  is_validated
FROM lakehouse.silver.material_property_observations
ORDER BY property_name, value_number DESC;

SELECT
  project_name,
  material_type,
  property_name,
  unit,
  observation_count,
  mean_value,
  stddev_value,
  validated_ratio
FROM lakehouse.gold.property_summary
ORDER BY observation_count DESC;

SELECT batch_id, severity, rule_name, issue_count
FROM lakehouse.gold.data_quality_summary
ORDER BY batch_id DESC, severity, rule_name;

-- Iceberg metadata tables expose the reproducible history of every mart.
SELECT committed_at, snapshot_id, operation
FROM lakehouse.gold.property_summary.snapshots
ORDER BY committed_at DESC;

