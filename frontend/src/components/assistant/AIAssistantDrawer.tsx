import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Avatar,
  Button,
  Card,
  Drawer,
  Empty,
  Input,
  Popconfirm,
  Space,
  Tag,
  Tooltip,
  Typography,
  message as antdMessage,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  RobotOutlined,
  SendOutlined,
  UndoOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import {
  chatWithAssistant,
  confirmAssistantAction,
  listAssistantBackups,
  restoreAssistantBackup,
  type AssistantBackup,
  type AssistantMessage,
  type PendingAssistantAction,
} from '../../api/assistant';
import {
  canConfirmAssistantAction,
  updateAssistantActionStatus,
  type AssistantActionStatus,
} from './actionState';

interface AIAssistantDrawerProps {
  open: boolean;
  onClose: () => void;
  contextPath: string;
}

interface DisplayMessage extends AssistantMessage {
  id: string;
}

interface DisplayAction extends PendingAssistantAction {
  status: AssistantActionStatus;
}

const WELCOME_MESSAGE = '你好，我可以回答材料领域问题，也可以查询平台数据。需要新增、修改或删除数据时，我会先生成操作预览，由你确认后才执行。';

function createId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function errorDetail(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join('；');
  if (error?.code === 'ECONNABORTED') return '请求超时，请稍后重试。';
  return 'AI 助手暂时不可用，请稍后重试。';
}

