import { useState } from 'react';
import { Table, Tag, Typography, Select, Space, Card, Descriptions, Modal, Button } from 'antd';
import { HistoryOutlined, EyeOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/client';

const { Title, Text, Paragraph } = Typography;

const ACTION_COLORS: Record<string, string> = {
  CREATE: 'green', UPDATE: 'blue', DELETE: 'red', EXPORT: 'orange',
  LOGIN: 'purple', RUN_ANALYSIS: 'cyan',
};

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState<string | undefined>();
  const [entityFilter, setEntityFilter] = useState<string | undefined>();
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState<any>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', { page, size: 20, action: actionFilter, entity_type: entityFilter }],
    queryFn: () =>
      apiClient
        .get('/audit-logs', {
          params: { page, size: 20, action: actionFilter, entity_type: entityFilter },
        })
        .then((r) => r.data),
  });

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 170,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      dataIndex: 'action',
      width: 110,
      render: (a: string) => (
        <Tag color={ACTION_COLORS[a] || 'default'}>{a}</Tag>
      ),
    },
    {
      title: '对象类型',
      dataIndex: 'entity_type',
      width: 100,
      render: (t: string) => <Tag>{t}</Tag>,
    },
    {
      title: '对象ID',
      dataIndex: 'entity_id',
      width: 120,
      ellipsis: true,
      render: (id: string) => id ? <Text copyable={{ text: id }} style={{ fontSize: 12 }}>{id.slice(0, 8)}...</Text> : '-',
    },
    {
      title: '用户ID',
      dataIndex: 'user_id',
      width: 120,
      ellipsis: true,
      render: (id: string) => id ? <Text style={{ fontSize: 12 }}>{id.slice(0, 8)}...</Text> : '-',
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      width: 130,
      render: (ip: string) => ip || '-',
    },
    {
      title: '详情',
      width: 70,
      render: (_: unknown, record: any) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => { setSelectedLog(record); setDetailOpen(true); }}
        >
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}><HistoryOutlined /> 审计日志</Title>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="筛选操作类型"
          value={actionFilter}
          onChange={(v) => { setActionFilter(v); setPage(1); }}
          style={{ width: 140 }}
          options={[
            { label: 'CREATE', value: 'CREATE' },
            { label: 'UPDATE', value: 'UPDATE' },
            { label: 'DELETE', value: 'DELETE' },
            { label: 'EXPORT', value: 'EXPORT' },
            { label: 'LOGIN', value: 'LOGIN' },
          ]}
        />
        <Select
          allowClear
          placeholder="筛选对象类型"
          value={entityFilter}
          onChange={(v) => { setEntityFilter(v); setPage(1); }}
          style={{ width: 140 }}
          options={[
            { label: 'material', value: 'material' },
            { label: 'user', value: 'user' },
            { label: 'experiment', value: 'experiment' },
            { label: 'characterization', value: 'characterization' },
          ]}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={data?.items || []}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total || 0,
          onChange: (p) => setPage(p),
          showTotal: (total) => `共 ${total} 条`,
        }}
      />

      <Modal
        title="变更详情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={600}
      >
        {selectedLog && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="操作">{selectedLog.action}</Descriptions.Item>
            <Descriptions.Item label="对象类型">{selectedLog.entity_type}</Descriptions.Item>
            <Descriptions.Item label="对象ID">{selectedLog.entity_id}</Descriptions.Item>
            <Descriptions.Item label="用户ID">{selectedLog.user_id}</Descriptions.Item>
            <Descriptions.Item label="IP 地址">{selectedLog.ip_address || '-'}</Descriptions.Item>
            <Descriptions.Item label="时间">{selectedLog.created_at ? new Date(selectedLog.created_at).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
            <Descriptions.Item label="变更内容">
              {selectedLog.changes ? (
                <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                  {JSON.stringify(selectedLog.changes, null, 2)}
                </pre>
              ) : (
                <Text type="secondary">无变更数据</Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
