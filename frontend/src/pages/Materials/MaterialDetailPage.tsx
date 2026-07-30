import { useParams, useNavigate } from 'react-router-dom';
import { Descriptions, Tag, Card, Tabs, Button, Spin, Typography } from 'antd';
import { EditOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { fetchMaterial } from '../../api/materials';
import { fetchProject } from '../../api/projects';
import AttachmentWorkbench from '../../components/files/AttachmentWorkbench';
import { useAuthStore } from '../../stores/authStore';
import PropertyEditor from './components/PropertyEditor';
import CompositionEditor from './components/CompositionEditor';
import TestEditor from './components/TestEditor';

const { Title } = Typography;

const MATERIAL_TYPE_LABELS: Record<string, string> = {
  metal: '金属',
  polymer: '聚合物',
  ceramic: '陶瓷',
  composite: '复合材料',
  battery: '电池材料',
  other: '其他',
};

export default function MaterialDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUser = useAuthStore((state) => state.user);

  const { data: material, isLoading } = useQuery({
    queryKey: ['material', id],
    queryFn: () => fetchMaterial(id!),
    enabled: !!id,
  });
  const { data: project } = useQuery({
    queryKey: ['project', material?.project_id],
    queryFn: () => fetchProject(material!.project_id!),
    enabled: Boolean(material?.project_id),
  });
  const projectRole = project?.members.find(
    (member) => member.user_id === currentUser?.id
  )?.role;
  const hasSystemWriteAccess = currentUser?.role_name === 'researcher';
  const canEdit =
    currentUser?.role_name === 'admin' ||
    (hasSystemWriteAccess &&
      (!material?.project_id || projectRole === 'owner' || projectRole === 'editor'));

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!material) return <div>材料不存在</div>;

  const tabs = [
    {
      key: 'overview',
      label: '概述',
      children: (
        <Card>
          <Descriptions column={2} bordered>
            <Descriptions.Item label="名称">{material.name}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag>{MATERIAL_TYPE_LABELS[material.material_type] || material.material_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="化学式">{material.formula_string || '-'}</Descriptions.Item>
            <Descriptions.Item label="Hill公式">{material.hill_formula || '-'}</Descriptions.Item>
            <Descriptions.Item label="别名">{material.aliases?.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{new Date(material.created_at).toLocaleDateString('zh-CN')}</Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>{material.description || '-'}</Descriptions.Item>
          </Descriptions>
        </Card>
      ),
    },
    {
      key: 'composition',
      label: '配方',
      children: <CompositionEditor materialId={id!} composition={material.composition || []} />,
    },
    {
      key: 'properties',
      label: '属性',
      children: <PropertyEditor materialId={id!} />,
    },
    {
      key: 'tests',
      label: '测试',
      children: <TestEditor materialId={id!} />,
    },
    {
      key: 'attachments',
      label: '原始数据与附件',
      children: <AttachmentWorkbench parentType="material" parentId={id!} canEdit={canEdit} />,
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/materials')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>{material.name}</Title>
        {canEdit && (
          <Button type="primary" icon={<EditOutlined />} onClick={() => navigate(`/materials/${id}/edit`)}>
            编辑
          </Button>
        )}
      </div>
      <Tabs items={tabs} />
    </div>
  );
}