export default function AIAssistantDrawer({
  open,
  onClose,
  contextPath,
}: AIAssistantDrawerProps) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<DisplayMessage[]>([
    { id: createId(), role: 'assistant', content: WELCOME_MESSAGE },
  ]);
  const [actions, setActions] = useState<DisplayAction[]>([]);
  const [backups, setBackups] = useState<AssistantBackup[]>([]);
  const [loadingBackups, setLoadingBackups] = useState(false);
  const [restoringBackupId, setRestoringBackupId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);

  const conversation = useMemo(
    () => messages.map(({ role, content }) => ({ role, content })),
    [messages],
  );

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingBackups(true);
    listAssistantBackups()
      .then((items) => {
        if (!cancelled) setBackups(items);
      })
      .catch(() => {
        if (!cancelled) setBackups([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingBackups(false);
      });
    return () => { cancelled = true; };
  }, [open]);

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || sending) return;

    const userMessage: DisplayMessage = { id: createId(), role: 'user', content };
    const nextConversation = [
      ...conversation,
      { role: 'user' as const, content },
    ].slice(-30);
    setMessages((current) => [...current, userMessage]);
    setInput('');
    setSending(true);

    try {
      const response = await chatWithAssistant(nextConversation, contextPath);
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: response.message },
      ]);
      if (response.pending_actions.length) {
        setActions((current) => [
          ...current,
          ...response.pending_actions.map((action) => ({
            ...action,
            status: 'pending' as const,
          })),
        ]);
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: errorDetail(error) },
      ]);
    } finally {
      setSending(false);
    }
  };

  const updateActionStatus = (token: string, status: DisplayAction['status']) => {
    setActions((current) => (
      updateAssistantActionStatus(current, token, status)
    ));
  };

  const confirmAction = async (action: DisplayAction) => {
    updateActionStatus(action.token, 'executing');
    try {
      const result = await confirmAssistantAction(action.token);
      updateActionStatus(action.token, 'completed');
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: result.message },
      ]);
      if (result.backup) {
        setBackups((current) => [
          result.backup!,
          ...current.filter((item) => item.id !== result.backup!.id),
        ]);
      }
      await queryClient.invalidateQueries();
      antdMessage.success(result.message);
    } catch (error) {
      updateActionStatus(action.token, 'pending');
      antdMessage.error(errorDetail(error));
    }
  };

  const restoreBackup = async (backup: AssistantBackup) => {
    setRestoringBackupId(backup.id);
    try {
      const result = await restoreAssistantBackup(backup.id);
      setBackups((current) => current.filter((item) => item.id !== backup.id));
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: result.message },
      ]);
      await queryClient.invalidateQueries();
      antdMessage.success(result.message);
    } catch (error) {
      antdMessage.error(errorDetail(error));
    } finally {
      setRestoringBackupId(null);
    }
  };

  const clearConversation = () => {
    setMessages([{ id: createId(), role: 'assistant', content: WELCOME_MESSAGE }]);
    setActions([]);
    setInput('');
  };

  const operationLabel = {
    create: '新增',
    update: '修改',
    delete: '删除',
  } as const;

  return (
    <Drawer
      title={
        <Space>
          <RobotOutlined style={{ color: '#1677ff' }} />
          <span>AI 数据助手</span>
          <Tag color="blue">DeepSeek</Tag>
        </Space>
      }
      placement="right"
      width="min(460px, 100vw)"
      open={open}
      onClose={onClose}
      extra={
        <Tooltip title="清空本次对话和未执行操作">
          <Button type="text" icon={<DeleteOutlined />} onClick={clearConversation} />
        </Tooltip>
      }
      styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
    >
      <div style={{ padding: '10px 16px 0' }}>
        <Alert
          type="info"
          showIcon
          message="查询会自动执行；任何数据变更都需要你确认。"
        />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {messages.length === 0 ? (
          <Empty description="开始一段对话" />
        ) : (
          messages.map((item) => (
            <div
              key={item.id}
              style={{
                display: 'flex',
                flexDirection: item.role === 'user' ? 'row-reverse' : 'row',
                gap: 8,
                marginBottom: 16,
                alignItems: 'flex-start',
              }}
            >
              <Avatar
                size="small"
                icon={item.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                style={{ background: item.role === 'user' ? '#1677ff' : '#52c41a' }}
              />
              <div
                style={{
                  maxWidth: '82%',
                  padding: '9px 12px',
                  borderRadius: 10,
                  background: item.role === 'user' ? '#e6f4ff' : '#f5f5f5',
                  whiteSpace: 'pre-wrap',
                  overflowWrap: 'anywhere',
                }}
              >
                <Typography.Text>{item.content}</Typography.Text>
              </div>
            </div>
          ))
        )}

        {sending && (
          <div style={{ color: '#8c8c8c', margin: '0 0 16px 40px' }}>
            AI 正在思考并检查数据权限…
          </div>
        )}

        {(loadingBackups || backups.length > 0) && (
          <div style={{ marginBottom: 16 }}>
            <Typography.Title level={5} style={{ margin: '0 0 8px' }}>
              可回退版本
            </Typography.Title>
            {loadingBackups && backups.length === 0 ? (
              <Typography.Text type="secondary">正在加载临时备份…</Typography.Text>
            ) : (
              backups.map((backup) => (
                <Card
                  key={backup.id}
                  size="small"
                  style={{ marginBottom: 8, borderColor: '#13c2c2' }}
                >
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag color="cyan">{operationLabel[backup.operation]}前版本</Tag>
                      <Typography.Text strong>{backup.entity_name}</Typography.Text>
                    </Space>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      有效期至 {new Date(backup.expires_at).toLocaleString()}
                    </Typography.Text>
                    <Popconfirm
                      title="确认回退到上一个版本？"
                      description="回退前会重新检查权限；更新后的当前内容将被旧版本替换。"
                      okText="确认回退"
                      cancelText="取消"
                      onConfirm={() => restoreBackup(backup)}
                    >
                      <Button
                        size="small"
                        icon={<UndoOutlined />}
                        loading={restoringBackupId === backup.id}
                      >
                        回退
                      </Button>
                    </Popconfirm>
                  </Space>
                </Card>
              ))
            )}
          </div>
        )}

        {actions.map((action) => (
          <Card
            key={action.token}
            size="small"
            title={
              <Space>
                <Tag color={action.operation === 'delete' ? 'red' : 'orange'}>
                  {operationLabel[action.operation]}
                </Tag>
                <span>待确认操作</span>
              </Space>
            }
            style={{ marginBottom: 12, borderColor: '#faad14' }}
          >
            <Typography.Paragraph style={{ marginBottom: 8 }}>
              {action.summary}
            </Typography.Paragraph>
            <details style={{ marginBottom: 12 }}>
              <summary style={{ cursor: 'pointer', color: '#1677ff' }}>查看字段详情</summary>
              <pre
                style={{
                  margin: '8px 0 0',
                  padding: 8,
                  maxHeight: 180,
                  overflow: 'auto',
                  background: '#fafafa',
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {JSON.stringify(action.arguments, null, 2)}
              </pre>
            </details>

            {canConfirmAssistantAction(action.status) && (
              <Space>
                <Popconfirm
                  title={`确认${operationLabel[action.operation]}？`}
                  description={
                    action.operation === 'delete'
                      ? '确认后将删除；服务器会保留 24 小时临时备份。'
                      : '确认后将写入数据库，并保留操作前的临时版本。'
                  }
                  okText="确认执行"
                  cancelText="返回"
                  okButtonProps={{ danger: action.operation === 'delete' }}
                  onConfirm={() => confirmAction(action)}
                >
                  <Button
                    type="primary"
                    danger={action.operation === 'delete'}
                    size="small"
                    icon={<CheckOutlined />}
                  >
                    确认执行
                  </Button>
                </Popconfirm>
                <Button
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={() => updateActionStatus(action.token, 'cancelled')}
                >
                  取消
                </Button>
              </Space>
            )}
            {action.status === 'executing' && <Tag color="processing">正在执行</Tag>}
            {action.status === 'completed' && <Tag color="success">已执行</Tag>}
            {action.status === 'cancelled' && <Tag>已取消</Tag>}
          </Card>
        ))}
      </div>

      <div style={{ padding: 16, borderTop: '1px solid #f0f0f0', background: '#fff' }}>
        <Input.TextArea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onPressEnter={(event) => {
            if (!event.shiftKey) {
              event.preventDefault();
              sendMessage();
            }
          }}
          placeholder="询问材料知识，或让我查询、维护平台数据…"
          autoSize={{ minRows: 2, maxRows: 5 }}
          maxLength={6000}
          disabled={sending}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={sendMessage}
          loading={sending}
          disabled={!input.trim()}
          block
          style={{ marginTop: 8 }}
        >
          发送
        </Button>
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
          AI 可能出错，请在执行数据变更前核对操作预览。
        </Typography.Text>
      </div>
    </Drawer>
  );
}
