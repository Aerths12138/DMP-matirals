import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Alert,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { BarChartOutlined, DotChartOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fetchMaterials } from '../../api/materials';
import { fetchProjects } from '../../api/projects';
import { fetchSamples } from '../../api/samples';
import {
  fetchPropertyComparison,
  fetchSamplePropertyComparison,
} from '../../api/visualizations';
import type { ComparisonMeasurement } from '../../types/visualization';

const { Title, Text } = Typography;

type ComparisonMode = 'material' | 'sample';

interface Metric {
  key: string;
  name: string;
  unit?: string;
  propertyType: string;
}

interface ComparisonSubject {
  id: string;
  name: string;
  typeLabel: string;
  detailPath?: string;
}

interface NormalizedComparison {
  subjects: ComparisonSubject[];
  measurements: ComparisonMeasurement[];
}

const MATERIAL_TYPE_LABELS: Record<string, string> = {
  metal: '金属',
  polymer: '聚合物',
  ceramic: '陶瓷',
  composite: '复合材料',
  battery: '电池材料',
  other: '其他',
};

function metricKey(propertyName: string, unit?: string) {
  return `${propertyName}\u001f${unit || ''}`;
}

function measurementKey(subjectId: string, selectedMetricKey: string) {
  return `${subjectId}\u001e${selectedMetricKey}`;
}

function metricLabel(metric: Metric) {
  return metric.unit ? `${metric.name} [${metric.unit}]` : `${metric.name} [无单位]`;
}

function formatNumber(value: number) {
  const absolute = Math.abs(value);
  if ((absolute !== 0 && absolute < 0.001) || absolute >= 10000) {
    return value.toExponential(3);
  }
  return Number(value.toPrecision(6)).toString();
}

function formatConditions(conditions: Record<string, unknown>) {
  const entries = Object.entries(conditions || {});
  if (entries.length === 0) return '未记录';
  return entries
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join('；');
}

async function loadComparison(
  mode: ComparisonMode,
  subjectIds: string[]
): Promise<NormalizedComparison> {
  if (mode === 'material') {
    const response = await fetchPropertyComparison(subjectIds);
    return {
      subjects: response.materials.map((material) => ({
        id: material.id,
        name: material.name,
        typeLabel: MATERIAL_TYPE_LABELS[material.material_type] || material.material_type,
        detailPath: `/materials/${material.id}`,
      })),
      measurements: response.measurements,
    };
  }

  const response = await fetchSamplePropertyComparison(subjectIds);
  return {
    subjects: response.samples.map((sample) => ({
      id: sample.id,
      name: sample.sample_code,
      typeLabel: [
        sample.material_name || '未关联材料',
        sample.batch_number ? `批次 ${sample.batch_number}` : undefined,
      ].filter(Boolean).join(' · '),
      detailPath: sample.project_id ? `/projects/${sample.project_id}` : undefined,
    })),
    measurements: response.measurements,
  };
}

function BarTooltip({ active, payload, metric, subjectLabel }: any) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div style={{ background: '#fff', border: '1px solid #d9d9d9', padding: 10, borderRadius: 6 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{subjectLabel}：{row.subject}</div>
      <div>
        {metric.name}: {formatNumber(row.value)}{metric.unit ? ` ${metric.unit}` : ''}
        {row.uncertainty != null ? ` ± ${formatNumber(row.uncertainty)}` : ''}
      </div>
      {row.measurementCount > 1 && <div>历史记录：{row.measurementCount} 条（当前显示最新值）</div>}
    </div>
  );
}

function ScatterTooltip({ active, payload, xMetric, yMetric, subjectLabel }: any) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div style={{ background: '#fff', border: '1px solid #d9d9d9', padding: 10, borderRadius: 6 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{subjectLabel}：{row.subject}</div>
      <div>{xMetric.name}: {formatNumber(row.x)}{xMetric.unit ? ` ${xMetric.unit}` : ''}</div>
      <div>{yMetric.name}: {formatNumber(row.y)}{yMetric.unit ? ` ${yMetric.unit}` : ''}</div>
    </div>
  );
}

