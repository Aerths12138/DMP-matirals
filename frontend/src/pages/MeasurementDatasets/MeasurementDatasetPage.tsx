import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Button, Card, Col, Descriptions, Empty, Input, Modal, Row, Segmented,
  Select, Space, Spin, Statistic, Table, Typography, message,
} from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteMeasurementDataset,
  fetchMeasurementDataset,
  updateMeasurementDataset,
} from '../../api/measurementDatasets';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { buildHistogram, formatCompact, summarizeSeries } from '../../utils/measurementVisualization';

const { Title, Text } = Typography;
type VisualizationMode = 'line' | 'scatter' | 'area' | 'histogram' | 'summary';
const CHART_COLOR = '#1677ff';

export default function MeasurementDatasetPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [editing, setEditing] = useState(false);
  const [visualizationMode, setVisualizationMode] = useState<VisualizationMode>('line');
  const [selectedSeriesKey, setSelectedSeriesKey] = useState('');
  const [histogramBinCount, setHistogramBinCount] = useState(20);
  const query = useQuery({
    queryKey: ['measurement-dataset', id],
    queryFn: () => fetchMeasurementDataset(id),
    enabled: Boolean(id),
  });
  const updateMutation = useMutation({
    mutationFn: () => updateMeasurementDataset(id, { name: name.trim() }),
    onSuccess: (data) => {
      queryClient.setQueryData(['measurement-dataset', id], data);
      setEditing(false);
      message.success('数据集名称已修改');
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteMeasurementDataset(id),
    onSuccess: () => {
      message.success('数据集已删除');
      navigate('/import');
    },
  });

  if (query.isLoading) return <Spin />;
  if (query.isError) return <Alert type="error" showIcon message="读取数据集失败" />;
  const dataset = query.data;
  if (!dataset) return <Empty description="数据集不存在" />;
  const chartData = dataset.points.map((point) => ({ x: point.x_value, ...point.values }));
  const selectedSeries = dataset.series_schema.find((series) => series.key === selectedSeriesKey)
    || dataset.series_schema[0];
  const selectedValues = selectedSeries
    ? dataset.points.map((point) => point.values[selectedSeries.key]).filter(Number.isFinite)
    : [];
  const statistics = summarizeSeries(selectedValues);
  const histogram = buildHistogram(selectedValues, histogramBinCount);
  const xAxisLabel = `${dataset.x_name}${dataset.x_unit ? ` (${dataset.x_unit})` : ''}`;
  const yAxisLabel = selectedSeries
    ? `${selectedSeries.name}${selectedSeries.unit ? ` (${selectedSeries.unit})` : ''}`
    : '';
  const tableColumns = [
    { title: dataset.x_name, dataIndex: 'x', key: 'x' },
    ...dataset.series_schema.map((series) => ({
      title: `${series.name}${series.unit ? ` (${series.unit})` : ''}`,
      dataIndex: series.key,
      key: series.key,
    })),
  ];

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{dataset.name}</Title>
        <Space>
          <Button icon={<EditOutlined />} onClick={() => { setName(dataset.name); setEditing(true); }}>修改名称</Button>
          <Button danger icon={<DeleteOutlined />} onClick={() => Modal.confirm({
            title: '确认删除这个数据集？',
            content: `将删除 ${dataset.row_count} 个测点。此操作不会在未确认时执行。`,
            okText: '确认删除',
            okButtonProps: { danger: true },
            cancelText: '取消',
            onOk: () => deleteMutation.mutateAsync(),
          })}>删除</Button>
        </Space>
      </Space>
      <Descriptions bordered size="small" style={{ marginBottom: 16 }}>
        <Descriptions.Item label="横坐标">{dataset.x_name}{dataset.x_unit ? ` (${dataset.x_unit})` : ''}</Descriptions.Item>
        <Descriptions.Item label="测点">{dataset.row_count}</Descriptions.Item>
        <Descriptions.Item label="原始文件">{dataset.source_file_id ? '已留存' : '未留存'}</Descriptions.Item>
      </Descriptions>
      <Card
        title="可视化模组"
        extra={(
          <Space wrap>
            <Text type="secondary">数值序列</Text>
            <Select
              value={selectedSeries?.key}
              onChange={setSelectedSeriesKey}
              options={dataset.series_schema.map((series) => ({
                value: series.key,
                label: `${series.name}${series.unit ? ` (${series.unit})` : ''}`,
              }))}
              style={{ minWidth: 220 }}
            />
          </Space>
        )}
        style={{ marginBottom: 16 }}
      >
        <Segmented
          block
          value={visualizationMode}
          onChange={(value) => setVisualizationMode(value as VisualizationMode)}
          options={[
            { label: '趋势折线', value: 'line' },
            { label: '散点分布', value: 'scatter' },
            { label: '面积概览', value: 'area' },
            { label: '频数直方图', value: 'histogram' },
            { label: '统计摘要', value: 'summary' },
          ]}
          style={{ marginBottom: 20 }}
        />
        {!selectedSeries ? (
          <Empty description="该数据集没有可视化的数值序列" />
        ) : visualizationMode === 'summary' && statistics ? (
          <Row gutter={[16, 16]}>
            {[
              ['测点数', statistics.count, undefined],
              ['最小值', statistics.minimum, selectedSeries.unit],
              ['最大值', statistics.maximum, selectedSeries.unit],
              ['平均值', statistics.mean, selectedSeries.unit],
              ['中位数', statistics.median, selectedSeries.unit],
              ['标准差', statistics.standardDeviation, selectedSeries.unit],
              ['首点值', statistics.first, selectedSeries.unit],
              ['末点值', statistics.last, selectedSeries.unit],
            ].map(([title, value, suffix]) => (
              <Col xs={24} sm={12} lg={6} key={String(title)}>
                <Card size="small">
                  <Statistic
                    title={title}
                    value={typeof value === 'number' ? formatCompact(value) : value}
                    suffix={suffix}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        ) : (
          <>
            {visualizationMode === 'histogram' && (
              <Space style={{ marginBottom: 12 }}>
                <Text type="secondary">分箱数量</Text>
                <Select
                  value={histogramBinCount}
                  onChange={setHistogramBinCount}
                  options={[10, 20, 30, 50].map((value) => ({ value, label: `${value} 箱` }))}
                  style={{ width: 100 }}
                />
              </Space>
            )}
            <div style={{ width: '100%', height: 440 }}>
              <ResponsiveContainer>
                {visualizationMode === 'scatter' ? (
                  <ScatterChart margin={{ top: 10, right: 30, left: 20, bottom: 25 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="x" type="number" name={xAxisLabel} domain={['dataMin', 'dataMax']} label={{ value: xAxisLabel, position: 'insideBottom', offset: -12 }} />
                    <YAxis dataKey={selectedSeries.key} type="number" name={yAxisLabel} />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                    <Scatter name={yAxisLabel} data={chartData} fill={CHART_COLOR} isAnimationActive={false} />
                  </ScatterChart>
                ) : visualizationMode === 'area' ? (
                  <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 25 }}>
                    <defs>
                      <linearGradient id="measurementArea" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CHART_COLOR} stopOpacity={0.7} />
                        <stop offset="95%" stopColor={CHART_COLOR} stopOpacity={0.08} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} label={{ value: xAxisLabel, position: 'insideBottom', offset: -12 }} />
                    <YAxis />
                    <Tooltip />
                    <Area type="monotone" dataKey={selectedSeries.key} name={yAxisLabel} stroke={CHART_COLOR} fill="url(#measurementArea)" isAnimationActive={false} />
                  </AreaChart>
                ) : visualizationMode === 'histogram' ? (
                  <BarChart data={histogram} margin={{ top: 10, right: 30, left: 20, bottom: 55 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" interval="preserveStartEnd" angle={-25} textAnchor="end" height={70} />
                    <YAxis allowDecimals={false} label={{ value: '频数', angle: -90, position: 'insideLeft' }} />
                    <Tooltip formatter={(value) => [`${value} 个测点`, '频数']} labelFormatter={(label) => `${yAxisLabel}：${label}`} />
                    <Bar dataKey="count" name="频数" fill={CHART_COLOR} isAnimationActive={false} />
                  </BarChart>
                ) : (
                  <LineChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 25 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} label={{ value: xAxisLabel, position: 'insideBottom', offset: -12 }} />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey={selectedSeries.key} name={yAxisLabel} dot={false} stroke={CHART_COLOR} isAnimationActive={false} />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </>
        )}
      </Card>
      <Card title="测点数据（可查询）">
        <Table columns={tableColumns} dataSource={chartData.map((row, index) => ({ ...row, key: index }))} pagination={{ pageSize: 50 }} scroll={{ x: 'max-content' }} size="small" />
      </Card>
      <Modal
        title="修改数据集名称"
        open={editing}
        onCancel={() => setEditing(false)}
        onOk={() => updateMutation.mutate()}
        confirmLoading={updateMutation.isPending}
        okButtonProps={{ disabled: !name.trim() }}
      >
        <Text>名称</Text>
        <Input value={name} onChange={(event) => setName(event.target.value)} style={{ marginTop: 8 }} />
      </Modal>
    </div>
  );
}
