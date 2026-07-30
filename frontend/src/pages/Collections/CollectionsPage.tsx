import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Button, Space, Tag, Popconfirm, message, Typography, Modal, Input, Form, Empty,
  Select, Checkbox, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, FolderOpenOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchCollections, fetchCollection, createCollection, updateCollection, deleteCollection,
} from '../../api/collections';
import { fetchMaterials } from '../../api/materials';
import { fetchRoles } from '../../api/users';
import type { CollectionListItem, Collection } from '../../types/collection';
import type { Material } from '../../types/material';

const { Title, Text } = Typography;

export default function CollectionsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Create/Edit modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editingColl, setEditingColl] = useState<CollectionListItem | null>(null);
  const [form] = Form.useForm();

  // View materials modal
  const [materialsModalOpen, setMaterialsModalOpen] = useState(false);
  const [viewingCollection, setViewingCollection] = useState<Collection | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['collections', { page, size: pageSize }],
    queryFn: () => fetchCollections({ page, size: pageSize }),
  });

  const { data: roles = [] } = useQuery({
    queryKey: ['roles'],
    queryFn: fetchRoles,
  });

  const ROLE_OPTIONS = roles.map((r) => ({ label: r.name, value: r.id }));

  // Load full collection when viewing materials
  const { data: viewingMaterials, isFetching: loadingMaterials } = useQuery({
    queryKey: ['collection', viewingCollection?.id],
    queryFn: async () => {
      if (!viewingCollection) return [];
      const coll = await fetchCollection(viewingCollection.id);
      if (!coll.material_ids?.length) return [];
      // Fetch materials by IDs — use a large page to get them all
      const result = await fetchMaterials({ size: 500 });
      const idSet = new Set(coll.material_ids);
      return (result.items as Material[]).filter((m) => idSet.has(m.id));
    },
    enabled: !!viewingCollection && materialsModalOpen,
  });

  const createMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      createCollection(body as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      message.success('子集已创建');
      setModalOpen(false);
    },
    onError: () => message.error('创建失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      updateCollection(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      message.success('子集已更新');
      setModalOpen(false);
    },
    onError: () => message.error('更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCollection(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      message.success('子集已删除');
    },
    onError: () => message.error('删除失败'),
  });

  const openCreateModal = () => {
    setEditingColl(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (coll: CollectionListItem) => {
    setEditingColl(coll);
    // Load full collection for allowed_role_ids
    fetchCollection(coll.id).then((c) => {
      form.setFieldsValue({
        name: c.name,
        description: c.description || '',
        visibility: c.visibility || 'private',
        allowed_role_ids: c.allowed_role_ids || [],
      });
      setModalOpen(true);
    });
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (editingColl) {
      updateMutation.mutate({
        id: editingColl.id,
        body: {
          name: values.name,
          description: values.description || undefined,
          visibility: values.visibility,
          allowed_role_ids: values.allowed_role_ids || [],
        },
      });
    } else {
      createMutation.mutate({
        name: values.name,
        description: values.description || undefined,
        material_ids: [],
        visibility: values.visibility || 'private',
        allowed_role_ids: values.allowed_role_ids || [],
      });
    }
  };

  const openViewMaterials = (coll: CollectionListItem) => {
    // We need the full collection with material_ids
    fetchCollection(coll.id).then((c) => {
      setViewingCollection(c);
      setMaterialsModalOpen(true);
    });
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: CollectionListItem) => (
        <a onClick={() => openViewMaterials(record)}>{text}</a>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string | undefined) => text || '-',
    },
    {
      title: '可见性',
      dataIndex: 'visibility',
      key: 'visibility',
      width: 90,
      align: 'center' as const,
      render: (v: string) => {
        const labels: Record<string, { color: string; text: string }> = {
          private: { color: 'red', text: '私有' },
          role: { color: 'orange', text: '角色' },
          public: { color: 'green', text: '公开' },
        };
        const info = labels[v] || labels.private;
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    {
      title: '材料数量',
      dataIndex: 'material_count',
      key: 'material_count',
      width: 110,
      align: 'center' as const,
      render: (count: number) => <Tag color="blue">{count}</Tag>,
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
      width: 200,
      render: (_: unknown, record: CollectionListItem) => (
        <Space>
          <Button
            type="link"
            icon={<FolderOpenOutlined />}
            onClick={() => openViewMaterials(record)}
          >
            查看
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此子集？（材料不会被删除）"
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

  const materialsColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Material) => (
        <a onClick={() => { setMaterialsModalOpen(false); navigate(`/materials/${record.id}`); }}>
          {text}
        </a>
      ),
    },
    { title: '类型', dataIndex: 'material_type', key: 'type', width: 100 },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>子集管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          新建子集
        </Button>
      </div>

      <Table
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
          showTotal: (total) => `共 ${total} 个子集`,
        }}
        locale={{ emptyText: <Empty description="暂无子集，选择材料后可保存到子集" /> }}
      />

      {/* Create/Edit Modal */}
      <Modal
        title={editingColl ? '编辑子集' : '新建子集'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }} initialValues={{ visibility: 'private', allowed_role_ids: [] }}>
          <Form.Item name="name" label="子集名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如：高介电材料、耐高温聚合物" />
          </Form.Item>
          <Form.Item name="description" label="描述（可选）">
            <Input.TextArea placeholder="简要描述这个子集..." rows={3} />
          </Form.Item>
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item name="visibility" label="可见性">
            <Select
              options={[
                { label: '🔒 私有 — 仅创建者可见', value: 'private' },
                { label: '👥 角色可见 — 指定角色可查看', value: 'role' },
                { label: '🌐 公开 — 所有人可见', value: 'public' },
              ]}
            />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, cur) => prev.visibility !== cur.visibility}
          >
            {({ getFieldValue }) =>
              getFieldValue('visibility') === 'role' ? (
                <Form.Item name="allowed_role_ids" label="允许访问的角色">
                  <Checkbox.Group options={ROLE_OPTIONS} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
        </Form>
      </Modal>

      {/* View Materials Modal */}
      <Modal
        title={viewingCollection ? `子集：${viewingCollection.name}` : ''}
        open={materialsModalOpen}
        onCancel={() => { setMaterialsModalOpen(false); setViewingCollection(null); }}
        footer={null}
        width={700}
      >
        <Table
          columns={materialsColumns}
          dataSource={viewingMaterials || []}
          rowKey="id"
          loading={loadingMaterials}
          pagination={false}
          size="small"
          locale={{ emptyText: '此子集暂无材料' }}
        />
      </Modal>
    </div>
  );
}
