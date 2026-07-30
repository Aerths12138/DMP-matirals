import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message, Tabs } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, IdcardOutlined, BankOutlined } from '@ant-design/icons';
import { login, register } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

const { Title } = Typography;

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const navigate = useNavigate();
  const { setUser } = useAuthStore();

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const tokenResp = await login(values.username, values.password);
      console.log('Login OK, tokens stored');

      const { fetchCurrentUser } = await import('../api/auth');
      const user = await fetchCurrentUser();
      setUser(user);
      message.success('登录成功');
      navigate('/dashboard');
    } catch (err: any) {
      const msg = err?.response?.data?.detail
        || err?.message
        || '登录失败，请检查后端是否运行';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: {
    username: string;
    email: string;
    password: string;
    display_name?: string;
    department?: string;
  }) => {
    setLoading(true);
    try {
      // Register the user
      await register({
        username: values.username,
        email: values.email,
        password: values.password,
        display_name: values.display_name,
        department: values.department,
      });
      message.success('注册成功，正在登录...');

      // Auto-login after registration
      const tokenResp = await login(values.username, values.password);
      const { fetchCurrentUser } = await import('../api/auth');
      const user = await fetchCurrentUser();
      setUser(user);
      navigate('/dashboard');
    } catch (err: any) {
      const msg = err?.response?.data?.detail
        || err?.message
        || '注册失败';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'login',
      label: '登录',
      children: (
        <Form form={loginForm} onFinish={handleLogin} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mode === 'login' && loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'register',
      label: '注册',
      children: (
        <Form form={registerForm} onFinish={handleRegister} size="large" layout="vertical">
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少 3 个字符' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="邮箱" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少 8 位' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码（至少8位）" />
          </Form.Item>
          <Form.Item name="display_name">
            <Input prefix={<IdcardOutlined />} placeholder="显示名称（可选）" />
          </Form.Item>
          <Form.Item name="department">
            <Input prefix={<BankOutlined />} placeholder="部门/单位（可选）" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mode === 'register' && loading} block>
              注册
            </Button>
          </Form.Item>
        </Form>
      ),
    },
  ];

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: '#f0f2f5',
    }}>
      <Card style={{ width: 420, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          Materials DMP
        </Title>
        <Tabs
          activeKey={mode}
          onChange={(key) => setMode(key as 'login' | 'register')}
          centered
          items={tabItems}
        />
      </Card>
    </div>
  );
}