export default function VisualizationPage() {
  const [mode, setMode] = useState<ComparisonMode>('material');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [materialSearch, setMaterialSearch] = useState('');
  const [sampleProjectId, setSampleProjectId] = useState<string>();
  const [barMetricKey, setBarMetricKey] = useState<string>();
  const [scatterXKey, setScatterXKey] = useState<string>();
  const [scatterYKey, setScatterYKey] = useState<string>();

  const materialOptionsQuery = useQuery({
    queryKey: ['visualization-material-options', materialSearch],
    queryFn: () => fetchMaterials({ page: 1, size: 100, search: materialSearch || undefined }),
    enabled: mode === 'material',
  });

  const projectsQuery = useQuery({
    queryKey: ['visualization-project-options'],
    queryFn: () => fetchProjects({ page: 1, size: 200 }),
    enabled: mode === 'sample',
  });

  const sampleOptionsQuery = useQuery({
    queryKey: ['visualization-sample-options', sampleProjectId],
    queryFn: () => fetchSamples({ project_id: sampleProjectId!, page: 1, size: 200 }),
    enabled: mode === 'sample' && !!sampleProjectId,
  });

  const comparisonQuery = useQuery({
    queryKey: ['property-comparison', mode, selectedIds],
    queryFn: () => loadComparison(mode, selectedIds),
    enabled: selectedIds.length >= 2,
  });

  const comparison = comparisonQuery.data;
  const projectOptions = (projectsQuery.data?.items || []).map((project) => ({
    value: project.id,
    label: project.name,
  }));

  const materialOptions = useMemo(() => {
    const subjects = new Map<string, { id: string; name: string; typeLabel: string }>();
    materialOptionsQuery.data?.items.forEach((material) => subjects.set(material.id, {
      id: material.id,
      name: material.name,
      typeLabel: MATERIAL_TYPE_LABELS[material.material_type] || material.material_type,
    }));
    if (mode === 'material') {
      comparison?.subjects.forEach((subject) => subjects.set(subject.id, subject));
    }
    return Array.from(subjects.values()).map((subject) => ({
      value: subject.id,
      label: `${subject.name} · ${subject.typeLabel}`,
    }));
  }, [materialOptionsQuery.data, comparison, mode]);

  const sampleOptions = useMemo(() => {
    const subjects = new Map<string, { id: string; name: string; typeLabel: string }>();
    sampleOptionsQuery.data?.items.forEach((sample) => subjects.set(sample.id, {
      id: sample.id,
      name: sample.sample_code,
      typeLabel: [sample.form, sample.batch_number ? `批次 ${sample.batch_number}` : undefined]
        .filter(Boolean).join(' · ') || '样品',
    }));
    if (mode === 'sample') {
      comparison?.subjects.forEach((subject) => subjects.set(subject.id, subject));
    }
    return Array.from(subjects.values()).map((subject) => ({
      value: subject.id,
      label: `${subject.name} · ${subject.typeLabel}`,
    }));
  }, [sampleOptionsQuery.data, comparison, mode]);

  const metrics = useMemo<Metric[]>(() => {
    const byKey = new Map<string, Metric>();
    comparison?.measurements.forEach((measurement) => {
      const key = metricKey(measurement.property_name, measurement.unit);
      if (!byKey.has(key)) {
        byKey.set(key, {
          key,
          name: measurement.property_name,
          unit: measurement.unit,
          propertyType: measurement.property_type,
        });
      }
    });
    return Array.from(byKey.values()).sort((a, b) => metricLabel(a).localeCompare(metricLabel(b), 'zh-CN'));
  }, [comparison]);

  const measurements = useMemo(() => {
    const bySubjectAndMetric = new Map<string, ComparisonMeasurement>();
    comparison?.measurements.forEach((measurement) => {
      const subjectId = mode === 'material' ? measurement.material_id : measurement.sample_id;
      if (!subjectId) return;
      const key = metricKey(measurement.property_name, measurement.unit);
      bySubjectAndMetric.set(measurementKey(subjectId, key), measurement);
    });
    return bySubjectAndMetric;
  }, [comparison, mode]);

  useEffect(() => {
    const keys = metrics.map((metric) => metric.key);
    setBarMetricKey((current) => current && keys.includes(current) ? current : keys[0]);
    setScatterXKey((current) => current && keys.includes(current) ? current : keys[0]);
    setScatterYKey((current) => current && keys.includes(current) ? current : (keys[1] || keys[0]));
  }, [metrics]);

  const currentBarMetric = metrics.find((metric) => metric.key === barMetricKey);
  const currentXMetric = metrics.find((metric) => metric.key === scatterXKey);
  const currentYMetric = metrics.find((metric) => metric.key === scatterYKey);
  const metricOptions = metrics.map((metric) => ({ value: metric.key, label: metricLabel(metric) }));
  const subjectLabel = mode === 'material' ? '材料' : '样品';

  const barData = useMemo(() => {
    if (!comparison || !currentBarMetric) return [];
    return comparison.subjects.flatMap((subject) => {
      const measurement = measurements.get(measurementKey(subject.id, currentBarMetric.key));
      return measurement ? [{
        subject: subject.name,
        value: measurement.value_number,
        uncertainty: measurement.uncertainty,
        measurementCount: measurement.measurement_count,
      }] : [];
    });
  }, [comparison, currentBarMetric, measurements]);

  const scatterData = useMemo(() => {
    if (!comparison || !currentXMetric || !currentYMetric) return [];
    return comparison.subjects.flatMap((subject) => {
      const x = measurements.get(measurementKey(subject.id, currentXMetric.key));
      const y = measurements.get(measurementKey(subject.id, currentYMetric.key));
      return x && y ? [{ subject: subject.name, x: x.value_number, y: y.value_number }] : [];
    });
  }, [comparison, currentXMetric, currentYMetric, measurements]);

  const columns = useMemo<ColumnsType<ComparisonSubject>>(() => [
    {
      title: subjectLabel,
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 180,
      render: (name: string, subject) => subject.detailPath
        ? <Link to={subject.detailPath}>{name}</Link>
        : name,
    },
    {
      title: mode === 'material' ? '类型' : '关联材料 / 批次',
      dataIndex: 'typeLabel',
      key: 'typeLabel',
      fixed: 'left',
      width: mode === 'material' ? 110 : 180,
      render: (label: string) => <Tag>{label}</Tag>,
    },
    ...metrics.map((metric) => ({
      title: (
        <div>
          <div>{metric.name}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>{metric.unit || '无单位'}</Text>
        </div>
      ),
      key: metric.key,
      width: 175,
      render: (_: unknown, subject: ComparisonSubject) => {
        const measurement = measurements.get(measurementKey(subject.id, metric.key));
        if (!measurement) return <Text type="secondary">—</Text>;
        const detail = (
          <div>
            <div>条件：{formatConditions(measurement.conditions)}</div>
            <div>方法：{measurement.test_method || '未记录'}</div>
            <div>记录时间：{new Date(measurement.created_at).toLocaleString('zh-CN')}</div>
          </div>
        );
        return (
          <Tooltip title={detail} placement="topLeft">
            <Space size={4} wrap>
              <span>
                {formatNumber(measurement.value_number)}
                {measurement.uncertainty != null ? ` ± ${formatNumber(measurement.uncertainty)}` : ''}
              </span>
              {measurement.measurement_count > 1 && <Tag color="blue">最新/{measurement.measurement_count}</Tag>}
            </Space>
          </Tooltip>
        );
      },
    })),
  ], [metrics, measurements, mode, subjectLabel]);

  const hasHistory = comparison?.measurements.some((measurement) => measurement.measurement_count > 1);

  const handleModeChange = (nextMode: ComparisonMode) => {
    setMode(nextMode);
    setSelectedIds([]);
    setMaterialSearch('');
  };

  const handleProjectChange = (projectId?: string) => {
    setSampleProjectId(projectId);
    setSelectedIds([]);
  };

  const handleSubjectChange = (ids: string[]) => {
    if (ids.length > 12) {
      message.warning(`一次最多对比 12 个${subjectLabel}`);
      return;
    }
    setSelectedIds(ids);
  };

  return (
    <div>
      <Title level={4}>材料与样品性能可视化</Title>
      <Text type="secondary">
        对比可访问对象的数值性能。相同指标的不同单位会作为独立序列，不进行隐式换算。
      </Text>

      <Card style={{ marginTop: 16, marginBottom: 16 }}>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Segmented
            value={mode}
            options={[
              { label: '材料对比', value: 'material' },
              { label: '样品对比', value: 'sample' },
            ]}
            onChange={(value) => handleModeChange(value as ComparisonMode)}
          />

          {mode === 'sample' && (
            <Select
              value={sampleProjectId}
              options={projectOptions}
              onChange={handleProjectChange}
              loading={projectsQuery.isLoading}
              placeholder="先选择样品所属项目"
              style={{ width: '100%' }}
              showSearch
              optionFilterProp="label"
              allowClear
            />
          )}

          <div>
            <Text strong>选择{subjectLabel}（2–12 个）</Text>
            <Select
              mode="multiple"
              value={selectedIds}
              options={mode === 'material' ? materialOptions : sampleOptions}
              onChange={handleSubjectChange}
              onSearch={mode === 'material' ? setMaterialSearch : undefined}
              filterOption={mode === 'material' ? false : true}
              optionFilterProp="label"
              loading={mode === 'material' ? materialOptionsQuery.isLoading : sampleOptionsQuery.isLoading}
              disabled={mode === 'sample' && !sampleProjectId}
              placeholder={mode === 'material' ? '输入材料名称搜索并选择' : '搜索并选择项目内样品'}
              style={{ width: '100%', marginTop: 8 }}
              allowClear
            />
          </div>
        </Space>
      </Card>

      {selectedIds.length < 2 ? (
        <Card><Empty description={`请至少选择两个${subjectLabel}开始对比`} /></Card>
      ) : comparisonQuery.isLoading ? (
        <Card><div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div></Card>
      ) : comparisonQuery.isError ? (
        <Alert type="error" showIcon message="无法加载对比数据" description={`请检查${subjectLabel}访问权限或稍后重试。`} />
      ) : comparison && comparison.measurements.length === 0 ? (
        <Card><Empty description={`所选${subjectLabel}尚无可视化的数值性能记录`} /></Card>
      ) : comparison ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {mode === 'sample' && (
            <Alert
              type="warning"
              showIcon
              message="样品模式只使用明确绑定到样品的性能记录"
              description="材料级性能不会自动复制到样品，避免把无法确认归属的数据混入对比。"
            />
          )}
          {hasHistory && (
            <Alert
              type="info"
              showIcon
              message="部分指标存在多条历史记录"
              description={`当前按${subjectLabel}、指标名称和单位展示最新记录；悬停表格数值可查看实验条件和测试方法。`}
            />
          )}

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <Card title={<span><BarChartOutlined /> 单指标对比</span>}>
                <Select
                  value={barMetricKey}
                  options={metricOptions}
                  onChange={setBarMetricKey}
                  style={{ width: '100%', marginBottom: 16 }}
                  placeholder="选择性能指标"
                />
                {currentBarMetric && barData.length > 0 ? (
                  <div style={{ height: 360 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData} margin={{ top: 20, right: 20, left: 10, bottom: 50 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="subject" angle={-25} textAnchor="end" interval={0} height={75} />
                        <YAxis />
                        <ChartTooltip content={<BarTooltip metric={currentBarMetric} subjectLabel={subjectLabel} />} />
                        <Bar dataKey="value" fill="#1677ff" name={metricLabel(currentBarMetric)}>
                          <ErrorBar dataKey="uncertainty" direction="y" stroke="#595959" strokeWidth={1.5} />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : <Empty description="所选指标没有可绘制数据" />}
              </Card>
            </Col>

            <Col xs={24} xl={12}>
              <Card title={<span><DotChartOutlined /> 二维性能关系</span>}>
                <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
                  <Select
                    value={scatterXKey}
                    options={metricOptions}
                    onChange={setScatterXKey}
                    style={{ width: '50%' }}
                    placeholder="X 轴指标"
                  />
                  <Select
                    value={scatterYKey}
                    options={metricOptions}
                    onChange={setScatterYKey}
                    style={{ width: '50%' }}
                    placeholder="Y 轴指标"
                  />
                </Space.Compact>
                {currentXMetric && currentYMetric && scatterData.length > 0 ? (
                  <div style={{ height: 360 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 20, right: 20, left: 10, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" dataKey="x" name={metricLabel(currentXMetric)} domain={['auto', 'auto']} />
                        <YAxis type="number" dataKey="y" name={metricLabel(currentYMetric)} domain={['auto', 'auto']} />
                        <ChartTooltip content={(
                          <ScatterTooltip
                            xMetric={currentXMetric}
                            yMetric={currentYMetric}
                            subjectLabel={subjectLabel}
                          />
                        )} />
                        <Scatter name={subjectLabel} data={scatterData} fill="#722ed1" />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                ) : <Empty description={`至少需要一个${subjectLabel}同时具有 X、Y 两项性能`} />}
              </Card>
            </Col>
          </Row>

          <Card title={`性能对比矩阵（${metrics.length} 个指标）`}>
            <Table
              columns={columns}
              dataSource={comparison.subjects}
              rowKey="id"
              pagination={false}
              size="small"
              scroll={{ x: Math.max(760, (mode === 'material' ? 290 : 360) + metrics.length * 175) }}
            />
          </Card>
        </Space>
      ) : null}
    </div>
  );
}
