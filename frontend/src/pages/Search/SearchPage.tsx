import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Empty,
  Input,
  message,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';

import { fetchProjects } from '../../api/projects';
import { globalSearch } from '../../api/search';
import type { GlobalSearchResult, SearchEntityType } from '../../types/search';

const { Title, Text, Paragraph } = Typography;

const ENTITY_TYPES: Array<{
  label: string;
  value: SearchEntityType | '';
  color?: string;
}> = [
  { label: '全部', value: '' },
  { label: '项目', value: 'project', color: 'gold' },
  { label: '材料', value: 'material', color: 'blue' },
  { label: '实验', value: 'experiment', color: 'purple' },
  { label: '样品', value: 'sample', color: 'cyan' },
  { label: '表征', value: 'characterization', color: 'green' },
  { label: '附件', value: 'file', color: 'orange' },
];

const ENTITY_LABELS = Object.fromEntries(
  ENTITY_TYPES.filter((item) => item.value).map((item) => [item.value, item])
) as Record<SearchEntityType, { label: string; value: SearchEntityType; color?: string }>;

export default function SearchPage() {
  const navigate = useNavigate();
  const inputRef = useRef<any>(null);
  const [search, setSearch] = useState('');
  const [activeSearch, setActiveSearch] = useState('');
  const [entityType, setEntityType] = useState<SearchEntityType | ''>('');
  const [projectId, setProjectId] = useState<string>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const { data: projectData } = useQuery({
    queryKey: ['projects', 'search-filter'],
    queryFn: () => fetchProjects({ size: 200 }),
  });
  const projects = projectData?.items || [];
  const projectNames = new Map(projects.map((project) => [project.id, project.name]));

  const { data, isLoading } = useQuery({
    queryKey: [
      'global-search',
      {
        q: activeSearch,
        entity_type: entityType,
        project_id: projectId,
        page,
        size: pageSize,
      },
    ],
    queryFn: () =>
      globalSearch({
        q: activeSearch,
        entity_type: entityType || undefined,
        project_id: projectId,
        page,
        size: pageSize,
      }),
    enabled: hasSearched && Boolean(activeSearch),
  });

  const handleSearch = (value: string) => {
    const term = value.trim();
    if (!term) {
      message.warning('请输入搜索关键词');
      return;
    }
    setSearch(term);
    setActiveSearch(term);
    setPage(1);
    setHasSearched(true);
  };

  const handleEntityFilter = (value: SearchEntityType | '') => {
    setEntityType(value);
    setPage(1);
  };

  const openResult = (record: GlobalSearchResult) => {
    if (record.entity_type === 'project') {
      navigate(`/projects/${record.id}`);
      return;
    }
    if (record.entity_type === 'material') {
      navigate(`/materials/${record.id}`);
      return;
    }
    if (record.entity_type === 'file' && record.parent_type === 'material' && record.parent_id) {
      navigate(`/materials/${record.parent_id}`);
      return;
    }
    if (record.project_id) {
      navigate(`/projects/${record.project_id}`);
      return;
    }
    message.info('该历史记录没有可跳转的项目页面');
  };

  const columns: ColumnsType<GlobalSearchResult> = [
    {
      title: '类型',
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 100,
      render: (value: SearchEntityType) => {
        const entity = ENTITY_LABELS[value];
        return <Tag color={entity.color}>{entity.label}</Tag>;
      },
    },
    {
      title: '名称',
      dataIndex: 'title',
      key: 'title',
      width: 280,
      render: (title: string, record) => (
        <a onClick={() => openResult(record)}>{title}</a>
      ),
    },
    {
      title: '上下文',
      dataIndex: 'subtitle',
      key: 'subtitle',
      render: (value?: string) =>
        value ? (
          <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
            {value}
          </Paragraph>
        ) : (
          '-'
        ),
    },
    {
      title: '所属项目',
      dataIndex: 'project_id',
      key: 'project_id',
      width: 180,
      render: (value?: string) => (value && projectNames.get(value)) || '公共数据',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
      render: (value: string) => new Date(value).toLocaleString('zh-CN'),
    },
  ];

  const filters = (
    <Space wrap>
      <Select
        allowClear
        showSearch
        optionFilterProp="label"
        placeholder="全部项目"
        value={projectId}
        onChange={(value) => {
          setProjectId(value);
          setPage(1);
        }}
        options={projects.map((project) => ({ value: project.id, label: project.name }))}
        style={{ width: 220 }}
      />
      {ENTITY_TYPES.map((entity) => (
        <Tag.CheckableTag
          key={entity.value || 'all'}
          checked={entityType === entity.value}
          onChange={() => handleEntityFilter(entity.value)}
          style={{ padding: '4px 14px', fontSize: 14 }}
        >
          {entity.label}
        </Tag.CheckableTag>
      ))}
    </Space>
  );

  if (!hasSearched) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '55vh',
          gap: 24,
        }}
      >
        <SearchOutlined style={{ fontSize: 64, color: '#bfbfbf' }} />
        <Title level={3} style={{ color: '#666', margin: 0 }}>
          搜索研发数据
        </Title>
        <Text type="secondary">统一检索项目、材料、实验、样品、表征记录和附件</Text>
        <Input.Search
          ref={inputRef}
          placeholder="输入名称、编号、仪器、文件名或描述..."
          size="large"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onSearch={handleSearch}
          style={{ width: 620 }}
          enterButton="搜索"
        />
        {filters}
      </div>
    );
  }

  return (
    <div>
      <Title level={4}>全局搜索</Title>
      <Input.Search
        ref={inputRef}
        placeholder="输入名称、编号、仪器、文件名或描述..."
        size="large"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        onSearch={handleSearch}
        style={{ maxWidth: 620, marginBottom: 16 }}
        enterButton="搜索"
      />
      <div style={{ marginBottom: 16 }}>{filters}</div>
      {data && (
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          共找到 {data.total} 条可访问结果
        </Text>
      )}
      <Table
        columns={columns}
        dataSource={data?.items || []}
        rowKey={(record) => `${record.entity_type}:${record.id}`}
        loading={isLoading}
        pagination={
          data && data.total > 0
            ? {
                current: page,
                pageSize,
                total: data.total,
                onChange: (nextPage, nextSize) => {
                  setPage(nextPage);
                  setPageSize(nextSize);
                },
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条`,
              }
            : false
        }
        locale={{ emptyText: <Empty description="未找到可访问的匹配数据" /> }}
      />
    </div>
  );
}
