import {
  Alert, Button, Card, Col, Empty, Row, Skeleton, Space, Statistic, Table, Tag, Typography,
} from 'antd';
import {
  AppstoreOutlined, ArrowRightOutlined, BarChartOutlined, ClockCircleOutlined,
  DatabaseOutlined, ExperimentOutlined, FireOutlined, ImportOutlined,
  PlusOutlined, ProjectOutlined, SearchOutlined, TeamOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip as ChartTooltip } from 'recharts';
import apiClient from '../../api/client';
import { useAuthStore } from '../../stores/authStore';
import './DashboardPage.css';

const { Title, Text } = Typography;

interface DashboardStats {
  materials_total: number;
  users_total: number;
  tests_total: number;
  material_types: { type: string; count: number }[];
  recent_materials: { id: string; name: string; material_type: string; formula_string?: string; created_at: string }[];
  recent_tests: { id: string; test_name: string; test_method?: string; material_id: string; created_at: string }[];
}

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  metal: { label: '金属', color: '#2563eb' },
  polymer: { label: '聚合物', color: '#10b981' },
  ceramic: { label: '陶瓷', color: '#f59e0b' },
  composite: { label: '复合材料', color: '#8b5cf6' },
  battery: { label: '电池材料', color: '#ef4444' },
  other: { label: '其他', color: '#64748b' },
};
const FALLBACK_COLORS = ['#0ea5e9', '#14b8a6', '#f97316', '#a855f7', '#e11d48', '#64748b'];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return '夜深了';
  if (hour < 12) return '早上好';
  if (hour < 18) return '下午好';
  return '晚上好';
}

