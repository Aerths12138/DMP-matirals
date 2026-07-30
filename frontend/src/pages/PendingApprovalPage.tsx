import { Result, Button, Typography } from 'antd';
import { LogoutOutlined } from '@ant-design/icons';
import { useAuthStore } from '../stores/authStore';
import { logout } from '../api/auth';
import { useNavigate } from 'react-router-dom';

const { Text } = Typography;

export default function PendingApprovalPage() {
  const navigate = useNavigate();
  const { user, logout: logoutStore } = useAuthStore();

  const handleLogout = async () => {
    await logout();
    logoutStore();
    navigate('/login');
  };

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: '#f0f2f5',
    }}>
      <Result
        status="info"
        title="账户审核中"
        subTitle={
          <div>
            <p>你的账户 <strong>{user?.username}</strong> 已注册成功，但需要管理员审核后才能使用。</p>
            <p>请联系管理员为你分配角色和权限。</p>
          </div>
        }
        extra={[
          <Button key="logout" icon={<LogoutOutlined />} onClick={handleLogout}>
            退出登录
          </Button>,
          <Button key="refresh" type="primary" onClick={() => window.location.reload()}>
            刷新状态
          </Button>,
        ]}
      />
    </div>
  );
}
