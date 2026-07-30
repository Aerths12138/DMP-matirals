import { useState } from 'react';
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  CheckCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approveUser,
  changeUserRole,
  createUser,
  deleteUser,
  fetchRoles,
  fetchUsers,
} from '../../api/users';
import type { User } from '../../types/user';

const { Title, Text } = Typography;

type ApprovalFilter = 'all' | 'pending' | 'approved';

function errorMessage(error: any, fallback: string) {
  return error?.response?.data?.detail || error?.message || fallback;
}

export default function UserManagementPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [approvalFilter, setApprovalFilter] = useState<ApprovalFilter>('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [pendingUser, setPendingUser] = useState<User | null>(null);
  const [selectedRole, setSelectedRole] = useState<number>();
  const [form] = Form.useForm();

  const approvedParam = approvalFilter === 'all'
    ? undefined
    : approvalFilter === 'approved';

  const usersQuery = useQuery({
    queryKey: ['users', { page, size: 20, search, is_approved: approvedParam }],
    queryFn: () => fetchUsers({
      page,
      size: 20,
      search: search || undefined,
      is_approved: approvedParam,
    }),
    retry: false,
  });

  const rolesQuery = useQuery({
    queryKey: ['roles'],
    queryFn: fetchRoles,
    retry: false,
  });
  const roles = rolesQuery.data || [];
  const roleOptions = roles.map((role) => ({ label: role.name, value: role.id }));

  const createMutation = useMutation({
    mutationFn: (body: {
      username: string;
      email: string;
      password: string;
      display_name?: string;
      department?: string;
    }) => createUser(body),
    onSuccess: () => {
      message.success('用户已创建，请在待审核列表中分配角色');
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setModalOpen(false);
      form.resetFields();
    },
    onError: (error) => message.error(errorMessage(error, '创建失败')),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success('用户已删除');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => message.error(errorMessage(error, '删除失败')),
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, role_id }: { id: string; role_id: number }) =>
      changeUserRole(id, role_id),
    onSuccess: () => {
      message.success('角色已更新');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => message.error(errorMessage(error, '角色更新失败')),
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, role_id }: { id: string; role_id: number }) =>
      approveUser(id, role_id),
    onSuccess: () => {
      message.success('用户已审核通过');
      queryClient.invalidateQueries({ queryKey: ['users'] });
      closeApproveModal();
    },
    onError: (error) => message.error(errorMessage(error, '审核失败')),
  });

  const closeApproveModal = () => {
    setApproveModalOpen(false);
    setPendingUser(null);
    setSelectedRole(undefined);
  };

  const openApproveModal = (user: User) => {
    setPendingUser(user);
    setSelectedRole(undefined);
    setApproveModalOpen(true);
  };

  const handleApprove = () => {
    if (!pendingUser || selectedRole == null) {
      message.warning('请先为用户分配角色');
      return;
    }
    approveMutation.mutate({ id: pendingUser.id, role_id: selectedRole });
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 140 },
    { title: '邮箱', dataIndex: 'email', key: 'email', width: 220 },
    {
      title: '显示名称',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 150,
      render: (value: string | undefined) => value || '-',
    },
    {
      title: '部门',
      dataIndex: 'department',
      key: 'department',
      width: 140,
      render: (value: string | undefined) => value || '-',
    },
    {
      title: '角色',
      dataIndex: 'role_id',
      key: 'role_id',
      width: 140,
      render: (roleId: number | undefined, record: User) => {
        if (!record.is_approved) return <Text type="secondary">未分配</Text>;
        return (
          <Select
            value={roleId}
            size="small"
            options={roleOptions}
            loading={rolesQuery.isLoading}
            style={{ width: 115 }}
            onChange={(value) => roleMutation.mutate({ id: record.id, role_id: value })}
          />
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active: boolean, record: User) => {
        if (!record.is_approved) return <Tag color="orange">待审核</Tag>;
        return active ? <Tag color="green">已启用</Tag> : <Tag color="red">已禁用</Tag>;
      },
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (value: string) => new Date(value).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right' as const,
      width: 160,
      render: (_: unknown, record: User) => (
        <Space>
          {!record.is_approved && (
            <Button
              type="link"
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => openApproveModal(record)}
            >
              审核
            </Button>
          )}
          <Popconfirm
            title="确定删除此用户？"
            description="该操作不可恢复。"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>用户管理</Title>
          <Text type="secondary">查看平台用户，为新注册用户分配角色并完成审核。</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建用户
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Segmented
          value={approvalFilter}
          options={[
            { label: '全部用户', value: 'all' },
            { label: '待审核', value: 'pending' },
            { label: '已通过', value: 'approved' },
          ]}
          onChange={(value) => {
            setApprovalFilter(value as ApprovalFilter);
            setPage(1);
          }}
        />
        <Input.Search
          prefix={<SearchOutlined />}
          placeholder="搜索用户名或邮箱"
          allowClear
          style={{ width: 280 }}
          onSearch={(value) => {
            setSearch(value.trim());
            setPage(1);
          }}
          onChange={(event) => {
            if (!event.target.value) {
              setSearch('');
              setPage(1);
            }
          }}
        />
      </Space>

      {rolesQuery.isError && (
        <Alert
          type="warning"
          showIcon
          message="角色列表加载失败"
          description={errorMessage(rolesQuery.error, '暂时无法分配或修改角色。')}
          style={{ marginBottom: 16 }}
        />
      )}

      {usersQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="用户列表加载失败"
          description={errorMessage(usersQuery.error, '请检查后端服务后重试。')}
          action={(
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => usersQuery.refetch()}
            >
              重试
            </Button>
          )}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={usersQuery.data?.items || []}
          rowKey="id"
          loading={usersQuery.isLoading || usersQuery.isFetching}
          scroll={{ x: 1220 }}
          pagination={{
            current: page,
            pageSize: 20,
            total: usersQuery.data?.total || 0,
            onChange: setPage,
            showTotal: (total) => `共 ${total} 个用户`,
          }}
        />
      )}

      <Modal
        title="新建用户"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
        okText="创建"
      >
        <Form form={form} layout="vertical" onFinish={(values) => createMutation.mutate(values)}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 8, message: '密码至少8位' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input />
          </Form.Item>
          <Form.Item name="department" label="部门">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="审核新用户"
        open={approveModalOpen}
        onCancel={closeApproveModal}
        onOk={handleApprove}
        confirmLoading={approveMutation.isPending}
        okText="通过审核"
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div><Text strong>用户名：</Text>{pendingUser?.username}</div>
          <div><Text strong>邮箱：</Text>{pendingUser?.email}</div>
          <div><Text strong>显示名称：</Text>{pendingUser?.display_name || '-'}</div>
          <div><Text strong>部门：</Text>{pendingUser?.department || '-'}</div>
          <div style={{ marginTop: 8 }}><Text strong>分配角色</Text></div>
          <Select
            placeholder="选择角色"
            value={selectedRole}
            onChange={setSelectedRole}
            options={roleOptions}
            loading={rolesQuery.isLoading}
            disabled={rolesQuery.isError}
            style={{ width: '100%' }}
          />
        </Space>
      </Modal>
    </div>
  );
}
