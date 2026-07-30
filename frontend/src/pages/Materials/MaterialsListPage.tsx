import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Button, Input, Select, Space, Tag, Popconfirm, message, Typography,
  Modal, Form, Radio, Divider,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined,
  FolderAddOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchMaterials, deleteMaterial, batchDeleteMaterials, getExportUrl,
} from '../../api/materials';
import {
  fetchCollections, createCollection, addMaterialsToCollection,
} from '../../api/collections';
import type { Material } from '../../types/material';
import type { CollectionListItem } from '../../types/collection';

const { Title, Text } = Typography;

const MATERIAL_TYPES = [
  { label: '全部类型', value: '' },
  { label: '金属', value: 'metal' },
  { label: '聚合物', value: 'polymer' },
  { label: '陶瓷', value: 'ceramic' },
  { label: '复合材料', value: 'composite' },
  { label: '电池材料', value: 'battery' },
  { label: '其他', value: 'other' },
];

export default function MaterialsListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [materialType, setMaterialType] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Row selection
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Save-to-subset modal
  const [subsetModalOpen, setSubsetModalOpen] = useState(false);
  const [subsetMode, setSubsetMode] = useState<'existing' | 'new'>('existing');
  const [existingCollectionId, setExistingCollectionId] = useState<string | null>(null);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [newCollectionDesc, setNewCollectionDesc] = useState('');
  const [subsetForm] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['materials', { page, size: pageSize, search, material_type: materialType }],
    queryFn: () => fetchMaterials({ page, size: pageSize, search, material_type: materialType || undefined }),
  });

  // Collections for the save-to-subset selector
  const { data: collectionsData } = useQuery({
    queryKey: ['collections'],
    queryFn: () => fetchCollections({ size: 200 }),
    enabled: subsetModalOpen,
  });
  const collections = collectionsData?.items || [];

  const deleteMutation = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      message.success('材料已删除');
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      setSelectedIds([]);
    },
    onError: () => message.error('删除失败'),
  });

  const batchDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => batchDeleteMaterials(ids),
    onSuccess: (res) => {
      message.success(`已删除 ${res.deleted} 个材料`);
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      setSelectedIds([]);
    },
    onError: () => message.error('批量删除失败'),
  });

  const addToCollectionMutation = useMutation({
    mutationFn: ({ id, ids }: { id: string; ids: string[] }) =>
      addMaterialsToCollection(id, ids),
    onSuccess: () => {
      message.success('已添加到子集');
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setSubsetModalOpen(false);
      setSelectedIds([]);
    },
    onError: () => message.error('添加失败'),
  });

  const createCollectionMutation = useMutation({
    mutationFn: (body: { name: string; description?: string; material_ids: string[] }) =>
      createCollection(body),
    onSuccess: () => {
      message.success('子集已创建');
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setSubsetModalOpen(false);
      setSelectedIds([]);
    },
    onError: () => message.error('创建失败'),
  });

  const handleSaveToSubset = async () => {
    if (subsetMode === 'existing') {
      if (!existingCollectionId) {
        message.warning('请选择一个已有子集');
        return;
      }
      addToCollectionMutation.mutate({
        id: existingCollectionId,
        ids: selectedIds,
      });
    } else {
      if (!newCollectionName.trim()) {
        message.warning('请输入子集名称');
        return;
      }
      createCollectionMutation.mutate({
        name: newCollectionName.trim(),
        description: newCollectionDesc.trim() || undefined,
        material_ids: selectedIds,
      });
    }
  };

  const openSubsetModal = () => {
    setSubsetMode('existing');
    setExistingCollectionId(null);
    setNewCollectionName('');
    setNewCollectionDesc('');
    setSubsetModalOpen(true);
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Material) => (
        <a onClick={() => navigate(`/materials/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: '类型',
      dataIndex: 'material_type',
      key: 'material_type',
      width: 120,
      render: (t: string) => {
        const colors: Record<string, string> = {
          metal: 'blue',
          polymer: 'green',
          ceramic: 'orange',
          composite: 'purple',
          battery: 'red',
          other: 'default',
        };
        return <Tag color={colors[t] || 'default'}>{MATERIAL_TYPES.find((m) => m.value === t)?.label || t}</Tag>;
      },
    },
    {
      title: '化学式',
      dataIndex: 'formula_string',
      key: 'formula_string',
      width: 200,
      render: (text: string | undefined) => text || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleDateString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: unknown, record: Material) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => navigate(`/materials/${record.id}/edit`)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此材料？"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const rowSelection = {
    selectedRowKeys: selectedIds,
    onChange: (keys: React.Key[]) => setSelectedIds(keys as string[]),
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>材料管理</Title>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/materials/new')}>
            新建材料
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => {
              const token = localStorage.getItem('access_token');
              const url = `${import.meta.env.VITE_API_BASE || '/api/v1'}${getExportUrl({
                search: search || undefined,
                material_type: materialType || undefined,
              })}`;
              // Download via hidden link with auth header
              const link = document.createElement('a');
              link.href = `${window.location.origin}/api/v1${getExportUrl({
                search: search || undefined,
                material_type: materialType || undefined,
              })}`;
              // For authenticated download, use fetch + blob
              fetch(link.href, {
                headers: { Authorization: `Bearer ${token}` },
              })
                .then((res) => res.blob())
                .then((blob) => {
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `materials_export_${new Date().toISOString().slice(0, 10)}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                  message.success('导出成功');
                })
                .catch(() => message.error('导出失败'));
            }}
          >
            导出 CSV
          </Button>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索材料名称、化学式..."
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 300 }}
          allowClear
        />
        <Select
          value={materialType}
          onChange={(v) => { setMaterialType(v); setPage(1); }}
          options={MATERIAL_TYPES}
          style={{ width: 140 }}
        />
      </Space>

      {/* Batch action bar */}
      {selectedIds.length > 0 && (
        <div style={{
          marginBottom: 16, padding: '10px 16px',
          background: '#e6f4ff', borderRadius: 6,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <Text>已选 <strong>{selectedIds.length}</strong> 项</Text>
          <Space>
            <Button
              icon={<FolderAddOutlined />}
              onClick={openSubsetModal}
            >
              保存到子集
            </Button>
            <Popconfirm
              title={`确定删除选中的 ${selectedIds.length} 个材料及其全部关联数据？此操作不可恢复。`}
              onConfirm={() => batchDeleteMutation.mutate(selectedIds)}
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
          </Space>
        </div>
      )}

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={data?.items || []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: data?.total || 0,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
      />

      {/* Save to Subset Modal */}
      <Modal
        title="保存到子集"
        open={subsetModalOpen}
        onCancel={() => setSubsetModalOpen(false)}
        onOk={handleSaveToSubset}
        confirmLoading={addToCollectionMutation.isPending || createCollectionMutation.isPending}
        okText="确认"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">将选中的 {selectedIds.length} 个材料保存到：</Text>
        </div>

        <Radio.Group
          value={subsetMode}
          onChange={(e) => setSubsetMode(e.target.value)}
          style={{ marginBottom: 16 }}
          optionType="button"
          buttonStyle="solid"
        >
          <Radio.Button value="existing">已有子集</Radio.Button>
          <Radio.Button value="new">新建子集</Radio.Button>
        </Radio.Group>

        <Divider style={{ margin: '12px 0' }} />

        {subsetMode === 'existing' ? (
          <Select
            showSearch
            placeholder="选择已有子集..."
            value={existingCollectionId}
            onChange={setExistingCollectionId}
            options={collections.map((c) => ({
              label: `${c.name}（${c.material_count} 个材料）`,
              value: c.id,
            }))}
            style={{ width: '100%' }}
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
            }
            notFoundContent="暂无子集，请选择新建"
          />
        ) : (
          <Form layout="vertical">
            <Form.Item label="子集名称" required>
              <Input
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="如：高介电材料"
              />
            </Form.Item>
            <Form.Item label="描述（可选）">
              <Input.TextArea
                value={newCollectionDesc}
                onChange={(e) => setNewCollectionDesc(e.target.value)}
                placeholder="简要描述这个子集..."
                rows={3}
              />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}
