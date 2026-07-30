import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Result,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  ControlOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addProjectMember,
  fetchProject,
  removeProjectMember,
  updateProject,
  updateProjectMember,
} from '../../api/projects';
import { fetchUserDirectory } from '../../api/users';
import { useAuthStore } from '../../stores/authStore';
import type {
  ProjectMember,
  ProjectRole,
  ProjectStatus,
  ProjectUpdate,
} from '../../types/project';
import DataStandardsDrawer from './DataStandardsDrawer';
import ProjectDataSection from './ProjectDataSection';

const { Title, Text } = Typography;

const STATUS_OPTIONS = [
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
];

const STATUS_LABELS: Record<ProjectStatus, { color: string; text: string }> = {
  active: { color: 'processing', text: '进行中' },
  completed: { color: 'success', text: '已完成' },
  archived: { color: 'default', text: '已归档' },
};

const ROLE_LABELS: Record<ProjectRole, { color: string; text: string }> = {
  owner: { color: 'gold', text: '负责人' },
  editor: { color: 'blue', text: '编辑者' },
  viewer: { color: 'default', text: '只读成员' },
};

type EditableProjectRole = Exclude<ProjectRole, 'owner'>;

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const [editOpen, setEditOpen] = useState(false);
  const [memberOpen, setMemberOpen] = useState(false);
  const [standardsOpen, setStandardsOpen] = useState(false);
  const [editForm] = Form.useForm<ProjectUpdate>();
  const [memberForm] = Form.useForm<{
    user_id: string;
    role: EditableProjectRole;
  }>();

  const {
    data: project,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['project', id],
    queryFn: () => fetchProject(id!),
    enabled: !!id,
  });

  const currentMembership = project?.members.find(
    (member) => member.user_id === currentUser?.id
  );
  const isAdmin = currentUser?.role_name === 'admin';
  const hasSystemWriteAccess = currentUser?.role_name === 'researcher';
  const canEdit =
    isAdmin ||
    (hasSystemWriteAccess &&
      (currentMembership?.role === 'owner' ||
        currentMembership?.role === 'editor'));
  const canManageMembers =
    isAdmin ||
    (hasSystemWriteAccess && currentMembership?.role === 'owner');

  const { data: directory = [] } = useQuery({
    queryKey: ['user-directory'],
    queryFn: fetchUserDirectory,
    enabled: canManageMembers,
  });

  const refreshProject = () => {
    queryClient.invalidateQueries({ queryKey: ['project', id] });
    queryClient.invalidateQueries({ queryKey: ['projects'] });
  };

  const editMutation = useMutation({
    mutationFn: (body: ProjectUpdate) => updateProject(id!, body),
    onSuccess: () => {
      refreshProject();
      setEditOpen(false);
      message.success('项目信息已更新');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '更新项目失败');
    },
  });

  const addMemberMutation = useMutation({
    mutationFn: (values: { user_id: string; role: EditableProjectRole }) =>
      addProjectMember(id!, values.user_id, values.role),
    onSuccess: () => {
      refreshProject();
      memberForm.resetFields();
      setMemberOpen(false);
      message.success('成员已添加');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '添加成员失败');
    },
  });

  const updateMemberMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: EditableProjectRole }) =>
      updateProjectMember(id!, userId, role),
    onSuccess: () => {
      refreshProject();
      message.success('成员角色已更新');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '更新成员角色失败');
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userId: string) => removeProjectMember(id!, userId),
    onSuccess: () => {
      refreshProject();
      message.success('成员已移除');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '移除成员失败');
    },
  });

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (isError || !project) {
    return (
      <Result
        status="403"
        title="无法访问该项目"
        subTitle="项目不存在，或你尚未加入该项目。"
        extra={<Button onClick={() => navigate('/projects')}>返回项目列表</Button>}
      />
    );
  }

  const openEdit = () => {
    editForm.setFieldsValue({
      name: project.name,
      description: project.description,
      status: project.status,
    });
    setEditOpen(true);
  };

  const handleEdit = async () => {
    const values = await editForm.validateFields();
    editMutation.mutate(values);
  };

  const handleAddMember = async () => {
    const values = await memberForm.validateFields();
    addMemberMutation.mutate(values);
  };

  const memberIds = new Set(project.members.map((member) => member.user_id));
  const userOptions = directory
    .filter((user) => !memberIds.has(user.id))
    .map((user) => ({
      value: user.id,
      label: user.display_name
        ? `${user.display_name} (${user.username})`
        : user.username,
    }));

  const memberColumns: ColumnsType<ProjectMember> = [
    {
      title: '成员',
      key: 'user',
      render: (_, member) => (
        <div>
          <div>{member.user.display_name || member.user.username}</div>
          {member.user.display_name && (
            <Text type="secondary">{member.user.username}</Text>
          )}
        </div>
      ),
    },
    {
      title: '项目角色',
      dataIndex: 'role',
      key: 'role',
      width: 180,
      render: (role: ProjectRole, member) => {
        if (canManageMembers && role !== 'owner') {
          return (
            <Select
              value={role}
              style={{ width: 120 }}
              options={[
                { value: 'editor', label: '编辑者' },
                { value: 'viewer', label: '只读成员' },
              ]}
              onChange={(nextRole: EditableProjectRole) =>
                updateMemberMutation.mutate({
                  userId: member.user_id,
                  role: nextRole,
                })
              }
            />
          );
        }
        const label = ROLE_LABELS[role];
        return <Tag color={label.color}>{label.text}</Tag>;
      },
    },
    {
      title: '加入时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (value: string) => new Date(value).toLocaleDateString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      render: (_, member) =>
        canManageMembers && member.role !== 'owner' ? (
          <Popconfirm
            title="确定移除该成员吗？"
            onConfirm={() => removeMemberMutation.mutate(member.user_id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              移除
            </Button>
          </Popconfirm>
        ) : (
          '-'
        ),
    },
  ];

  const statusLabel = STATUS_LABELS[project.status];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            {project.name}
          </Title>
          <Tag color={statusLabel.color}>{statusLabel.text}</Tag>
        </Space>
        <Space>
          <Button icon={<ControlOutlined />} onClick={() => setStandardsOpen(true)}>
            数据标准
          </Button>
          {canEdit && (
            <Button type="primary" icon={<EditOutlined />} onClick={openEdit}>
              编辑项目
            </Button>
          )}
        </Space>
      </div>

      <Card title="项目概览" style={{ marginBottom: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="负责人">
            {project.members.find((member) => member.role === 'owner')?.user
              .display_name ||
              project.members.find((member) => member.role === 'owner')?.user
                .username ||
              '-'}
          </Descriptions.Item>
          <Descriptions.Item label="成员数量">
            {project.members.length}
          </Descriptions.Item>
          <Descriptions.Item label="开始日期">
            {project.start_date || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="结束日期">
            {project.end_date || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="项目描述" span={2}>
            {project.description || '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <ProjectDataSection projectId={id!} canEdit={!!canEdit} />
      <Card
        title="项目成员"
        extra={
          canManageMembers ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                memberForm.setFieldsValue({ role: 'viewer' });
                setMemberOpen(true);
              }}
            >
              添加成员
            </Button>
          ) : null
        }
      >
        <Table
          columns={memberColumns}
          dataSource={project.members}
          rowKey="id"
          pagination={false}
        />
      </Card>

      <Modal
        title="编辑项目"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleEdit}
        confirmLoading={editMutation.isPending}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, whitespace: true, message: '请输入项目名称' }]}
          >
            <Input maxLength={300} />
          </Form.Item>
          <Form.Item name="description" label="项目描述">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="status" label="项目状态">
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加项目成员"
        open={memberOpen}
        onCancel={() => setMemberOpen(false)}
        onOk={handleAddMember}
        confirmLoading={addMemberMutation.isPending}
        okText="添加"
        cancelText="取消"
      >
        <Form form={memberForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="user_id"
            label="用户"
            rules={[{ required: true, message: '请选择用户' }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="选择已审批用户"
              options={userOptions}
              notFoundContent="没有可添加的用户"
            />
          </Form.Item>
          <Form.Item
            name="role"
            label="项目角色"
            rules={[{ required: true, message: '请选择项目角色' }]}
          >
            <Select
              options={[
                { value: 'editor', label: '编辑者（可修改项目）' },
                { value: 'viewer', label: '只读成员（仅查看）' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <DataStandardsDrawer
        open={standardsOpen}
        projectId={id!}
        canEdit={!!canEdit}
        onClose={() => setStandardsOpen(false)}
      />
    </div>
  );
}
