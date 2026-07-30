import { useState, useEffect } from 'react';
import { Table, Button, AutoComplete, InputNumber, Input, Popconfirm, Space, message, Typography } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchProperties,
  createProperty,
  updateProperty,
  deleteProperty,
  fetchPropertyNames,
} from '../../../api/properties';
import type { Property, PropertyCreate } from '../../../types/property';

const { Text } = Typography;

interface Props {
  materialId: string;
}

export default function PropertyEditor({ materialId }: Props) {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [newRow, setNewRow] = useState(false);
  const [editForm, setEditForm] = useState<Partial<PropertyCreate>>({});

  // Fetch existing properties
  const { data: properties, isLoading } = useQuery({
    queryKey: ['properties', materialId],
    queryFn: () => fetchProperties(materialId),
  });

  // Fetch property name suggestions
  const { data: nameSuggestions = [] } = useQuery({
    queryKey: ['propertyNames'],
    queryFn: fetchPropertyNames,
  });

  const createMutation = useMutation({
    mutationFn: (body: PropertyCreate) => createProperty(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties', materialId] });
      queryClient.invalidateQueries({ queryKey: ['propertyNames'] });
      message.success('属性已添加');
      setNewRow(false);
      setEditForm({});
    },
    onError: () => message.error('添加失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<PropertyCreate> }) => updateProperty(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties', materialId] });
      message.success('属性已更新');
      setEditingKey(null);
      setEditForm({});
    },
    onError: () => message.error('更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteProperty(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties', materialId] });
      message.success('属性已删除');
    },
    onError: () => message.error('删除失败'),
  });

  const startAdd = () => {
    setNewRow(true);
    setEditForm({ property_name: '', value_number: undefined, unit: '', test_method: '' });
  };

  const startEdit = (record: Property) => {
    setEditingKey(record.id);
    setEditForm({
      property_name: record.property_name,
      value_number: record.value_number,
      value_text: record.value_text,
      unit: record.unit || '',
      test_method: record.test_method || '',
    });
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setNewRow(false);
    setEditForm({});
  };

  const saveNew = () => {
    if (!editForm.property_name?.trim()) {
      message.warning('请输入属性名');
      return;
    }
    createMutation.mutate({
      material_id: materialId,
      property_name: editForm.property_name.trim(),
      value_number: editForm.value_number,
      value_text: editForm.value_text,
      unit: editForm.unit || undefined,
      test_method: editForm.test_method || undefined,
      metadata: {},
    } as PropertyCreate);
  };

  const saveEdit = () => {
    if (!editingKey) return;
    updateMutation.mutate({
      id: editingKey,
      body: {
        property_name: editForm.property_name,
        value_number: editForm.value_number,
        value_text: editForm.value_text,
        unit: editForm.unit || undefined,
        test_method: editForm.test_method || undefined,
      },
    });
  };

  const displayValue = (r: Property) => {
    if (r.value_number != null) return r.value_number;
    if (r.value_text) return r.value_text;
    return '-';
  };

  const columns = [
    {
      title: '属性名',
      dataIndex: 'property_name',
      key: 'property_name',
      width: 200,
      render: (_: string, record: Property) => {
        const isEditing = editingKey === record.id;
        return isEditing ? (
          <AutoComplete
            value={editForm.property_name}
            options={nameSuggestions.map((n) => ({ value: n }))}
            onChange={(v) => setEditForm({ ...editForm, property_name: v })}
            style={{ width: '100%' }}
            placeholder="属性名"
          />
        ) : (
          <Text strong>{record.property_name}</Text>
        );
      },
    },
    {
      title: '数值',
      dataIndex: 'value_number',
      key: 'value',
      width: 160,
      render: (_: unknown, record: Property) => {
        const isEditing = editingKey === record.id;
        return isEditing ? (
          <InputNumber
            value={editForm.value_number}
            onChange={(v) => setEditForm({ ...editForm, value_number: v ?? undefined })}
            style={{ width: '100%' }}
            placeholder="数值"
            stringMode={false}
          />
        ) : (
          displayValue(record)
        );
      },
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 100,
      render: (_: string, record: Property) => {
        const isEditing = editingKey === record.id;
        return isEditing ? (
          <Input
            value={editForm.unit}
            onChange={(e) => setEditForm({ ...editForm, unit: e.target.value })}
            placeholder="如 MPa"
          />
        ) : (
          record.unit || '-'
        );
      },
    },
    {
      title: '测试方法',
      dataIndex: 'test_method',
      key: 'test_method',
      width: 140,
      render: (_: string, record: Property) => {
        const isEditing = editingKey === record.id;
        return isEditing ? (
          <Input
            value={editForm.test_method}
            onChange={(e) => setEditForm({ ...editForm, test_method: e.target.value })}
            placeholder="如 ASTM D638"
          />
        ) : (
          record.test_method || '-'
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: Property) => {
        const isEditing = editingKey === record.id;
        return isEditing ? (
          <Space>
            <Button type="link" icon={<SaveOutlined />} onClick={saveEdit} loading={updateMutation.isPending} />
            <Button type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
          </Space>
        ) : (
          <Space>
            <Button type="link" icon={<EditOutlined />} onClick={() => startEdit(record)} disabled={editingKey !== null || newRow} />
            <Popconfirm title="删除此属性？" onConfirm={() => deleteMutation.mutate(record.id)}>
              <Button type="link" danger icon={<DeleteOutlined />} disabled={editingKey !== null || newRow} />
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  // Build data source: existing properties + optional new row
  const dataSource = [...(properties || [])];
  if (newRow) {
    dataSource.push({
      id: '__new__',
      material_id: materialId,
      property_name: '',
      created_at: '',
      updated_at: '',
    } as Property);
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={startAdd}
          disabled={newRow || editingKey !== null}
        >
          添加属性
        </Button>
      </div>

      {newRow && (
        <div style={{ marginBottom: 12, padding: 12, background: '#f6ffed', borderRadius: 6, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <AutoComplete
            value={editForm.property_name}
            options={nameSuggestions.map((n) => ({ value: n }))}
            onChange={(v) => setEditForm({ ...editForm, property_name: v })}
            style={{ width: 180 }}
            placeholder="属性名*"
          />
          <InputNumber
            value={editForm.value_number}
            onChange={(v) => setEditForm({ ...editForm, value_number: v ?? undefined })}
            placeholder="数值"
            style={{ width: 120 }}
          />
          <Input
            value={editForm.unit}
            onChange={(e) => setEditForm({ ...editForm, unit: e.target.value })}
            placeholder="单位"
            style={{ width: 100 }}
          />
          <Input
            value={editForm.test_method}
            onChange={(e) => setEditForm({ ...editForm, test_method: e.target.value })}
            placeholder="测试方法"
            style={{ width: 140 }}
          />
          <Button type="primary" icon={<SaveOutlined />} onClick={saveNew} loading={createMutation.isPending}>保存</Button>
          <Button icon={<CloseOutlined />} onClick={cancelEdit}>取消</Button>
        </div>
      )}

      <Table
        columns={columns}
        dataSource={dataSource}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        size="middle"
        locale={{ emptyText: '暂无属性，点击上方按钮添加' }}
      />
    </div>
  );
}
