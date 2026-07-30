import { Card, Col, Row, Statistic, Typography, Table, Tag, Spin, Empty, Progress } from 'antd';
import {
  ExperimentOutlined, DatabaseOutlined, UserOutlined,
  BarChartOutlined, FireOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/client';

const { Title, Text } = Typography;

interface DashboardStats {
  materials_total: number;
  users_total: number;
  tests_total: number;
  material_types: { type: string; count: number }[];
  recent_materials: {
    id: string;
    name: string;
    material_type: string;
    formula_string?: string;
    created_at: string;
  }[];
  recent_tests: {
    id: string;
    test_name: string;
    test_method?: string;
    material_id: string;
    created_at: string;
  }[];
}

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  metal: { label: '金属', color: '#1677ff' },
  polymer: { label: '聚合物', color: '#52c41a' },
  ceramic: { label: '陶瓷', color: '#fa8c16' },
  composite: { label: '复合材料', color: '#722ed1' },
  battery: { label: '电池材料', color: '#f5222d' },
  other: { label: '其他', color: '#8c8c8c' },
};

const TYPE_BAR_COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#722ed1', '#f5222d', '#8c8c8c'];

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: () => apiClient.get('/dashboard/stats').then((r) => r.data),
    refetchInterval: 30000, // refresh every 30s
  });

  if (isLoading) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  }

  if (!data) {
    return <Empty description="无法加载仪表板数据" />;
  }

  const maxTypeCount = Math.max(...data.material_types.map((t) => t.count), 1);

  const materialColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (text: string, r: any) => <a onClick={() => navigate(`/materials/${r.id}`)}>{text}</a>,
    },
    {
      title: '类型',
      dataIndex: 'material_type',
      width: 100,
      render: (t: string) => {
        const info = TYPE_LABELS[t] || { label: t, color: '#8c8c8c' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '化学式',
      dataIndex: 'formula_string',
      width: 180,
      render: (t: string) => t || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 160,
      render: (t: string) => t ? new Date(t).toLocaleDateString('zh-CN') : '-',
    },
  ];

  const testColumns = [
    {
      title: '测试名称',
      dataIndex: 'test_name',
    },
    {
      title: '方法',
      dataIndex: 'test_method',
      width: 120,
      render: (t: string) => t ? <Tag>{t}</Tag> : '-',
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 160,
      render: (t: string) => t ? new Date(t).toLocaleDateString('zh-CN') : '-',
    },
  ];

  return (
    <div>
      <Title level={4}>仪表板</Title>

      {/* Stat cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate('/materials')}>
            <Statistic
              title="材料总数"
              value={data.materials_total}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="实验测试"
              value={data.tests_total}
              prefix={<ExperimentOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="用户数"
              value={data.users_total}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* Material type distribution */}
        <Col xs={24} lg={10}>
          <Card
            title={<span><BarChartOutlined /> 材料类型分布</span>}
            style={{ height: '100%' }}
          >
            {data.material_types.length === 0 ? (
              <Empty description="暂无数据" />
            ) : (
              data.material_types.map((t, i) => {
                const info = TYPE_LABELS[t.type] || { label: t.type, color: TYPE_BAR_COLORS[i % TYPE_BAR_COLORS.length] };
                const pct = Math.round((t.count / data.materials_total) * 100);
                return (
                  <div key={t.type} style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text>{info.label}</Text>
                      <Text type="secondary">{t.count} ({pct}%)</Text>
                    </div>
                    <Progress
                      percent={pct}
                      showInfo={false}
                      strokeColor={info.color}
                      size="small"
                    />
                  </div>
                );
              })
            )}
          </Card>
        </Col>

        {/* Recent materials */}
        <Col xs={24} lg={14}>
          <Card
            title={<span><ClockCircleOutlined /> 最近添加的材料</span>}
            extra={<a onClick={() => navigate('/materials')}>查看全部</a>}
          >
            <Table
              columns={materialColumns}
              dataSource={data.recent_materials}
              rowKey="id"
              pagination={false}
              size="small"
              locale={{ emptyText: '暂无材料' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Recent tests */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            title={<span><FireOutlined /> 最近实验测试</span>}
          >
            <Table
              columns={testColumns}
              dataSource={data.recent_tests}
              rowKey="id"
              pagination={false}
              size="small"
              locale={{ emptyText: '暂无测试' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
