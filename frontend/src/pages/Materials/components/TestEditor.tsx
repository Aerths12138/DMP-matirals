import { useState, useMemo } from 'react';
import {
  Card, Button, Table, Modal, Form, Input, DatePicker, Popconfirm, Space, Alert,
  message, Typography, Tag, InputNumber, Empty, Divider, Checkbox,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, SaveOutlined,
  CloseOutlined, ExperimentOutlined, MergeCellsOutlined,
  CheckSquareOutlined, BorderOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchTests, createTest, updateTest, deleteTest,
  updateMeasurement, deleteMeasurement,
  batchDeleteTests, batchMergeTests,
} from '../../../api/tests';
import type { Test, TestCreate, TestMeasurement, MeasurementCreate } from '../../../types/test';
import dayjs from 'dayjs';

const { Text } = Typography;

interface Props {
  materialId: string;
}

export default function TestEditor({ materialId }: Props) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTest, setEditingTest] = useState<Test | null>(null);
  const [form] = Form.useForm();
  const [conditions, setConditions] = useState<{ key: string; value: string }[]>([]);
  const [measRows, setMeasRows] = useState<Partial<MeasurementCreate>[]>([]);
  const [editingMeasId, setEditingMeasId] = useState<string | null>(null);
  const [editMeasForm, setEditMeasForm] = useState<Partial<MeasurementCreate>>({});

  // Batch selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [mergeModalOpen, setMergeModalOpen] = useState(false);
  const [mergeForm] = Form.useForm();

  const { data: testsData, isLoading } = useQuery({
    queryKey: ['tests', materialId],
    queryFn: () => fetchTests({ material_id: materialId, size: 500 }),
  });
  const tests = testsData?.items || [];

  const createMutation = useMutation({
    mutationFn: (body: TestCreate) => createTest(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success('测试已创建');
      closeModal();
    },
    onError: () => message.error('创建失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => updateTest(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success('测试已更新');
      closeModal();
    },
    onError: () => message.error('更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success('测试已删除');
    },
    onError: () => message.error('删除失败'),
  });

  // Batch mutations
  const batchDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => batchDeleteTests(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success(`已删除 ${selectedIds.size} 个测试`);
      setSelectedIds(new Set());
    },
    onError: () => message.error('批量删除失败'),
  });

  const batchMergeMutation = useMutation({
    mutationFn: (body: { test_ids: string[]; target_name?: string; target_method?: string }) =>
      batchMergeTests(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success(`已合并 ${selectedIds.size} 个测试`);
      setSelectedIds(new Set());
      setMergeModalOpen(false);
    },
    onError: () => message.error('合并失败'),
  });

  const updateMeasMutation = useMutation({
    mutationFn: ({ testId, measId, body }: { testId: string; measId: string; body: any }) =>
      updateMeasurement(testId, measId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success('测量值已更新');
      setEditingMeasId(null);
    },
    onError: () => message.error('更新失败'),
  });

  const deleteMeasMutation = useMutation({
    mutationFn: ({ testId, measId }: { testId: string; measId: string }) =>
      deleteMeasurement(testId, measId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests', materialId] });
      message.success('测量值已删除');
    },
    onError: () => message.error('删除失败'),
  });

  // Selection helpers
  const allSelected = tests.length > 0 && selectedIds.size === tests.length;
  const someSelected = selectedIds.size > 0;

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tests.map((t) => t.id)));
    }
  };

  const openNewModal = () => {
    setEditingTest(null);
    form.resetFields();
    setConditions([{ key: '', value: '' }]);
    setMeasRows([]);
    setModalOpen(true);
  };

  const openEditModal = (test: Test) => {
    setEditingTest(test);
    form.setFieldsValue({
      test_name: test.test_name,
      test_method: test.test_method,
      test_date: test.test_date ? dayjs(test.test_date) : undefined,
    });
    const conds = Object.entries(test.conditions || {}).map(([k, v]) => ({ key: k, value: v }));
    setConditions(conds.length > 0 ? conds : [{ key: '', value: '' }]);
    setMeasRows([]);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingTest(null);
    setConditions([]);
    setMeasRows([]);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const condDict: Record<string, string> = {};
    conditions.forEach((c) => {
      if (c.key.trim()) condDict[c.key.trim()] = c.value.trim();
    });

    const base = {
      test_name: values.test_name,
      test_method: values.test_method || undefined,
      test_date: values.test_date ? values.test_date.format('YYYY-MM-DD') : undefined,
      conditions: condDict,
      metadata: {},
      measurements: measRows.filter((m) => m.property_name?.trim()).map((m) => ({
        property_name: m.property_name!,
        value_number: m.value_number,
        value_text: m.value_text,
        unit: m.unit,
      })),
    };

    if (editingTest) {
      updateMutation.mutate({ id: editingTest.id, body: base });
    } else {
      createMutation.mutate({ ...base, material_id: materialId } as TestCreate);
    }
  };

  const addCondition = () => setConditions([...conditions, { key: '', value: '' }]);
  const removeCondition = (i: number) => setConditions(conditions.filter((_, idx) => idx !== i));
  const updateCondition = (i: number, field: 'key' | 'value', val: string) => {
    const updated = [...conditions];
    updated[i][field] = val;
    setConditions(updated);
  };

  // Measurement inline editing
  const startEditMeas = (m: TestMeasurement) => {
    setEditingMeasId(m.id);
    setEditMeasForm({
      property_name: m.property_name,
      value_number: m.value_number,
      value_text: m.value_text,
      unit: m.unit,
    });
  };

  const saveEditMeas = (testId: string) => {
    if (!editingMeasId) return;
    updateMeasMutation.mutate({
      testId,
      measId: editingMeasId,
      body: editMeasForm,
    });
  };

  // Batch merge handler
  const handleBatchMerge = async () => {
    const values = await mergeForm.validateFields();
    batchMergeMutation.mutate({
      test_ids: Array.from(selectedIds),
      target_name: values.target_name || undefined,
      target_method: values.target_method || undefined,
    });
  };

  const measurementColumns = (testId: string) => [
    {
      title: '属性名',
      dataIndex: 'property_name',
      key: 'name',
      width: 140,
      render: (_: string, record: TestMeasurement) => {
        if (editingMeasId === record.id) {
          return (
            <Input
              value={editMeasForm.property_name}
              onChange={(e) => setEditMeasForm({ ...editMeasForm, property_name: e.target.value })}
              size="small"
            />
          );
        }
        return <Text strong>{record.property_name}</Text>;
      },
    },
    {
      title: '数值',
      dataIndex: 'value_number',
      key: 'value',
      width: 120,
      render: (_: unknown, record: TestMeasurement) => {
        if (editingMeasId === record.id) {
          return (
            <InputNumber
              value={editMeasForm.value_number}
              onChange={(v) => setEditMeasForm({ ...editMeasForm, value_number: v ?? undefined })}
              size="small"
              style={{ width: '100%' }}
            />
          );
        }
        return record.value_number != null ? record.value_number : (record.value_text || '-');
      },
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 80,
      render: (_: string, record: TestMeasurement) => {
        if (editingMeasId === record.id) {
          return (
            <Input
              value={editMeasForm.unit}
              onChange={(e) => setEditMeasForm({ ...editMeasForm, unit: e.target.value })}
              size="small"
            />
          );
        }
        return record.unit || '-';
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: TestMeasurement) => {
        if (editingMeasId === record.id) {
          return (
            <Space size="small">
              <Button type="link" size="small" icon={<SaveOutlined />} onClick={() => saveEditMeas(testId)} loading={updateMeasMutation.isPending} />
              <Button type="link" size="small" icon={<CloseOutlined />} onClick={() => setEditingMeasId(null)} />
            </Space>
          );
        }
        return (
          <Space size="small">
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => startEditMeas(record)} disabled={editingMeasId !== null} />
            <Popconfirm title="删除此测量值？" onConfirm={() => deleteMeasMutation.mutate({ testId, measId: record.id })}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />} disabled={editingMeasId !== null} />
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={openNewModal}>
            新建测试
          </Button>
          {tests.length > 0 && (
            <Button
              icon={allSelected ? <BorderOutlined /> : <CheckSquareOutlined />}
              onClick={toggleSelectAll}
              size="small"
            >
              {allSelected ? '取消全选' : '全选'}
            </Button>
          )}
        </Space>

        {/* Batch action bar — visible when items are selected */}
        {someSelected && (
          <Space>
            <Text type="secondary">已选 {selectedIds.size} 项</Text>
            <Popconfirm
              title={`确定删除选中的 ${selectedIds.size} 个测试及其全部测量数据？`}
              onConfirm={() => batchDeleteMutation.mutate(Array.from(selectedIds))}
              okText="确认删除"
              cancelText="取消"
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                loading={batchDeleteMutation.isPending}
              >
                批量删除
              </Button>
            </Popconfirm>
            <Button
              icon={<MergeCellsOutlined />}
              onClick={() => {
                mergeForm.resetFields();
                setMergeModalOpen(true);
              }}
              disabled={selectedIds.size < 2}
              title={selectedIds.size < 2 ? '至少选择 2 个测试才能合并' : '合并选中的测试'}
            >
              合并为一项
            </Button>
          </Space>
        )}
      </div>

      {/* Test card list */}
      {tests.length === 0 && !isLoading ? (
        <Empty description="暂无测试数据，点击上方按钮创建" />
      ) : (
        tests.map((test) => (
          <Card
            key={test.id}
            style={{ marginBottom: 16 }}
            title={
              <Space>
                <Checkbox
                  checked={selectedIds.has(test.id)}
                  onChange={() => toggleSelect(test.id)}
                />
                <ExperimentOutlined />
                <Text strong>{test.test_name}</Text>
                {test.test_method && <Tag color="blue">{test.test_method}</Tag>}
              </Space>
            }
            extra={
              <Space>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(test)}>编辑</Button>
                <Popconfirm title="确定删除此测试？" onConfirm={() => deleteMutation.mutate(test.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            }
          >
            {/* Conditions */}
            {Object.keys(test.conditions || {}).length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <Text type="secondary">条件：</Text>
                {Object.entries(test.conditions).map(([k, v]) => (
                  <Tag key={k} style={{ marginBottom: 4 }}>{k}={v}</Tag>
                ))}
              </div>
            )}

            <Divider style={{ margin: '8px 0' }} />

            {/* Measurements table */}
            <Table
              columns={measurementColumns(test.id)}
              dataSource={test.measurements?.map((m) => ({ ...m, key: m.id })) || []}
              pagination={false}
              size="small"
              locale={{ emptyText: '暂无测量数据' }}
            />
          </Card>
        ))
      )}

      {/* Create/Edit Modal */}
      <Modal
        title={editingTest ? '编辑测试' : '新建测试'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={700}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="test_name" label="测试名称" rules={[{ required: true, message: '请输入测试名称' }]}>
            <Input placeholder="如：介电性能测试" />
          </Form.Item>
          <Space size="middle">
            <Form.Item name="test_method" label="测试方法">
              <Input placeholder="如：ASTM D150" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="test_date" label="测试日期">
              <DatePicker style={{ width: 200 }} />
            </Form.Item>
          </Space>

          {/* Conditions editor */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong>测试条件</Text>
              <Button size="small" icon={<PlusOutlined />} onClick={addCondition}>添加条件</Button>
            </div>
            {conditions.map((c, i) => (
              <Space key={i} style={{ marginBottom: 8 }}>
                <Input
                  placeholder="条件名"
                  value={c.key}
                  onChange={(e) => updateCondition(i, 'key', e.target.value)}
                  style={{ width: 160 }}
                />
                <Input
                  placeholder="条件值"
                  value={c.value}
                  onChange={(e) => updateCondition(i, 'value', e.target.value)}
                  style={{ width: 200 }}
                />
                {conditions.length > 1 && (
                  <Button type="link" danger icon={<DeleteOutlined />} onClick={() => removeCondition(i)} />
                )}
              </Space>
            ))}
          </div>

          {/* Measurements in modal (for new tests) */}
          {!editingTest && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Text strong>测量结果（可选）</Text>
                <Button size="small" icon={<PlusOutlined />} onClick={() => setMeasRows([...measRows, {}])}>添加</Button>
              </div>
              {measRows.map((m, i) => (
                <Space key={i} style={{ marginBottom: 8 }}>
                  <Input
                    placeholder="属性名"
                    value={m.property_name || ''}
                    onChange={(e) => {
                      const rows = [...measRows];
                      rows[i] = { ...rows[i], property_name: e.target.value };
                      setMeasRows(rows);
                    }}
                    style={{ width: 140 }}
                  />
                  <InputNumber
                    placeholder="数值"
                    value={m.value_number}
                    onChange={(v) => {
                      const rows = [...measRows];
                      rows[i] = { ...rows[i], value_number: v ?? undefined };
                      setMeasRows(rows);
                    }}
                    style={{ width: 100 }}
                  />
                  <Input
                    placeholder="单位"
                    value={m.unit || ''}
                    onChange={(e) => {
                      const rows = [...measRows];
                      rows[i] = { ...rows[i], unit: e.target.value };
                      setMeasRows(rows);
                    }}
                    style={{ width: 80 }}
                  />
                  <Button type="link" danger icon={<DeleteOutlined />} onClick={() => setMeasRows(measRows.filter((_, idx) => idx !== i))} />
                </Space>
              ))}
            </div>
          )}
        </Form>
      </Modal>

      {/* Merge Modal */}
      <Modal
        title={`合并 ${selectedIds.size} 个测试`}
        open={mergeModalOpen}
        onCancel={() => setMergeModalOpen(false)}
        onOk={handleBatchMerge}
        confirmLoading={batchMergeMutation.isPending}
        okText="确认合并"
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="合并操作会将选中测试的测量数据全部归入第一个测试，不同名的条件会被合并，其他测试将被删除。"
        />
        <Form form={mergeForm} layout="vertical">
          <Form.Item name="target_name" label="合并后的测试名称（留空则保留第一个测试的名称）">
            <Input placeholder="如：综合测试结果" />
          </Form.Item>
          <Form.Item name="target_method" label="合并后的测试方法（可选）">
            <Input placeholder="如：综合" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
