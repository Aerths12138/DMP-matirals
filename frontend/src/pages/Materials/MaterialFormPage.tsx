import { useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Form, Input, Select, Button, Card, Space, message, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createMaterial, updateMaterial, fetchMaterial } from '../../api/materials';
import type { MaterialCreate } from '../../types/material';

const { Title } = Typography;

const MATERIAL_TYPES = [
  { label: '金属', value: 'metal' },
  { label: '聚合物', value: 'polymer' },
  { label: '陶瓷', value: 'ceramic' },
  { label: '复合材料', value: 'composite' },
  { label: '电池材料', value: 'battery' },
  { label: '其他', value: 'other' },
];

export default function MaterialFormPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const isEdit = !!id;
  const projectId = searchParams.get('project_id') || undefined;
  const returnPath = projectId ? `/projects/${projectId}` : '/materials';

  const { data: existing, isLoading: loadingExisting } = useQuery({
    queryKey: ['material', id],
    queryFn: () => fetchMaterial(id!),
    enabled: isEdit,
  });

  useEffect(() => {
    if (existing) {
      form.setFieldsValue(existing);
    }
  }, [existing, form]);

  const createMutation = useMutation({
    mutationFn: (data: MaterialCreate) => createMaterial(data),
    onSuccess: (result) => {
      message.success('材料创建成功。请在下方添加属性。');
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: ['project-materials', projectId] });
      }
      navigate(projectId ? returnPath : `/materials/${result.id}`);
    },
    onError: () => message.error('创建失败'),
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<MaterialCreate>) => updateMaterial(id!, data),
    onSuccess: () => {
      message.success('材料更新成功');
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      navigate(`/materials/${id}`);
    },
    onError: () => message.error('更新失败'),
  });

  const onFinish = (values: Record<string, unknown>) => {
    const body: MaterialCreate = {
      name: values.name as string,
      material_type: values.material_type as string,
      formula_string: values.formula_string as string | undefined,
      hill_formula: values.hill_formula as string | undefined,
      aliases: values.aliases ? (values.aliases as string).split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      description: values.description as string | undefined,
      composition: [],
      metadata: {},
      project_id: projectId,
    };

    if (isEdit) {
      updateMutation.mutate(body);
    } else {
      createMutation.mutate(body);
    }
  };

  const isLoading = isEdit && loadingExisting;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(returnPath)}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>{isEdit ? '编辑材料' : '新建材料'}</Title>
      </div>

      <Card style={{ maxWidth: 800 }} loading={isLoading}>
        <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ material_type: 'polymer', aliases: '', composition: '[]' }}>
          <Form.Item name="name" label="材料名称" rules={[{ required: true, message: '请输入材料名称' }]}>
            <Input placeholder="例如: PVDF-HFP Polymer Blend" />
          </Form.Item>
          <Form.Item name="material_type" label="材料类型" rules={[{ required: true }]}>
            <Select options={MATERIAL_TYPES} />
          </Form.Item>
          <Form.Item name="formula_string" label="化学式">
            <Input placeholder="例如: (C2H2F2)n-(C3F6)m" />
          </Form.Item>
          <Form.Item name="hill_formula" label="Hill公式">
            <Input placeholder="标准Hill表达式" />
          </Form.Item>
          <Form.Item name="aliases" label="别名（逗号分隔）">
            <Input placeholder="PVDF-HFP, Kynar Flex" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} placeholder="材料描述..." />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={createMutation.isPending || updateMutation.isPending}>
                {isEdit ? '保存修改' : '创建材料'}
              </Button>
              <Button onClick={() => navigate(returnPath)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
