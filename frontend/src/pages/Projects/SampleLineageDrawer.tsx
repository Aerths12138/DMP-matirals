import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ApartmentOutlined,
  DiffOutlined,
  ExperimentOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchMetadataTemplates } from '../../api/dataStandards';
import AttachmentWorkbench from '../../components/files/AttachmentWorkbench';
import {
  createAnalysisResult,
  createCharacterization,
  createProcessingMethod,
  fetchAnalysisResults,
  fetchCharacterizations,
  fetchProcessingMethods,
} from '../../api/research';
import type { Sample } from '../../types/experiment';
import type {
  AnalysisResult,
  Characterization,
  ProcessingMethod,
} from '../../types/research';
import MetadataFields from './MetadataFields';

const { Paragraph, Text } = Typography;

interface SampleLineageDrawerProps {
  open: boolean;
  sample: Sample | null;
  projectId: string;
  canEdit: boolean;
  onClose: () => void;
}

interface ProcessingFormValues {
  method_type: string;
  equipment?: string;
  description?: string;
  order_in_chain?: number;
  parent_step_id?: string;
  parameters_json?: string;
}

interface CharacterizationFormValues {
  technique: string;
  title?: string;
  instrument?: string;
  description?: string;
  quality_flag?: string;
  parameters_json?: string;
  metadata_template_id?: string;
  metadata?: Record<string, unknown>;
}

interface AnalysisFormValues {
  analysis_type: string;
  pipeline_name?: string;
  model_name?: string;
  model_version?: string;
  result_data_json?: string;
  quality_metrics_json?: string;
  processing_time_ms?: number;
  gpu_used?: boolean;
}

function parseJsonObject(value: string | undefined, label: string) {
  if (!value?.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(value);
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('not an object');
    }
    return parsed as Record<string, unknown>;
  } catch {
    throw new Error(`${label}必须是合法的 JSON 对象`);
  }
}

function jsonPreview(value: Record<string, unknown>) {
  const text = JSON.stringify(value);
  return text.length > 80 ? `${text.slice(0, 77)}...` : text;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN');
}

function getErrorMessage(error: unknown, fallback: string) {
  const responseError = error as { response?: { data?: { detail?: string } } };
  return responseError.response?.data?.detail || fallback;
}

