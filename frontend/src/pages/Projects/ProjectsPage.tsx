import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Empty,
  Form,
  Input,
  message,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { FolderOpenOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';

import { createProject, fetchProjects } from '../../api/projects';
import { useAuthStore } from '../../stores/authStore';
import type { Project, ProjectCreate, ProjectStatus } from '../../types/project';

const { Title } = Typography;

const STATUS_LABELS: Record<ProjectStatus, { color: string; text: string }> = {
  active: { color: 'processing', text: '进行中' },
  completed: { color: 'success', text: '已完成' },
  archived: { color: 'default', text: '已归档' },
};

export default function ProjectsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<ProjectCreate>();

  const { data, isLoading } = useQuery({
    queryKey: ['projects', { page, size: pageSize }],
    queryFn: () => fetchProjects({ page, size: pageSize }),
  });

  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      message.success('项目已创建');
      setModalOpen(false);
      form.resetFields();
      navigate(`/projects/${project.id}`);
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '创建项目失败');
    },
  });

  const handleCreate = async () => {
    const values = await form.validateFields();
    createMutation.mutate({
      name: values.name,
      description: values.description || undefined,
      status: 'active',
    });
  };

  const columns: ColumnsType<Project> = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, project) => (
        <a onClick={() => navigate(`/projects/${project.id}`)}>{name}</a>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (description?: string) => description || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: ProjectStatus) => {
        const label = STATUS_LABELS[status];
        return <Tag color={label.color}>{label.text}</Tag>;
      },
    },
    {
      title: '成员',
      dataIndex: 'members',
      key: 'members',
      width: 90,
      align: 'center',
      render: (members: Project['members']) => members.length,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 140,
      render: (value: string) => new Date(value).toLocaleDateString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_, project) => (
        <Button
          type="link"
          icon={<FolderOpenOutlined />}
          onClick={() => navigate(`/projects/${project.id}`)}
        >
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>
            项目协作
          </Title>
          <Typography.Text type="secondary">
            按项目组织实验数据，并通过成员角色控制访问范围。
          </Typography.Text>
        </div>
        {user?.role_name !== 'viewer' && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalOpen(true)}
          >
            新建项目
          </Button>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={data?.items || []}
        rowKey="id"
        loading={isLoading}
        locale={{ emptyText: <Empty description="暂无可访问的项目" /> }}
        pagination={{
          current: page,
          pageSize,
          total: data?.total || 0,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 个项目`,
          onChange: (nextPage, nextSize) => {
            setPage(nextPage);
            setPageSize(nextSize);
          },
        }}
      />

      <Modal
        title="新建项目"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleCreate}
        confirmLoading={createMutation.isPending}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, whitespace: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="例如：固态电解质性能研究" maxLength={300} />
          </Form.Item>
          <Form.Item name="description" label="项目描述">
            <Input.TextArea rows={4} placeholder="说明项目目标、范围或研究方向" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
