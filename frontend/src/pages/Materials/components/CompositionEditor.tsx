import { useState } from 'react';
import { Table, Button, Select, Input, InputNumber, Popconfirm, Space, message, Typography } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateMaterial } from '../../../api/materials';
import type { CompositionItem } from '../../../types/material';

const { Text } = Typography;

const COMPONENT_TYPES = [
  { label: '元素', value: 'element' },
  { label: '单体', value: 'monomer' },
  { label: '相', value: 'phase' },
];

const AMOUNT_UNITS = [
  { label: 'wt%', value: 'wt%' },
  { label: 'at%', value: 'at%' },
  { label: 'mol%', value: 'mol%' },
  { label: '质量分数', value: 'weight_fraction' },
];

interface Props {
  materialId: string;
  composition: CompositionItem[];
}

export default function CompositionEditor({ materialId, composition }: Props) {
  const queryClient = useQueryClient();
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [addingNew, setAddingNew] = useState(false);
  const [editForm, setEditForm] = useState<Partial<CompositionItem>>({});

  const saveMutation = useMutation({
    mutationFn: (newComposition: CompositionItem[]) =>
      updateMaterial(materialId, { composition: newComposition } as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['material', materialId] });
      message.success('配方已更新');
      setEditingIndex(null);
      setAddingNew(false);
      setEditForm({});
    },
    onError: () => message.error('更新失败'),
  });

  const startAdd = () => {
    setAddingNew(true);
    setEditingIndex(null);
    setEditForm({ unit: 'wt%' });
  };

  const startEdit = (index: number, item: CompositionItem) => {
    setAddingNew(false);
    setEditingIndex(index);
    setEditForm({ ...item });
  };

  const cancelEdit = () => {
    setEditingIndex(null);
    setAddingNew(false);
    setEditForm({});
  };

  const saveNew = () => {
    const newItem = buildItem();
    if (!newItem) return;
    saveMutation.mutate([...composition, newItem]);
  };

  const saveEdit = () => {
    if (editingIndex === null) return;
    const updatedItem = buildItem();
    if (!updatedItem) return;
    const updated = [...composition];
    updated[editingIndex] = updatedItem;
    saveMutation.mutate(updated);
  };

  const deleteItem = (index: number) => {
    const updated = composition.filter((_, i) => i !== index);
    // Skip mutation wrapper — just update directly
    updateMaterial(materialId, { composition: updated } as any)
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ['material', materialId] });
        message.success('组分已删除');
      })
      .catch(() => message.error('删除失败'));
  };

  const buildItem = (): CompositionItem | null => {
    const item = { ...editForm } as CompositionItem;
    // Determine which name field is filled
    const type = getType(item);
    if (!type) {
      message.warning('请填写元素/单体/相名称');
      return null;
    }
    // Read amount from whichever field has a value
    const amount = item.amount ?? item.mole_percent ?? item.weight_fraction ?? undefined;
    if (amount == null) {
      message.warning('请输入含量');
      return null;
    }
    // Build clean item based on type
    const clean: CompositionItem = { unit: item.unit || 'wt%' };
    if (item.unit === 'mol%' || item.unit === 'mole_percent') {
      clean.mole_percent = amount;
      clean.unit = 'mol%';
    } else if (item.unit === 'weight_fraction') {
      clean.weight_fraction = amount;
    } else if (item.unit === 'at%') {
      clean.unit = 'at%';
      clean.amount = amount;
    } else {
      clean.amount = amount;
      clean.unit = item.unit || 'wt%';
    }
    if (type === 'element') clean.element = item.element;
    else if (type === 'monomer') clean.monomer = item.monomer;
    else clean.phase = item.phase;
    return clean;
  };

  const getType = (item: Partial<CompositionItem>): string | null => {
    if (item.element?.trim()) return 'element';
    if (item.monomer?.trim()) return 'monomer';
    if (item.phase?.trim()) return 'phase';
    return null;
  };

  const getTypeLabel = (item: CompositionItem): string => {
    if (item.element) return '元素';
    if (item.monomer) return '单体';
    if (item.phase) return '相';
    return '-';
  };

  const getName = (item: CompositionItem): string =>
    item.element || item.monomer || item.phase || '-';

  const getAmount = (item: CompositionItem): string => {
    if (item.amount != null) return `${item.amount} ${item.unit || ''}`;
    if (item.mole_percent != null) return `${item.mole_percent} mol%`;
    if (item.weight_fraction != null) return `${item.weight_fraction} (质量分数)`;
    return '-';
  };

  const renderEditRow = (isNew: boolean) => {
    const isEditing = isNew || editingIndex !== null;

    const nameField = () => {
      const type = getType(editForm);
      if (!type || type === 'element') {
        return (
          <Input
            value={editForm.element || ''}
            onChange={(e) => setEditForm({ ...editForm, element: e.target.value, monomer: undefined, phase: undefined })}
            placeholder="元素名"
            style={{ width: 100 }}
          />
        );
      }
      if (type === 'monomer') {
        return (
          <Input
            value={editForm.monomer || ''}
            onChange={(e) => setEditForm({ ...editForm, monomer: e.target.value, element: undefined, phase: undefined })}
            placeholder="单体名"
            style={{ width: 100 }}
          />
        );
      }
      return (
        <Input
          value={editForm.phase || ''}
          onChange={(e) => setEditForm({ ...editForm, phase: e.target.value, element: undefined, monomer: undefined })}
          placeholder="相名"
          style={{ width: 100 }}
        />
      );
    };

    return (
      <div style={{ padding: '8px 0', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Select
          value={getType(editForm) || undefined}
          options={COMPONENT_TYPES}
          onChange={(v) => {
            // Clear all name fields when switching type
            setEditForm({ ...editForm, element: undefined, monomer: undefined, phase: undefined, [v]: '' } as any);
          }}
          placeholder="类型"
          style={{ width: 80 }}
        />
        {nameField()}
        <InputNumber
          value={editForm.amount ?? editForm.mole_percent ?? editForm.weight_fraction ?? undefined}
          onChange={(v) => setEditForm({ ...editForm, amount: v ?? undefined })}
          placeholder="含量"
          style={{ width: 100 }}
          stringMode={false}
        />
        <Select
          value={editForm.unit || 'wt%'}
          options={AMOUNT_UNITS}
          onChange={(v) => setEditForm({ ...editForm, unit: v })}
          style={{ width: 110 }}
        />
        <Button type="primary" icon={<SaveOutlined />} onClick={isNew ? saveNew : saveEdit} loading={saveMutation.isPending}>
          保存
        </Button>
        <Button icon={<CloseOutlined />} onClick={cancelEdit}>取消</Button>
      </div>
    );
  };

  const columns = [
    {
      title: '类型',
      key: 'type',
      width: 70,
      render: (_: unknown, record: CompositionItem) => (
        <Text>{getTypeLabel(record)}</Text>
      ),
    },
    {
      title: '组分',
      key: 'name',
      width: 140,
      render: (_: unknown, record: CompositionItem) => (
        <Text strong>{getName(record)}</Text>
      ),
    },
    {
      title: '含量',
      key: 'amount',
      width: 140,
      render: (_: unknown, record: CompositionItem) => (
        <Text>{getAmount(record)}</Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, __: CompositionItem, index: number) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => startEdit(index, composition[index])}
            disabled={editingIndex !== null || addingNew}
          />
          <Popconfirm title="删除此组分？" onConfirm={() => deleteItem(index)}>
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              disabled={editingIndex !== null || addingNew}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={startAdd}
          disabled={addingNew || editingIndex !== null}
        >
          添加组分
        </Button>
      </div>

      {addingNew && (
        <div style={{ marginBottom: 12, padding: 12, background: '#f6ffed', borderRadius: 6 }}>
          {renderEditRow(true)}
        </div>
      )}

      {editingIndex !== null && (
        <div style={{ marginBottom: 12, padding: 12, background: '#fff7e6', borderRadius: 6 }}>
          {renderEditRow(false)}
        </div>
      )}

      <Table
        columns={columns}
        dataSource={composition.map((c, i) => ({ ...c, key: i }))}
        pagination={false}
        size="middle"
        locale={{ emptyText: '暂无配方数据，点击上方按钮添加' }}
      />
    </div>
  );
}