export default function SampleLineageDrawer({
  open,
  sample,
  projectId,
  canEdit,
  onClose,
}: SampleLineageDrawerProps) {
  const queryClient = useQueryClient();
  const [processingOpen, setProcessingOpen] = useState(false);
  const [characterizationOpen, setCharacterizationOpen] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [selectedCharacterizationId, setSelectedCharacterizationId] = useState<string>();
  const [selectedAnalysisIds, setSelectedAnalysisIds] = useState<string[]>([]);
  const [processingForm] = Form.useForm<ProcessingFormValues>();
  const [characterizationForm] = Form.useForm<CharacterizationFormValues>();
  const [analysisForm] = Form.useForm<AnalysisFormValues>();
  const selectedTemplateId = Form.useWatch('metadata_template_id', characterizationForm);

  const processingQuery = useQuery({
    queryKey: ['processing-methods', sample?.id],
    queryFn: () => fetchProcessingMethods({ sample_id: sample!.id, size: 200 }),
    enabled: open && Boolean(sample),
  });
  const characterizationQuery = useQuery({
    queryKey: ['characterizations', sample?.id],
    queryFn: () => fetchCharacterizations({ sample_id: sample!.id, size: 200 }),
    enabled: open && Boolean(sample),
  });
  const { data: characterizationTemplates = [] } = useQuery({
    queryKey: ['metadata-templates', projectId, 'characterization'],
    queryFn: () =>
      fetchMetadataTemplates({ project_id: projectId, entity_type: 'characterization' }),
    enabled: open,
  });
  const analysisQuery = useQuery({
    queryKey: ['analysis-results', selectedCharacterizationId],
    queryFn: () =>
      fetchAnalysisResults({
        characterization_id: selectedCharacterizationId!,
        size: 200,
      }),
    enabled: open && Boolean(selectedCharacterizationId),
  });

  const processingMethods = processingQuery.data?.items || [];
  const characterizations = characterizationQuery.data?.items || [];
  const analysisResults = analysisQuery.data?.items || [];
  const selectedTemplate = characterizationTemplates.find(
    (template) => template.id === selectedTemplateId
  );

  useEffect(() => {
    if (!open) {
      setSelectedCharacterizationId(undefined);
      setSelectedAnalysisIds([]);
      return;
    }
    if (
      selectedCharacterizationId &&
      characterizations.some((item) => item.id === selectedCharacterizationId)
    ) {
      return;
    }
    setSelectedCharacterizationId(characterizations[0]?.id);
    setSelectedAnalysisIds([]);
  }, [characterizations, open, selectedCharacterizationId]);

  useEffect(() => {
    setSelectedAnalysisIds([]);
  }, [selectedCharacterizationId]);

  const methodLabels = useMemo(
    () =>
      new Map(
        processingMethods.map((item) => [
          item.id,
          `${item.order_in_chain ?? '-'} · ${item.method_type}`,
        ])
      ),
    [processingMethods]
  );
  const selectedCharacterization = characterizations.find(
    (item) => item.id === selectedCharacterizationId
  );
  const comparisonResults = selectedAnalysisIds
    .map((id) => analysisResults.find((item) => item.id === id))
    .filter((item): item is AnalysisResult => Boolean(item));

  const refreshProcessingMethods = () =>
    queryClient.invalidateQueries({ queryKey: ['processing-methods', sample?.id] });
  const refreshCharacterizations = () =>
    queryClient.invalidateQueries({ queryKey: ['characterizations', sample?.id] });
  const refreshAnalysisResults = () =>
    queryClient.invalidateQueries({
      queryKey: ['analysis-results', selectedCharacterizationId],
    });

  const processingMutation = useMutation({
    mutationFn: createProcessingMethod,
    onSuccess: () => {
      refreshProcessingMethods();
      processingForm.resetFields();
      setProcessingOpen(false);
      message.success('制备步骤已登记');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '登记制备步骤失败'));
    },
  });
  const characterizationMutation = useMutation({
    mutationFn: createCharacterization,
    onSuccess: (created) => {
      refreshCharacterizations();
      characterizationForm.resetFields();
      setCharacterizationOpen(false);
      setSelectedCharacterizationId(created.id);
      message.success('表征记录已登记');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '登记表征记录失败'));
    },
  });
  const analysisMutation = useMutation({
    mutationFn: createAnalysisResult,
    onSuccess: () => {
      refreshAnalysisResults();
      analysisForm.resetFields();
      setAnalysisOpen(false);
      setSelectedAnalysisIds([]);
      message.success('分析结果新版本已保存');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '保存分析结果失败'));
    },
  });

  const handleCreateProcessing = async () => {
    if (!sample) return;
    const values = await processingForm.validateFields();
    try {
      processingMutation.mutate({
        sample_id: sample.id,
        method_type: values.method_type,
        equipment: values.equipment,
        description: values.description,
        order_in_chain: values.order_in_chain,
        parent_step_id: values.parent_step_id,
        parameters: parseJsonObject(values.parameters_json, '工艺参数'),
      });
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const handleCreateCharacterization = async () => {
    if (!sample) return;
    const values = await characterizationForm.validateFields();
    try {
      characterizationMutation.mutate({
        sample_id: sample.id,
        technique: values.technique,
        title: values.title,
        instrument: values.instrument,
        description: values.description,
        quality_flag: values.quality_flag,
        parameters: parseJsonObject(values.parameters_json, '表征参数'),
        metadata_template_id: values.metadata_template_id,
        metadata: values.metadata || {},
      });
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const handleCreateAnalysis = async () => {
    if (!selectedCharacterizationId) return;
    const values = await analysisForm.validateFields();
    try {
      analysisMutation.mutate({
        characterization_id: selectedCharacterizationId,
        analysis_type: values.analysis_type,
        pipeline_name: values.pipeline_name,
        model_name: values.model_name,
        model_version: values.model_version,
        processing_time_ms: values.processing_time_ms,
        gpu_used: values.gpu_used,
        result_data: parseJsonObject(values.result_data_json, '分析结果'),
        quality_metrics: parseJsonObject(values.quality_metrics_json, '质量指标'),
      });
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const processingColumns: ColumnsType<ProcessingMethod> = [
    {
      title: '顺序',
      dataIndex: 'order_in_chain',
      key: 'order_in_chain',
      width: 70,
      render: (value?: number) => value ?? '-',
    },
    { title: '工艺类型', dataIndex: 'method_type', key: 'method_type', width: 150 },
    {
      title: '参数',
      dataIndex: 'parameters',
      key: 'parameters',
      ellipsis: true,
      render: (value: Record<string, unknown>) => <Text code>{jsonPreview(value)}</Text>,
    },
    {
      title: '设备',
      dataIndex: 'equipment',
      key: 'equipment',
      width: 140,
      render: (value?: string) => value || '-',
    },
    {
      title: '上一步',
      dataIndex: 'parent_step_id',
      key: 'parent_step_id',
      width: 160,
      render: (value?: string) => (value && methodLabels.get(value)) || '-',
    },
    {
      title: '登记时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: formatDate,
    },
  ];

  const characterizationColumns: ColumnsType<Characterization> = [
    {
      title: '表征技术',
      dataIndex: 'technique',
      key: 'technique',
      width: 130,
      render: (value: string, row) => (
        <div>
          <div>{value}</div>
          {row.title && <Text type="secondary">{row.title}</Text>}
        </div>
      ),
    },
    {
      title: '仪器',
      dataIndex: 'instrument',
      key: 'instrument',
      render: (value?: string) => value || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: '质量',
      dataIndex: 'quality_flag',
      key: 'quality_flag',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'good' ? 'success' : value === 'bad' ? 'error' : 'warning'}>
          {value}
        </Tag>
      ),
    },
    {
      title: '登记时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: formatDate,
    },
  ];

  const analysisColumns: ColumnsType<AnalysisResult> = [
    {
      title: '分析类型',
      dataIndex: 'analysis_type',
      key: 'analysis_type',
      width: 140,
    },
    {
      title: '模型 / 版本',
      key: 'model',
      width: 180,
      render: (_, row) =>
        [row.model_name, row.model_version].filter(Boolean).join(' / ') || '-',
    },
    {
      title: '版本状态',
      dataIndex: 'is_latest',
      key: 'is_latest',
      width: 100,
      render: (value: boolean) =>
        value ? <Tag color="success">当前版本</Tag> : <Tag>历史版本</Tag>,
    },
    {
      title: '结果摘要',
      dataIndex: 'result_data',
      key: 'result_data',
      ellipsis: true,
      render: (value: Record<string, unknown>) => <Text code>{jsonPreview(value)}</Text>,
    },
    {
      title: '运行时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: formatDate,
    },
  ];

  const processingPanel = (
    <Card
      size="small"
      title={
        <Space>
          <ApartmentOutlined />
          制备工艺链
        </Space>
      }
      extra={
        canEdit ? (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setProcessingOpen(true)}>
            登记步骤
          </Button>
        ) : null
      }
    >
      <Table
        columns={processingColumns}
        dataSource={processingMethods}
        rowKey="id"
        loading={processingQuery.isLoading}
        pagination={false}
        scroll={{ x: 900 }}
        locale={{ emptyText: <Empty description="暂未登记制备步骤" /> }}
      />
    </Card>
  );

  const characterizationPanel = (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        size="small"
        title={
          <Space>
            <ExperimentOutlined />
            表征记录
          </Space>
        }
        extra={
          canEdit ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCharacterizationOpen(true)}
            >
              登记表征
            </Button>
          ) : null
        }
      >
        <Table
          columns={characterizationColumns}
          dataSource={characterizations}
          rowKey="id"
          loading={characterizationQuery.isLoading}
          pagination={false}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: selectedCharacterizationId ? [selectedCharacterizationId] : [],
            onChange: (keys) => setSelectedCharacterizationId(keys[0]?.toString()),
          }}
          locale={{ emptyText: <Empty description="暂未登记表征记录" /> }}
        />
      </Card>

      <Card
        size="small"
        title={
          selectedCharacterization
            ? `分析版本 · ${selectedCharacterization.technique}${
                selectedCharacterization.title ? ` / ${selectedCharacterization.title}` : ''
              }`
            : '分析版本'
        }
        extra={
          <Space>
            <Button
              icon={<DiffOutlined />}
              disabled={selectedAnalysisIds.length !== 2}
              onClick={() => setCompareOpen(true)}
            >
              对比所选版本
            </Button>
            {canEdit && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                disabled={!selectedCharacterizationId}
                onClick={() => setAnalysisOpen(true)}
              >
                新增分析版本
              </Button>
            )}
          </Space>
        }
      >
        {selectedCharacterizationId ? (
          <Table
            columns={analysisColumns}
            dataSource={analysisResults}
            rowKey="id"
            loading={analysisQuery.isLoading}
            pagination={false}
            rowSelection={{
              selectedRowKeys: selectedAnalysisIds,
              onChange: (keys) =>
                setSelectedAnalysisIds(keys.slice(-2).map((key) => key.toString())),
            }}
            scroll={{ x: 850 }}
            locale={{ emptyText: <Empty description="该表征尚无分析结果" /> }}
          />
        ) : (
          <Empty description="请先选择或登记一条表征记录" />
        )}
      </Card>

      {selectedCharacterizationId && (
        <AttachmentWorkbench
          parentType="characterization"
          parentId={selectedCharacterizationId}
          canEdit={canEdit}
          title="所选表征的原始数据与附件"
        />
      )}
    </Space>
  );

  return (
    <>
      <Drawer
        title={`样品研发链路${sample ? ` · ${sample.sample_code}` : ''}`}
        width={1100}
        open={open}
        onClose={onClose}
      >
        {sample && (
          <Paragraph type="secondary" style={{ marginTop: -8 }}>
            从样品制备、表征采集到分析结果版本，记录可追溯的研发过程。
          </Paragraph>
        )}
        <Tabs
          items={[
            {
              key: 'processing',
              label: `制备工艺 (${processingMethods.length})`,
              children: processingPanel,
            },
            {
              key: 'characterization',
              label: `表征与分析 (${characterizations.length})`,
              children: characterizationPanel,
            },
            {
              key: 'attachments',
              label: '样品附件',
              children: sample ? <AttachmentWorkbench parentType="sample" parentId={sample.id} canEdit={canEdit} /> : null,
            },
          ]}
        />
      </Drawer>

      <Modal
        title="登记制备步骤"
        open={processingOpen}
        onCancel={() => setProcessingOpen(false)}
        onOk={handleCreateProcessing}
        confirmLoading={processingMutation.isPending}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={processingForm}
          layout="vertical"
          initialValues={{ parameters_json: '{}', order_in_chain: processingMethods.length + 1 }}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="method_type"
            label="工艺类型"
            rules={[{ required: true, whitespace: true, message: '请输入工艺类型' }]}
          >
            <Input placeholder="例如：球磨、烧结、热处理" maxLength={100} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="equipment" label="设备">
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="order_in_chain" label="链路顺序">
                <InputNumber min={0} precision={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="parent_step_id" label="上一步">
            <Select
              allowClear
              options={processingMethods.map((item) => ({
                value: item.id,
                label: methodLabels.get(item.id),
              }))}
            />
          </Form.Item>
          <Form.Item name="parameters_json" label="工艺参数（JSON 对象）">
            <Input.TextArea rows={4} spellCheck={false} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="登记表征记录"
        open={characterizationOpen}
        onCancel={() => setCharacterizationOpen(false)}
        onOk={handleCreateCharacterization}
        confirmLoading={characterizationMutation.isPending}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={characterizationForm}
          layout="vertical"
          initialValues={{ parameters_json: '{}', quality_flag: 'good', metadata: {} }}
          style={{ marginTop: 16 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="technique"
                label="表征技术"
                rules={[{ required: true, whitespace: true, message: '请输入表征技术' }]}
              >
                <Input placeholder="例如：SEM、XRD、EDS" maxLength={100} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quality_flag" label="数据质量">
                <Select
                  options={[
                    { value: 'good', label: '良好' },
                    { value: 'warning', label: '需复核' },
                    { value: 'bad', label: '不可用' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="metadata_template_id" label="元数据模板">
            <Select
              allowClear
              placeholder="选择后将按模板校验扩展字段"
              options={characterizationTemplates.map((template) => ({
                value: template.id,
                label: template.name,
              }))}
              onChange={() => characterizationForm.setFieldValue('metadata', {})}
            />
          </Form.Item>
          <MetadataFields template={selectedTemplate} />
          <Form.Item name="title" label="记录标题">
            <Input maxLength={300} />
          </Form.Item>
          <Form.Item name="instrument" label="仪器">
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="parameters_json" label="采集参数（JSON 对象）">
            <Input.TextArea rows={4} spellCheck={false} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="新增分析结果版本"
        open={analysisOpen}
        onCancel={() => setAnalysisOpen(false)}
        onOk={handleCreateAnalysis}
        confirmLoading={analysisMutation.isPending}
        okText="保存版本"
        cancelText="取消"
        width={720}
      >
        <Form
          form={analysisForm}
          layout="vertical"
          initialValues={{ result_data_json: '{}', quality_metrics_json: '{}', gpu_used: false }}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="analysis_type"
            label="分析类型"
            rules={[{ required: true, whitespace: true, message: '请输入分析类型' }]}
            extra="同一表征下，同类型的新结果会自动成为当前版本，历史版本仍保留。"
          >
            <Input placeholder="例如：grain_segmentation" maxLength={100} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="pipeline_name" label="分析流程">
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="model_name" label="模型">
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="model_version" label="模型版本">
                <Input maxLength={100} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="result_data_json" label="分析结果（JSON 对象）">
            <Input.TextArea rows={6} spellCheck={false} />
          </Form.Item>
          <Form.Item name="quality_metrics_json" label="质量指标（JSON 对象）">
            <Input.TextArea rows={4} spellCheck={false} />
          </Form.Item>
          <Row gutter={16} align="middle">
            <Col span={12}>
              <Form.Item name="processing_time_ms" label="处理耗时（毫秒）">
                <InputNumber min={0} precision={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="gpu_used" label="使用 GPU" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      <Modal
        title="分析版本对比"
        open={compareOpen}
        onCancel={() => setCompareOpen(false)}
        footer={null}
        width={1000}
      >
        <Row gutter={16} style={{ marginTop: 16 }}>
          {comparisonResults.map((result) => (
            <Col span={12} key={result.id}>
              <Card
                size="small"
                title={`${result.analysis_type}${result.is_latest ? ' · 当前版本' : ' · 历史版本'}`}
              >
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="模型">
                    {[result.model_name, result.model_version].filter(Boolean).join(' / ') || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="分析流程">
                    {result.pipeline_name || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="运行时间">
                    {formatDate(result.created_at)}
                  </Descriptions.Item>
                </Descriptions>
                <Text strong>结果与质量指标</Text>
                <pre
                  style={{
                    maxHeight: 420,
                    overflow: 'auto',
                    marginTop: 8,
                    padding: 12,
                    background: '#f5f5f5',
                    borderRadius: 6,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(
                    {
                      result_data: result.result_data,
                      quality_metrics: result.quality_metrics,
                    },
                    null,
                    2
                  )}
                </pre>
              </Card>
            </Col>
          ))}
        </Row>
      </Modal>
    </>
  );
}
