import { useState } from 'react';
import {
  Button,
  Col,
  Drawer,
  Empty,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
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
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createMetadataTemplate,
  createUnitDefinition,
  fetchMetadataTemplates,
  fetchUnitDefinitions,
  updateMetadataTemplate,
} from '../../api/dataStandards';
import type {
  MetadataEntityType,
  MetadataTemplate,
  MetadataValueType,
  UnitDefinition,
} from '../../types/dataStandard';

const { Paragraph, Text } = Typography;

interface DataStandardsDrawerProps {
  open: boolean;
  projectId: string;
  canEdit: boolean;
  onClose: () => void;
}

interface TemplateFieldForm {
  key: string;
  label: string;
  value_type: MetadataValueType;
  required?: boolean;
  unit?: string;
  options_text?: string;
  description?: string;
}

interface TemplateFormValues {
  name: string;
  entity_type: MetadataEntityType;
  description?: string;
  fields: TemplateFieldForm[];
}

interface UnitFormValues {
  symbol: string;
  name: string;
  quantity_type: string;
  description?: string;
}

function getErrorMessage(error: unknown, fallback: string) {
  const responseError = error as { response?: { data?: { detail?: string } } };
  return responseError.response?.data?.detail || fallback;
}

export default function DataStandardsDrawer({
  open,
  projectId,
  canEdit,
  onClose,
}: DataStandardsDrawerProps) {
  const queryClient = useQueryClient();
  const [templateOpen, setTemplateOpen] = useState(false);
  const [unitOpen, setUnitOpen] = useState(false);
  const [templateForm] = Form.useForm<TemplateFormValues>();
  const [unitForm] = Form.useForm<UnitFormValues>();

  const templatesQuery = useQuery({
    queryKey: ['metadata-templates', projectId],
    queryFn: () => fetchMetadataTemplates({ project_id: projectId, active_only: false }),
    enabled: open,
  });
  const unitsQuery = useQuery({
    queryKey: ['unit-definitions', projectId],
    queryFn: () => fetchUnitDefinitions(projectId),
    enabled: open,
  });

  const templates = templatesQuery.data || [];
  const units = unitsQuery.data || [];
  const unitOptions = units.map((unit) => ({
    value: unit.symbol,
    label: `${unit.symbol} · ${unit.name}`,
  }));

  const refreshTemplates = () =>
    queryClient.invalidateQueries({ queryKey: ['metadata-templates', projectId] });
  const refreshUnits = () =>
    queryClient.invalidateQueries({ queryKey: ['unit-definitions', projectId] });

  const templateMutation = useMutation({
    mutationFn: createMetadataTemplate,
    onSuccess: () => {
      refreshTemplates();
      templateForm.resetFields();
      setTemplateOpen(false);
      message.success('元数据模板已创建');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '创建元数据模板失败'));
    },
  });
  const templateStatusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateMetadataTemplate(id, { is_active }),
    onSuccess: () => {
      refreshTemplates();
      message.success('模板状态已更新');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '更新模板状态失败'));
    },
  });
  const unitMutation = useMutation({
    mutationFn: createUnitDefinition,
    onSuccess: () => {
      refreshUnits();
      unitForm.resetFields();
      setUnitOpen(false);
      message.success('自定义单位已添加');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '添加自定义单位失败'));
    },
  });

  const handleCreateTemplate = async () => {
    const values = await templateForm.validateFields();
    templateMutation.mutate({
      project_id: projectId,
      name: values.name,
      entity_type: values.entity_type,
      description: values.description,
      fields: (values.fields || []).map((field) => ({
        key: field.key,
        label: field.label,
        value_type: field.value_type,
        required: Boolean(field.required),
        unit: field.unit || undefined,
        options: (field.options_text || '')
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
        description: field.description,
      })),
    });
  };

  const handleCreateUnit = async () => {
    const values = await unitForm.validateFields();
    unitMutation.mutate({ project_id: projectId, ...values });
  };

  const templateColumns: ColumnsType<MetadataTemplate> = [
    {
      title: '模板名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, row) => (
        <div>
          <div>{name}</div>
          {row.description && <Text type="secondary">{row.description}</Text>}
        </div>
      ),
    },
    {
      title: '适用对象',
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 120,
      render: (value: MetadataEntityType) => (value === 'sample' ? '样品' : '表征'),
    },
    {
      title: '字段',
      dataIndex: 'fields',
      key: 'fields',
      width: 80,
      render: (fields: MetadataTemplate['fields']) => fields.length,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (value: boolean) =>
        value ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, row) =>
        canEdit ? (
          <Popconfirm
            title={row.is_active ? '停用后新记录将不能选择此模板，确定吗？' : '确定重新启用吗？'}
            onConfirm={() =>
              templateStatusMutation.mutate({ id: row.id, is_active: !row.is_active })
            }
          >
            <Button type="link">{row.is_active ? '停用' : '启用'}</Button>
          </Popconfirm>
        ) : (
          '-'
        ),
    },
  ];

  const unitColumns: ColumnsType<UnitDefinition> = [
    { title: '符号', dataIndex: 'symbol', key: 'symbol', width: 130 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '物理量', dataIndex: 'quantity_type', key: 'quantity_type', width: 160 },
    {
      title: '来源',
      dataIndex: 'is_builtin',
      key: 'is_builtin',
      width: 100,
      render: (value: boolean) =>
        value ? <Tag color="blue">平台标准</Tag> : <Tag color="purple">项目自定义</Tag>,
    },
  ];

  return (
    <>
      <Drawer title="项目数据标准" width={1050} open={open} onClose={onClose}>
        <Paragraph type="secondary">
          模板用于约束元数据字段、类型、必填项和受控枚举；单位仅定义规范表达，不自动换算原始数值。
        </Paragraph>
        <Tabs
          items={[
            {
              key: 'templates',
              label: `元数据模板 (${templates.length})`,
              children: (
                <>
                  {canEdit && (
                    <div style={{ textAlign: 'right', marginBottom: 12 }}>
                      <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={() => {
                          templateForm.setFieldsValue({ entity_type: 'sample', fields: [] });
                          setTemplateOpen(true);
                        }}
                      >
                        新建模板
                      </Button>
                    </div>
                  )}
                  <Table
                    columns={templateColumns}
                    dataSource={templates}
                    rowKey="id"
                    loading={templatesQuery.isLoading}
                    pagination={false}
                    locale={{ emptyText: <Empty description="暂无元数据模板" /> }}
                  />
                </>
              ),
            },
            {
              key: 'units',
              label: `单位字典 (${units.length})`,
              children: (
                <>
                  {canEdit && (
                    <div style={{ textAlign: 'right', marginBottom: 12 }}>
                      <Button type="primary" icon={<PlusOutlined />} onClick={() => setUnitOpen(true)}>
                        添加自定义单位
                      </Button>
                    </div>
                  )}
                  <Table
                    columns={unitColumns}
                    dataSource={units}
                    rowKey="id"
                    loading={unitsQuery.isLoading}
                    pagination={{ pageSize: 12, hideOnSinglePage: true }}
                  />
                </>
              ),
            },
          ]}
        />
      </Drawer>

      <Modal
        title="新建元数据模板"
        open={templateOpen}
        onCancel={() => setTemplateOpen(false)}
        onOk={handleCreateTemplate}
        confirmLoading={templateMutation.isPending}
        okText="创建"
        cancelText="取消"
        width={1100}
      >
        <Form form={templateForm} layout="vertical" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="模板名称"
                rules={[{ required: true, whitespace: true, message: '请输入模板名称' }]}
              >
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="entity_type"
                label="适用对象"
                rules={[{ required: true, message: '请选择适用对象' }]}
              >
                <Select
                  options={[
                    { value: 'sample', label: '样品' },
                    { value: 'characterization', label: '表征记录' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="模板说明">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.List name="fields">
            {(fields, { add, remove }) => (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Text strong>字段定义</Text>
                {fields.map(({ key, name, ...restField }) => (
                  <Row key={key} gutter={8} align="middle">
                    <Col span={4}>
                      <Form.Item
                        {...restField}
                        name={[name, 'key']}
                        rules={[
                          { required: true, message: '请输入字段键' },
                          { pattern: /^[A-Za-z][A-Za-z0-9_]*$/, message: '使用英文字母、数字和下划线' },
                        ]}
                      >
                        <Input placeholder="字段键" />
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item
                        {...restField}
                        name={[name, 'label']}
                        rules={[{ required: true, message: '请输入显示名称' }]}
                      >
                        <Input placeholder="显示名称" />
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item
                        {...restField}
                        name={[name, 'value_type']}
                        rules={[{ required: true, message: '请选择类型' }]}
                      >
                        <Select
                          placeholder="字段类型"
                          options={[
                            { value: 'string', label: '文本' },
                            { value: 'number', label: '小数' },
                            { value: 'integer', label: '整数' },
                            { value: 'boolean', label: '布尔值' },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item {...restField} name={[name, 'unit']}>
                        <Select allowClear showSearch optionFilterProp="label" placeholder="数值单位" options={unitOptions} />
                      </Form.Item>
                    </Col>
                    <Col span={5}>
                      <Form.Item {...restField} name={[name, 'options_text']}>
                        <Input placeholder="文本枚举，用逗号分隔" />
                      </Form.Item>
                    </Col>
                    <Col span={2}>
                      <Form.Item {...restField} name={[name, 'required']} valuePropName="checked">
                        <Switch checkedChildren="必填" unCheckedChildren="选填" />
                      </Form.Item>
                    </Col>
                    <Col span={1}>
                      <Button danger type="text" icon={<DeleteOutlined />} onClick={() => remove(name)} />
                    </Col>
                  </Row>
                ))}
                <Button
                  type="dashed"
                  block
                  icon={<PlusOutlined />}
                  onClick={() => add({ value_type: 'string', required: false })}
                >
                  添加字段
                </Button>
              </Space>
            )}
          </Form.List>
        </Form>
      </Modal>

      <Modal
        title="添加自定义单位"
        open={unitOpen}
        onCancel={() => setUnitOpen(false)}
        onOk={handleCreateUnit}
        confirmLoading={unitMutation.isPending}
        okText="添加"
        cancelText="取消"
      >
        <Form form={unitForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="symbol"
            label="单位符号"
            rules={[{ required: true, whitespace: true, message: '请输入单位符号' }]}
          >
            <Input placeholder="例如：rpm" maxLength={50} />
          </Form.Item>
          <Form.Item
            name="name"
            label="单位名称"
            rules={[{ required: true, whitespace: true, message: '请输入单位名称' }]}
          >
            <Input placeholder="例如：转每分钟" maxLength={100} />
          </Form.Item>
          <Form.Item
            name="quantity_type"
            label="物理量"
            rules={[{ required: true, whitespace: true, message: '请输入物理量' }]}
          >
            <Input placeholder="例如：转速" maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
