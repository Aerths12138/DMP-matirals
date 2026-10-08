import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, theme, Dropdown, Avatar, Spin, Result, Modal, Form, Input, Tabs, message } from 'antd';
import {
  DashboardOutlined,
  ExperimentOutlined,
  BarChartOutlined,
  SearchOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ImportOutlined,
  FolderOpenOutlined,
  ProjectOutlined,
  LockOutlined,
  MailOutlined,
  IdcardOutlined,
  BankOutlined,
  HistoryOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { fetchCurrentUser, logout } from '../../api/auth';
import { updateUser } from '../../api/users';
import apiClient from '../../api/client';
import PendingApprovalPage from '../../pages/PendingApprovalPage';

const { Header, Sider, Content } = Layout;

const ALL_MENU_ITEMS = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表板', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/assistant', icon: <RobotOutlined />, label: 'AI 助手', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/materials', icon: <ExperimentOutlined />, label: '材料管理', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/visualizations', icon: <BarChartOutlined />, label: '数据可视化', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目协作', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/collections', icon: <FolderOpenOutlined />, label: '子集管理', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/search', icon: <SearchOutlined />, label: '搜索', roles: ['admin', 'researcher', 'viewer'] },
  { key: '/import', icon: <ImportOutlined />, label: '数据导入', roles: ['admin', 'researcher'] },
  { key: '/users', icon: <UserOutlined />, label: '用户管理', roles: ['admin'] },
  { key: '/audit-logs', icon: <HistoryOutlined />, label: '审计日志', roles: ['admin'] },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, setUser, logout: logoutStore } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { token: { colorBgContainer } } = theme.useToken();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Settings modal
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();

  // Filter menu by user role
  const menuItems = ALL_MENU_ITEMS.filter(
    (item) => user && item.roles.includes(user.role_name || '')
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchCurrentUser()
      .then((u) => {
        if (!cancelled) {
          setUser(u);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const msg = err?.code === 'ECONNABORTED' || err?.message?.includes('timeout')
            ? '无法连接到后端服务，请检查平台服务状态或联系管理员'
            : '获取用户信息失败，请重新登录';
          setError(msg);
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, []);

  const handleLogout = async () => {
    await logout();
    logoutStore();
    navigate('/login');
  };

  // Profile update
  const profileMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => updateUser(user!.id, body),
    onSuccess: () => {
      message.success('个人信息已更新');
      // Refresh user in store
      fetchCurrentUser().then((u) => setUser(u));
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || '更新失败';
      message.error(msg);
    },
  });

  // Password change
  const passwordMutation = useMutation({
    mutationFn: (body: { old_password: string; new_password: string }) =>
      apiClient.post('/users/change-password', body),
    onSuccess: () => {
      message.success('密码已修改');
      passwordForm.resetFields();
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || '修改失败';
      message.error(msg);
    },
  });

  const handleSaveProfile = async () => {
    const values = await profileForm.validateFields();
    profileMutation.mutate({
      display_name: values.display_name,
      email: values.email,
      department: values.department || undefined,
    });
  };

  const handleChangePassword = async () => {
    const values = await passwordForm.validateFields();
    passwordMutation.mutate({
      old_password: values.old_password,
      new_password: values.new_password,
    });
  };

  const openSettings = () => {
    profileForm.setFieldsValue({
      display_name: user?.display_name || '',
      email: user?.email || '',
      department: user?.department || '',
    });
    passwordForm.resetFields();
    setSettingsOpen(true);
  };

  const selectedKey = '/' + location.pathname.split('/')[1];

  // Show pending approval page for unapproved users
  if (!loading && !error && user && !user.is_approved) {
    return <PendingApprovalPage />;
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', gap: 16 }}>
        <Spin size="large" />
        <div style={{ color: '#666' }}>Connecting to server...</div>
      </div>
    );
  }

  if (error) {
    return (
      <Result
        status="warning"
        title="连接失败"
        subTitle={error}
        extra={[
          <Button key="retry" type="primary" onClick={() => window.location.reload()}>重试</Button>,
          <Button key="login" onClick={() => { logoutStore(); navigate('/login'); }}>返回登录</Button>,
        ]}
      />
    );
  }

  const settingsTabs = [
    {
      key: 'profile',
      label: '个人信息',
      children: (
        <Form form={profileForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="display_name" label="显示名称">
            <Input prefix={<IdcardOutlined />} placeholder="显示名称" />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '请输入有效邮箱' }]}>
            <Input prefix={<MailOutlined />} placeholder="邮箱" />
          </Form.Item>
          <Form.Item name="department" label="部门/单位">
            <Input prefix={<BankOutlined />} placeholder="部门或单位" />
          </Form.Item>
          <Button type="primary" onClick={handleSaveProfile} loading={profileMutation.isPending} block>
            保存
          </Button>
        </Form>
      ),
    },
    {
      key: 'password',
      label: '修改密码',
      children: (
        <Form form={passwordForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="old_password" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="当前密码" />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[
            { required: true, message: '请输入新密码' },
            { min: 8, message: '密码至少 8 位' },
          ]}>
            <Input.Password prefix={<LockOutlined />} placeholder="新密码（至少8位）" />
          </Form.Item>
          <Button type="primary" onClick={handleChangePassword} loading={passwordMutation.isPending} block>
            修改密码
          </Button>
        </Form>
      ),
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={sidebarCollapsed}>
        <div style={{ height: 32, margin: 16, color: '#fff', textAlign: 'center', fontWeight: 'bold', fontSize: sidebarCollapsed ? 14 : 18 }}>
          {sidebarCollapsed ? 'DMP' : 'Materials DMP'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 24px', background: colorBgContainer, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Button
            type="text"
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleSidebar}
          />
          <Button
            type="primary"
            ghost
            icon={<RobotOutlined />}
            onClick={() => navigate('/assistant')}
            style={{ marginLeft: 'auto', marginRight: 12 }}
          >
            AI 助手
          </Button>
          <Dropdown
            menu={{
              items: [
                { key: 'settings', icon: <SettingOutlined />, label: '设置' },
                { type: 'divider' },
                { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
              ],
              onClick: ({ key }) => {
                if (key === 'settings') openSettings();
                if (key === 'logout') handleLogout();
              },
            }}
          >
            <Avatar style={{ cursor: 'pointer', backgroundColor: '#1677ff' }} icon={<UserOutlined />} />
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: colorBgContainer, borderRadius: 8, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>

      {/* Settings Modal */}
      <Modal
        title="账户设置"
        open={settingsOpen}
        onCancel={() => setSettingsOpen(false)}
        footer={null}
        width={480}
      >
        <Tabs items={settingsTabs} />
      </Modal>

    </Layout>
  );
}