function formatDate(value?: string): string {
  return value ? new Date(value).toLocaleDateString('zh-CN') : '—';
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const canWrite = user?.role_name === 'admin' || user?.role_name === 'researcher';
  const { data, isLoading, isError, refetch } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: () => apiClient.get('/dashboard/stats').then((response) => response.data),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <Skeleton active paragraph={{ rows: 3 }} className="dashboard-loading-hero" />
        <Row gutter={[16, 16]}>{[1, 2, 3, 4].map((key) => <Col xs={24} sm={12} xl={6} key={key}><Card><Skeleton active paragraph={false} /></Card></Col>)}</Row>
      </div>
    );
  }
  if (isError || !data) {
    return <Alert type="error" showIcon message="首页数据加载失败" action={<Button onClick={() => refetch()}>重新加载</Button>} />;
  }

  const displayName = user?.display_name || user?.username || '研究者';
  const pieData = data.material_types.map((item, index) => ({
    ...item,
    label: TYPE_LABELS[item.type]?.label || item.type,
    color: TYPE_LABELS[item.type]?.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length],
  }));
  const quickActions = [
    ...(canWrite ? [
      { label: '新增材料', description: '建立一条材料档案', icon: <PlusOutlined />, path: '/materials/new', color: 'blue' },
      { label: '智能导入', description: '上传并自动整理数据', icon: <ImportOutlined />, path: '/import', color: 'violet' },
    ] : []),
    { label: '项目空间', description: '查看项目与样品', icon: <ProjectOutlined />, path: '/projects', color: 'cyan' },
    { label: '数据可视化', description: '比较与分析性能', icon: <BarChartOutlined />, path: '/visualizations', color: 'amber' },
    { label: '全局搜索', description: '快速定位平台数据', icon: <SearchOutlined />, path: '/search', color: 'slate' },
  ];

  const materialColumns = [
    {
      title: '材料名称', dataIndex: 'name',
      render: (value: string, record: DashboardStats['recent_materials'][number]) => (
        <Button type="link" className="dashboard-table-link" onClick={() => navigate(`/materials/${record.id}`)}>{value}</Button>
      ),
    },
    {
      title: '类型', dataIndex: 'material_type', width: 110,
      render: (value: string) => {
        const info = TYPE_LABELS[value] || { label: value, color: '#64748b' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    { title: '化学式', dataIndex: 'formula_string', width: 150, render: (value?: string) => value || '—' },
    { title: '录入日期', dataIndex: 'created_at', width: 130, render: formatDate },
  ];
  const testColumns = [
    {
      title: '测试名称', dataIndex: 'test_name',
      render: (value: string, record: DashboardStats['recent_tests'][number]) => (
        <Button type="link" className="dashboard-table-link" onClick={() => navigate(`/materials/${record.material_id}`)}>{value}</Button>
      ),
    },
    { title: '测试方法', dataIndex: 'test_method', render: (value?: string) => value ? <Tag>{value}</Tag> : <Text type="secondary">未记录</Text> },
    { title: '记录日期', dataIndex: 'created_at', width: 130, render: formatDate },
  ];

  return (
    <div className="dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-hero-orb dashboard-hero-orb-one" />
        <div className="dashboard-hero-orb dashboard-hero-orb-two" />
        <div className="dashboard-hero-content">
          <Text className="dashboard-eyebrow">MATERIALS DATA WORKSPACE</Text>
          <Title level={2}>{greeting()}，{displayName}</Title>
          <Text className="dashboard-hero-copy">汇集材料、实验与测量数据，让每一次导入都可追溯、可查询、可分析。</Text>
          <Space wrap className="dashboard-hero-actions">
            <Button type="primary" size="large" icon={canWrite ? <ImportOutlined /> : <DatabaseOutlined />} onClick={() => navigate(canWrite ? '/import' : '/materials')}>
              {canWrite ? '开始导入数据' : '浏览材料数据'}
            </Button>
            <Button size="large" className="dashboard-hero-secondary" onClick={() => navigate('/projects')}>进入项目空间 <ArrowRightOutlined /></Button>
          </Space>
        </div>
        <div className="dashboard-hero-summary">
          <div className="dashboard-hero-summary-label"><ClockCircleOutlined /> 平台实时概览</div>
          <div className="dashboard-hero-summary-value">{data.materials_total + data.tests_total}</div>
          <div className="dashboard-hero-summary-caption">条材料与实验数据记录</div>
          <div className="dashboard-hero-summary-foot">数据每 30 秒自动刷新</div>
        </div>
      </section>

      <Row gutter={[16, 16]} className="dashboard-stat-row">
        {[
          { label: '材料档案', value: data.materials_total, icon: <DatabaseOutlined />, color: 'blue', path: '/materials', note: '平台可见材料' },
          { label: '实验测试', value: data.tests_total, icon: <ExperimentOutlined />, color: 'green', path: '/visualizations', note: '已记录测试' },
          { label: '材料类别', value: data.material_types.length, icon: <AppstoreOutlined />, color: 'orange', path: '/materials', note: '当前覆盖类型' },
          { label: '协作成员', value: data.users_total, icon: <TeamOutlined />, color: 'purple', path: user?.role_name === 'admin' ? '/users' : '/projects', note: '平台注册用户' },
        ].map((item) => (
          <Col xs={24} sm={12} xl={6} key={item.label}>
            <Card className="dashboard-stat-card" hoverable onClick={() => navigate(item.path)}>
              <div className={`dashboard-stat-icon dashboard-stat-icon-${item.color}`}>{item.icon}</div>
              <div><Statistic title={item.label} value={item.value} /><Text type="secondary" className="dashboard-stat-note">{item.note}</Text></div>
              <ArrowRightOutlined className="dashboard-stat-arrow" />
            </Card>
          </Col>
        ))}
      </Row>

      <Card className="dashboard-section-card dashboard-quick-card" title="快捷入口">
        <Row gutter={[12, 12]}>
          {quickActions.map((action) => (
            <Col xs={24} sm={12} lg={quickActions.length > 4 ? 8 : 6} key={action.path}>
              <button type="button" className="dashboard-quick-action" onClick={() => navigate(action.path)}>
                <span className={`dashboard-quick-icon dashboard-quick-icon-${action.color}`}>{action.icon}</span>
                <span className="dashboard-quick-text"><strong>{action.label}</strong><small>{action.description}</small></span>
                <ArrowRightOutlined />
              </button>
            </Col>
          ))}
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card className="dashboard-section-card dashboard-distribution-card" title={<Space><BarChartOutlined />材料类型分布</Space>}>
            {pieData.length === 0 ? <Empty description="暂无材料类型数据" /> : (
              <div className="dashboard-distribution-layout">
                <div className="dashboard-pie-wrap">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} dataKey="count" nameKey="label" innerRadius="58%" outerRadius="82%" paddingAngle={3} stroke="none">
                        {pieData.map((item) => <Cell key={item.type} fill={item.color} />)}
                      </Pie>
                      <ChartTooltip formatter={(value) => [`${value} 项`, '材料数量']} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="dashboard-pie-center"><strong>{data.materials_total}</strong><span>材料总数</span></div>
                </div>
                <div className="dashboard-distribution-legend">
                  {pieData.map((item) => {
                    const percent = data.materials_total ? Math.round(item.count / data.materials_total * 100) : 0;
                    return (
                      <div className="dashboard-legend-row" key={item.type}>
                        <span className="dashboard-legend-dot" style={{ background: item.color }} />
                        <Text>{item.label}</Text><Text strong>{item.count}</Text><Text type="secondary">{percent}%</Text>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <Card className="dashboard-section-card" title={<Space><ClockCircleOutlined />最近添加的材料</Space>} extra={<Button type="link" onClick={() => navigate('/materials')}>查看全部 <ArrowRightOutlined /></Button>}>
            <Table columns={materialColumns} dataSource={data.recent_materials} rowKey="id" pagination={false} size="middle" scroll={{ x: 620 }} locale={{ emptyText: '暂无材料' }} />
          </Card>
        </Col>
      </Row>

      <Card className="dashboard-section-card dashboard-recent-tests" title={<Space><FireOutlined />最近实验测试</Space>} extra={<Button type="link" onClick={() => navigate('/visualizations')}>进入可视化 <ArrowRightOutlined /></Button>}>
        <Table columns={testColumns} dataSource={data.recent_tests} rowKey="id" pagination={false} size="middle" scroll={{ x: 520 }} locale={{ emptyText: '暂无测试记录' }} />
      </Card>
    </div>
  );
}
