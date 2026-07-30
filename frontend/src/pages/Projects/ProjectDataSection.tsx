import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DatabaseOutlined, ExperimentOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createExperiment,
  fetchExperiments,
  updateExperiment,
} from '../../api/experiments';
import { fetchMetadataTemplates } from '../../api/dataStandards';
import { fetchMaterials } from '../../api/materials';
import { createSample, fetchSamples, updateSample } from '../../api/samples';
import type { Material } from '../../types/material';
import type {
  Experiment,
  ExperimentCreate,
  ExperimentStatus,
  Sample,
  SampleCreate,
  SampleStatus,
} from '../../types/experiment';
import MetadataFields from './MetadataFields';
import SampleLineageDrawer from './SampleLineageDrawer';

const { Text } = Typography;

const EXPERIMENT_STATUS_OPTIONS = [
  { value: 'planned', label: '计划中' },
  { value: 'running', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '未达预期' },
];

const EXPERIMENT_STATUS_LABELS: Record<
  ExperimentStatus,
  { color: string; text: string }
> = {
  planned: { color: 'default', text: '计划中' },
  running: { color: 'processing', text: '进行中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '未达预期' },
};

const SAMPLE_STATUS_OPTIONS = [
  { value: 'created', label: '已创建' },
  { value: 'processing', label: '制备中' },
  { value: 'characterizing', label: '表征中' },
  { value: 'archived', label: '已归档' },
];

const SAMPLE_STATUS_LABELS: Record<
  SampleStatus,
  { color: string; text: string }
> = {
  created: { color: 'default', text: '已创建' },
  processing: { color: 'processing', text: '制备中' },
  characterizing: { color: 'purple', text: '表征中' },
  archived: { color: 'success', text: '已归档' },
};

const FORM_OPTIONS = [
  { value: 'powder', label: '粉末' },
  { value: 'pellet', label: '压片' },
  { value: 'film', label: '薄膜' },
  { value: 'fiber', label: '纤维' },
  { value: 'bulk', label: '块体' },
  { value: 'liquid', label: '液体' },
];

interface ProjectDataSectionProps {
  projectId: string;
  canEdit: boolean;
}

export default function ProjectDataSection({
  projectId,
  canEdit,
}: ProjectDataSectionProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [experimentOpen, setExperimentOpen] = useState(false);
  const [sampleOpen, setSampleOpen] = useState(false);
  const [lineageSample, setLineageSample] = useState<Sample | null>(null);
  const [experimentForm] = Form.useForm<ExperimentCreate>();
  const [sampleForm] = Form.useForm<SampleCreate>();
  const selectedSampleTemplateId = Form.useWatch('metadata_template_id', sampleForm);

  const { data: materialData, isLoading: materialsLoading } = useQuery({
    queryKey: ['project-materials', projectId],
    queryFn: () => fetchMaterials({ project_id: projectId, size: 200 }),
  });
  const { data: experimentData, isLoading: experimentsLoading } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => fetchExperiments({ project_id: projectId, size: 200 }),
  });
  const { data: sampleData, isLoading: samplesLoading } = useQuery({
    queryKey: ['samples', projectId],
    queryFn: () => fetchSamples({ project_id: projectId, size: 200 }),
  });
  const { data: sampleTemplates = [] } = useQuery({
    queryKey: ['metadata-templates', projectId, 'sample'],
    queryFn: () =>
      fetchMetadataTemplates({ project_id: projectId, entity_type: 'sample' }),
  });

  const materials = materialData?.items || [];
  const experiments = experimentData?.items || [];
  const samples = sampleData?.items || [];
  const selectedSampleTemplate = sampleTemplates.find(
    (template) => template.id === selectedSampleTemplateId
  );
  const experimentNames = useMemo(
    () => new Map(experiments.map((experiment) => [experiment.id, experiment.name])),
    [experiments]
  );
  const sampleCounts = useMemo(() => {
    const counts = new Map<string, number>();
    samples.forEach((sample) => {
      if (sample.experiment_id) {
        counts.set(sample.experiment_id, (counts.get(sample.experiment_id) || 0) + 1);
      }
    });
    return counts;
  }, [samples]);

  const refreshExperiments = () => {
    queryClient.invalidateQueries({ queryKey: ['experiments', projectId] });
  };
  const refreshSamples = () => {
    queryClient.invalidateQueries({ queryKey: ['samples', projectId] });
  };

  const createExperimentMutation = useMutation({
    mutationFn: createExperiment,
    onSuccess: () => {
      refreshExperiments();
      experimentForm.resetFields();
      setExperimentOpen(false);
      message.success('实验已创建');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '创建实验失败');
    },
  });

  const updateExperimentMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ExperimentStatus }) =>
      updateExperiment(id, { status }),
    onSuccess: () => {
      refreshExperiments();
      message.success('实验状态已更新');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '更新实验失败');
    },
  });

  const createSampleMutation = useMutation({
    mutationFn: createSample,
    onSuccess: () => {
      refreshSamples();
      sampleForm.resetFields();
      setSampleOpen(false);
      message.success('样品已创建');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '创建样品失败');
    },
  });

  const updateSampleMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: SampleStatus }) =>
      updateSample(id, { status }),
    onSuccess: () => {
      refreshSamples();
      message.success('样品状态已更新');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '更新样品失败');
    },
  });

  const handleCreateExperiment = async () => {
    const values = await experimentForm.validateFields();
    createExperimentMutation.mutate({
      ...values,
      project_id: projectId,
      status: 'planned',
    });
  };

  const handleCreateSample = async () => {
    const values = await sampleForm.validateFields();
    createSampleMutation.mutate({
      ...values,
      status: 'created',
      dimensions: {},
    });
  };

  const materialColumns: ColumnsType<Material> = [
    {
      title: '材料名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, material) => (
        <Button
          type="link"
          style={{ padding: 0 }}
          onClick={() => navigate(`/materials/${material.id}`)}
        >
          {name}
        </Button>
      ),
    },
    {
      title: '材料类型',
      dataIndex: 'material_type',
      key: 'material_type',
      width: 140,
    },
    {
      title: '化学式',
      dataIndex: 'formula_string',
      key: 'formula_string',
      render: (value?: string) => value || '-',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 130,
      render: (value: string) => new Date(value).toLocaleDateString('zh-CN'),
    },
  ];

  const experimentColumns: ColumnsType<Experiment> = [
    {
      title: '实验名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, experiment) => (
        <div>
          <div>{name}</div>
          {experiment.description && (
            <Text type="secondary" ellipsis style={{ maxWidth: 360 }}>
              {experiment.description}
            </Text>
          )}
        </div>
      ),
    },
    {
      title: '研究假设',
      dataIndex: 'hypothesis',
      key: 'hypothesis',
      ellipsis: true,
      render: (value?: string) => value || '-',
    },
    {
      title: '样品',
      key: 'sample_count',
      width: 80,
      align: 'center',
      render: (_, experiment) => sampleCounts.get(experiment.id) || 0,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (status: ExperimentStatus, experiment) => {
        if (canEdit) {
          return (
            <Select
              size="small"
              value={status}
              options={EXPERIMENT_STATUS_OPTIONS}
              style={{ width: 100 }}
              onChange={(nextStatus: ExperimentStatus) =>
                updateExperimentMutation.mutate({
                  id: experiment.id,
                  status: nextStatus,
                })
              }
            />
          );
        }
        const label = EXPERIMENT_STATUS_LABELS[status];
        return <Tag color={label.color}>{label.text}</Tag>;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 130,
      render: (value: string) => new Date(value).toLocaleDateString('zh-CN'),
    },
  ];

  const sampleColumns: ColumnsType<Sample> = [
    {
      title: '样品编号',
      dataIndex: 'sample_code',
      key: 'sample_code',
    },
    {
      title: '所属实验',
      dataIndex: 'experiment_id',
      key: 'experiment_id',
      render: (experimentId?: string) =>
        (experimentId && experimentNames.get(experimentId)) || '-',
    },
    {
      title: '批次',
      dataIndex: 'batch_number',
      key: 'batch_number',
      width: 110,
      render: (value?: string) => value || '-',
    },
    {
      title: '形态',
      dataIndex: 'form',
      key: 'form',
      width: 90,
      render: (value?: string) =>
        FORM_OPTIONS.find((option) => option.value === value)?.label || value || '-',
    },
    {
      title: '质量 (g)',
      dataIndex: 'mass_g',
      key: 'mass_g',
      width: 100,
      render: (value?: number) => value ?? '-',
    },
    {
      title: '存放位置',
      dataIndex: 'storage_location',
      key: 'storage_location',
      render: (value?: string) => value || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (status: SampleStatus, sample) => {
        if (canEdit) {
          return (
            <Select
              size="small"
              value={status}
              options={SAMPLE_STATUS_OPTIONS}
              style={{ width: 100 }}
              onChange={(nextStatus: SampleStatus) =>
                updateSampleMutation.mutate({ id: sample.id, status: nextStatus })
              }
            />
          );
        }
        const label = SAMPLE_STATUS_LABELS[status];
        return <Tag color={label.color}>{label.text}</Tag>;
      },
    },
    {
      title: '研发链路',
      key: 'lineage',
      width: 100,
      fixed: 'right',
      render: (_, sample) => (
        <Button type="link" onClick={() => setLineageSample(sample)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <>
      <Card
        title={
          <Space>
            <DatabaseOutlined />
            项目材料
          </Space>
        }
        extra={
          canEdit ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate(`/materials/new?project_id=${projectId}`)}
            >
              新建材料
            </Button>
          ) : null
        }
        style={{ marginBottom: 16 }}
      >
        <Table
          columns={materialColumns}
          dataSource={materials}
          rowKey="id"
          loading={materialsLoading}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无项目材料" /> }}
        />
      </Card>

      <Card
        title={
          <Space>
            <ExperimentOutlined />
            实验记录
          </Space>
        }
        extra={
          canEdit ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setExperimentOpen(true)}
            >
              新建实验
            </Button>
          ) : null
        }
        style={{ marginBottom: 16 }}
      >
        <Table
          columns={experimentColumns}
          dataSource={experiments}
          rowKey="id"
          loading={experimentsLoading}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无实验记录" /> }}
        />
      </Card>

      <Card
        title="样品台账"
        extra={
          canEdit ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              disabled={!experiments.length}
              onClick={() => setSampleOpen(true)}
            >
              新建样品
            </Button>
          ) : null
        }
        style={{ marginBottom: 16 }}
      >
        <Table
          columns={sampleColumns}
          dataSource={samples}
          rowKey="id"
          loading={samplesLoading}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                description={
                  experiments.length ? '暂无样品' : '请先创建实验，再登记样品'
                }
              />
            ),
          }}
          scroll={{ x: 900 }}
        />
      </Card>

      <Modal
        title="新建实验"
        open={experimentOpen}
        onCancel={() => setExperimentOpen(false)}
        onOk={handleCreateExperiment}
        confirmLoading={createExperimentMutation.isPending}
        okText="创建"
        cancelText="取消"
      >
        <Form form={experimentForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="实验名称"
            rules={[{ required: true, whitespace: true, message: '请输入实验名称' }]}
          >
            <Input maxLength={300} placeholder="例如：不同烧结温度对电导率的影响" />
          </Form.Item>
          <Form.Item name="hypothesis" label="研究假设">
            <Input.TextArea rows={3} placeholder="描述本次实验要验证的假设" />
          </Form.Item>
          <Form.Item name="description" label="实验说明">
            <Input.TextArea rows={3} placeholder="补充实验条件、范围或注意事项" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="登记样品"
        open={sampleOpen}
        onCancel={() => setSampleOpen(false)}
        onOk={handleCreateSample}
        confirmLoading={createSampleMutation.isPending}
        okText="创建"
        cancelText="取消"
      >
        <Form form={sampleForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="experiment_id"
            label="所属实验"
            rules={[{ required: true, message: '请选择所属实验' }]}
          >
            <Select
              options={experiments.map((experiment) => ({
                value: experiment.id,
                label: experiment.name,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="sample_code"
            label="样品编号"
            rules={[{ required: true, whitespace: true, message: '请输入样品编号' }]}
          >
            <Input maxLength={200} placeholder="例如：S-2026-001" />
          </Form.Item>
          <Form.Item name="metadata_template_id" label="元数据模板">
            <Select
              allowClear
              placeholder="选择后将按模板校验扩展字段"
              options={sampleTemplates.map((template) => ({
                value: template.id,
                label: template.name,
              }))}
              onChange={() => sampleForm.setFieldValue('metadata', {})}
            />
          </Form.Item>
          <MetadataFields template={selectedSampleTemplate} />
          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="batch_number" label="批次号" style={{ flex: 1 }}>
              <Input maxLength={100} />
            </Form.Item>
            <Form.Item name="form" label="样品形态" style={{ flex: 1 }}>
              <Select allowClear options={FORM_OPTIONS} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="mass_g" label="质量 (g)" style={{ flex: 1 }}>
              <InputNumber min={0} precision={6} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="storage_location"
              label="存放位置"
              style={{ flex: 1 }}
            >
              <Input maxLength={200} placeholder="例如：A柜-2层" />
            </Form.Item>
          </Space>
          <Form.Item name="description" label="样品说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <SampleLineageDrawer
        open={Boolean(lineageSample)}
        sample={lineageSample}
        projectId={projectId}
        canEdit={canEdit}
        onClose={() => setLineageSample(null)}
      />
    </>
  );
}
