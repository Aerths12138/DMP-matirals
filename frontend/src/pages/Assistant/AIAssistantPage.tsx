import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Avatar,
  Button,
  Card,
  Empty,
  Input,
  Popconfirm,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message as antdMessage,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  PaperClipOutlined,
  RobotOutlined,
  SendOutlined,
  UndoOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  chatWithAssistant,
  chatWithAssistantExcel,
  clearAssistantHistory,
  confirmAssistantAction,
  getAssistantHistory,
  listAssistantBackups,
  restoreAssistantBackup,
  type AssistantBackup,
  type AssistantAnalysisCard,
  type AssistantImportPreview,
  type AssistantKnowledgeCard,
  type PendingAssistantAction,
} from '../../api/assistant';
import { importMaterials } from '../../api/materials';
import {
  canConfirmAssistantAction,
  updateAssistantActionStatus,
  type AssistantActionStatus,
} from '../../components/assistant/actionState';
import {
  assistantErrorMessage,
  restoreAssistantConversation,
  type DisplayAssistantMessage,
} from '../../components/assistant/conversationState';
import {
  buildAssistantUserContent,
  canSendAssistantRequest,
  createAssistantFileState,
  failAssistantFileSend,
  readAssistantExcelSheetNames,
  removeAssistantExcelFile,
  selectAssistantExcelFile,
  startAssistantFileSend,
  succeedAssistantFileSend,
} from './assistantFileState';
import {
  canConfirmAssistantImport,
  clearAssistantImport,
  confirmAssistantImport,
  createAssistantImportState,
  failAssistantImport,
  receiveAssistantImportPreview,
  startAssistantImport,
} from './assistantImportState';

interface DisplayAction extends PendingAssistantAction {
  status: AssistantActionStatus;
}

const WELCOME_MESSAGE = '你好，我可以回答材料领域问题，也可以查询平台数据。需要新增、修改或删除数据时，我会先生成操作预览，由你确认后才执行。';

const IMPORT_MAPPING_LABELS: Record<string, string> = {
  name: '材料名称',
  material_type: '材料类型',
  formula_string: '化学式',
  hill_formula: 'Hill 化学式',
  aliases: '别名',
  description: '描述',
  test_name: '测试名称',
  test_method: '测试方法',
  property: '性能属性',
  condition: '测试条件',
  result: '测试结果',
  ignore: '忽略',
};

function createId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function MeasurementAnalysisCard({ analysis }: { analysis: AssistantAnalysisCard }) {
  const chartPoints = analysis.chart.points.filter((point) => point.mean !== null);
  const chartUnits = new Set(chartPoints.map((point) => point.unit));
  const canChart = chartPoints.length > 0 && chartUnits.size === 1;

  return (
    <Card
      size="small"
      title={analysis.title}
      style={{ marginBottom: 16, borderColor: '#1677ff' }}
      extra={<Tag color="blue">可复现分析</Tag>}
    >
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <Space wrap>
          <Tag color="green">有效数值 {analysis.quality.numeric_records}</Tag>
          <Tag>返回记录 {analysis.quality.records_returned}</Tag>
          <Tag color={analysis.quality.outlier_count ? 'gold' : 'default'}>
            IQR 异常值 {analysis.quality.outlier_count}
          </Tag>
          <Tag color={analysis.quality.truncated ? 'orange' : 'default'}>
            {analysis.quality.truncated ? '结果已截断' : '范围完整'}
          </Tag>
        </Space>

        {canChart ? (
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartPoints} margin={{ top: 12, right: 8, bottom: 36, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" angle={-20} textAnchor="end" interval={0} height={62} />
                <YAxis />
                <RechartsTooltip
                  formatter={(value: number, _name: string, item) => [
                    `${value} ${item.payload.unit}`,
                    `均值（n=${item.payload.count}）`,
                  ]}
                />
                <Bar dataKey="mean" name="均值" fill="#1677ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : chartPoints.length > 0 ? (
          <Alert
            type="warning"
            showIcon
            message="检测到多种不兼容单位，未绘制混合单位柱状图"
            description="统计已按单位拆分；请筛选单一单位或在确认换算规则后再比较。"
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有可绘图的数值记录" />
        )}

        {analysis.groups.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 6 }}>分组</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>n</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>均值</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>中位数</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>范围</th>
                </tr>
              </thead>
              <tbody>
                {analysis.groups.map((group) => (
                  <tr key={`${group.label}-${group.unit}`}>
                    <td style={{ padding: 6 }}>{group.label}</td>
                    <td style={{ textAlign: 'right', padding: 6 }}>{group.count}</td>
                    <td style={{ textAlign: 'right', padding: 6 }}>
                      {group.mean ?? '—'} {group.mean !== null ? group.unit : ''}
                    </td>
                    <td style={{ textAlign: 'right', padding: 6 }}>
                      {group.median ?? '—'} {group.median !== null ? group.unit : ''}
                    </td>
                    <td style={{ textAlign: 'right', padding: 6 }}>
                      {group.min ?? '—'} – {group.max ?? '—'} {group.min !== null ? group.unit : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {analysis.limitations.length > 0 && (
          <Alert
            type="info"
            showIcon
            message="解释边界与数据质量提示"
            description={analysis.limitations.join('；')}
          />
        )}

        <details>
          <summary style={{ cursor: 'pointer', color: '#1677ff' }}>查看查询计划与数据溯源</summary>
          <pre
            style={{
              margin: '8px 0 0', padding: 8, maxHeight: 220, overflow: 'auto',
              background: '#fafafa', fontSize: 12, whiteSpace: 'pre-wrap',
            }}
          >
            {JSON.stringify({ query_plan: analysis.query_plan, provenance: analysis.provenance }, null, 2)}
          </pre>
        </details>
      </Space>
    </Card>
  );
}

function ResearchKnowledgeCard({ knowledge }: { knowledge: AssistantKnowledgeCard }) {
  const engineLabel = knowledge.retrieval.semantic_embeddings ? '语义检索' : '全文检索';

  return (
    <Card
      size="small"
      title={`科研资料检索：${knowledge.query}`}
      style={{ marginBottom: 16, borderColor: '#13c2c2' }}
      extra={<Tag color="cyan">{engineLabel} · 可溯源</Tag>}
    >
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <Typography.Text type="secondary">
          在当前有权访问的附件中返回 {knowledge.retrieval.returned} 段证据；权限在每次检索时重新校验。
        </Typography.Text>
        {knowledge.items.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有检索到可引用的附件内容" />
        ) : knowledge.items.map(({ score, excerpt, citation }) => {
          const location = citation.page_start
            ? `第 ${citation.page_start}${citation.page_end && citation.page_end !== citation.page_start ? `–${citation.page_end}` : ''} 页`
            : typeof citation.source_metadata.sheet_name === 'string'
              ? `工作表：${citation.source_metadata.sheet_name}`
              : `片段 #${citation.chunk_index + 1}`;
          return (
            <Card key={`${citation.file_id}-${citation.chunk_index}`} type="inner" size="small">
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space wrap>
                  <a href={citation.download_url} target="_blank" rel="noreferrer">{citation.file_name}</a>
                  <Tag>{location}</Tag>
                  <Tag color="default">相关度 {score.toFixed(2)}</Tag>
                </Space>
                <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                  {excerpt}
                </Typography.Paragraph>
              </Space>
            </Card>
          );
        })}
        {knowledge.limitations.length > 0 && (
          <Alert type="info" showIcon message="检索边界" description={knowledge.limitations.join('；')} />
        )}
      </Space>
    </Card>
  );
}

export default function AIAssistantPage() {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<DisplayAssistantMessage[]>(() => (
    restoreAssistantConversation([], WELCOME_MESSAGE, createId)
  ));
  const [actions, setActions] = useState<DisplayAction[]>([]);
  const [analysisCards, setAnalysisCards] = useState<AssistantAnalysisCard[]>([]);
  const [knowledgeCards, setKnowledgeCards] = useState<AssistantKnowledgeCard[]>([]);
  const [backups, setBackups] = useState<AssistantBackup[]>([]);
  const [loadingBackups, setLoadingBackups] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [restoringBackupId, setRestoringBackupId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [fileState, setFileState] = useState(() => createAssistantFileState<File>());
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [selectedSheetName, setSelectedSheetName] = useState<string>();
  const [loadingSheetNames, setLoadingSheetNames] = useState(false);
  const [sheetNameError, setSheetNameError] = useState<string | null>(null);
  const sheetReadSequence = useRef(0);
  const [importState, setImportState] = useState(() => (
    createAssistantImportState<AssistantImportPreview>()
  ));
  const importing = importState.phase === 'importing';

  const conversation = useMemo(
    () => messages.map(({ role, content }) => ({ role, content })),
    [messages],
  );

  const clearSheetSelection = () => {
    sheetReadSequence.current += 1;
    setSheetNames([]);
    setSelectedSheetName(undefined);
    setLoadingSheetNames(false);
    setSheetNameError(null);
  };

  const loadSheetNames = async (file: File) => {
    const sequence = ++sheetReadSequence.current;
    setSheetNames([]);
    setSelectedSheetName(undefined);
    setLoadingSheetNames(true);
    setSheetNameError(null);
    try {
      const names = await readAssistantExcelSheetNames(file);
      if (sequence !== sheetReadSequence.current) return;
      setSheetNames(names);
      setSelectedSheetName(names[0]);
    } catch {
      if (sequence !== sheetReadSequence.current) return;
      setSheetNameError('无法读取工作表列表，请重新选择有效的 .xlsx 文件。');
    } finally {
      if (sequence === sheetReadSequence.current) setLoadingSheetNames(false);
    }
  };

  useEffect(() => {
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
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadingHistory(true);
    getAssistantHistory()
      .then((history) => {
        if (cancelled) return;
        setMessages(restoreAssistantConversation(
          history.messages,
          WELCOME_MESSAGE,
          createId,
        ));
        setActions([]);
      })
      .catch(() => {
        if (!cancelled) antdMessage.warning('无法加载上次对话，已保留当前内容。');
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => { cancelled = true; };
  }, []);

  const sendMessage = async (inputOverride?: string) => {
    const requestInput = inputOverride ?? input;
    if (sending || importing || !canSendAssistantRequest(requestInput, fileState)) return;
    const attachedFile = fileState.file;
    const attachedSheetName = selectedSheetName;
    if (attachedFile && (!attachedSheetName || loadingSheetNames || sheetNameError)) return;
    const content = buildAssistantUserContent(requestInput, attachedFile);

    const userMessage: DisplayAssistantMessage = { id: createId(), role: 'user', content };
    const nextConversation = [
      ...conversation,
      { role: 'user' as const, content },
    ].slice(-30);
    setMessages((current) => [...current, userMessage]);
    if (inputOverride === undefined) setInput('');
    setSending(true);
    setImportState(clearAssistantImport<AssistantImportPreview>());
    if (attachedFile) {
      setFileState((current) => startAssistantFileSend(current));
    }

    try {
      const response = attachedFile
        ? await chatWithAssistantExcel(
          nextConversation,
          attachedFile,
          '/assistant',
          attachedSheetName,
        )
        : await chatWithAssistant(nextConversation, '/assistant');
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: response.message },
      ]);
      if (response.analysis_cards.length) {
        setAnalysisCards((current) => [...current, ...response.analysis_cards].slice(-5));
      }
      if (response.knowledge_cards.length) {
        setKnowledgeCards((current) => [...current, ...response.knowledge_cards].slice(-5));
      }
      if (response.pending_actions.length) {
        setActions((current) => [
          ...current,
          ...response.pending_actions.map((action) => ({
            ...action,
            status: 'pending' as const,
          })),
        ]);
      }
      setImportState(receiveAssistantImportPreview(response.pending_import));
      if (attachedFile) {
        setFileState((current) => succeedAssistantFileSend(current));
      }
    } catch (error) {
      const errorMessage = assistantErrorMessage(error);
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: errorMessage },
      ]);
      if (attachedFile) {
        setFileState((current) => failAssistantFileSend(current, errorMessage));
      }
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
      antdMessage.error(assistantErrorMessage(error));
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
      antdMessage.error(assistantErrorMessage(error));
    } finally {
      setRestoringBackupId(null);
    }
  };

  const clearConversation = async () => {
    setClearingHistory(true);
    try {
      await clearAssistantHistory();
      setMessages(restoreAssistantConversation([], WELCOME_MESSAGE, createId));
      setActions([]);
      setAnalysisCards([]);
      setKnowledgeCards([]);
      setInput('');
      setFileState(removeAssistantExcelFile<File>());
      clearSheetSelection();
      setImportState(clearAssistantImport<AssistantImportPreview>());
    } catch (error) {
      antdMessage.error(assistantErrorMessage(error));
    } finally {
      setClearingHistory(false);
    }
  };

  const confirmPreparedImport = async () => {
    if (!canConfirmAssistantImport(importState)) return;
    const readyState = importState;
    setImportState(startAssistantImport(readyState));
    try {
      const result = await confirmAssistantImport(
        readyState,
        (rows) => importMaterials({ rows }),
      );
      if (!result) return;
      const summary = `Excel 导入完成：共 ${result.total} 条，成功 ${result.created} 条，失败 ${result.failed} 条。`;
      const errorSummary = result.errors.length
        ? `\n${result.errors.slice(0, 3).map((item) => `第 ${item.row} 条：${item.message}`).join('\n')}`
        : '';
      setImportState(clearAssistantImport<AssistantImportPreview>());
      setMessages((current) => [
        ...current,
        { id: createId(), role: 'assistant', content: `${summary}${errorSummary}` },
      ]);
      await queryClient.invalidateQueries();
      if (result.failed) {
        antdMessage.warning(summary);
      } else {
        antdMessage.success(summary);
      }
    } catch (error) {
      const errorMessage = assistantErrorMessage(error);
      setImportState((current) => failAssistantImport(current, errorMessage));
      antdMessage.error(errorMessage);
    }
  };

  const operationLabel = {
    create: '新增',
    update: '修改',
    delete: '删除',
  } as const;

  return (
    <div
      style={{
        height: 'calc(100vh - 160px)',
        minHeight: 620,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px 12px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Space>
          <RobotOutlined style={{ color: '#1677ff', fontSize: 22 }} />
          <Typography.Title level={3} style={{ margin: 0 }}>AI 数据助手</Typography.Title>
          <Tag color="blue">独立工作台</Tag>
        </Space>
        <Tooltip title="清空已保存对话和未执行操作">
          <Button
            type="text"
            icon={<DeleteOutlined />}
            onClick={clearConversation}
            loading={clearingHistory}
          />
        </Tooltip>
      </div>
      <div style={{ padding: '10px 16px 0' }}>
        <Alert
          type="info"
          showIcon
          message="Excel 可由 AI 读取并生成格式化导入预览；只有你确认后才会写入平台，原文件不会被覆盖。"
        />
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 16 }}>
        {loadingHistory ? (
          <Typography.Text type="secondary">正在加载上次对话…</Typography.Text>
        ) : messages.length === 0 ? (
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
            {fileState.file ? 'AI 正在读取 Excel 并分析…' : 'AI 正在思考并检查数据权限…'}
          </div>
        )}

        {importState.preview && (
          <Card
            size="small"
            title="Excel 格式化导入预览"
            style={{ marginBottom: 16, borderColor: '#1677ff' }}
          >
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Alert
                type="info"
                showIcon
                message="当前仅为订正后的数据副本，尚未写入数据库。请核对后再确认导入。"
              />
              <Space wrap>
                <Tag color="blue">文件：{importState.preview.filename}</Tag>
                <Tag>工作表：{importState.preview.sheet_name}</Tag>
                <Tag>源数据 {importState.preview.source_row_count} 行</Tag>
                <Tag color="green">待导入材料 {importState.preview.material_count} 条</Tag>
                <Tag color={importState.preview.conversion_count ? 'gold' : 'default'}>
                  自动订正 {importState.preview.conversion_count} 处
                </Tag>
              </Space>

              {importState.preview.blocking_errors.map((error) => (
                <Alert key={error} type="error" showIcon message={error} />
              ))}
              {importState.preview.warnings.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="格式化提示"
                  description={importState.preview.warnings.slice(0, 5).join('；')}
                />
              )}
              {importState.error && (
                <Alert
                  type="error"
                  showIcon
                  message="导入失败，预览和 Excel 已保留"
                  description={importState.error}
                />
              )}

              <div>
                <Typography.Text strong>字段映射</Typography.Text>
                <div style={{ marginTop: 6 }}>
                  <Space wrap size={[4, 6]}>
                    {Object.entries(importState.preview.mapping).slice(0, 16).map(([source, target]) => (
                      <Tag key={source} color={target === 'ignore' ? 'default' : 'processing'}>
                        {source} → {IMPORT_MAPPING_LABELS[target] || target}
                      </Tag>
                    ))}
                  </Space>
                </div>
              </div>

              <details>
                <summary style={{ cursor: 'pointer', color: '#1677ff' }}>
                  查看订正数据样例与转换明细
                </summary>
                <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                  订正数据样例（最多 5 行）
                </Typography.Text>
                <pre
                  style={{
                    margin: '6px 0',
                    padding: 8,
                    maxHeight: 200,
                    overflow: 'auto',
                    background: '#fafafa',
                    fontSize: 12,
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {JSON.stringify(importState.preview.normalized_rows.slice(0, 5), null, 2)}
                </pre>
                {importState.preview.conversions.length > 0 && (
                  <pre
                    style={{
                      margin: 0,
                      padding: 8,
                      maxHeight: 160,
                      overflow: 'auto',
                      background: '#fffbe6',
                      fontSize: 12,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {JSON.stringify(importState.preview.conversions.slice(0, 20), null, 2)}
                  </pre>
                )}
              </details>

              <Space>
                <Popconfirm
                  title="确认把格式化后的数据导入平台？"
                  description="确认后才会写入数据库，后端会再次检查你的导入权限。"
                  okText="确认导入"
                  cancelText="返回核对"
                  onConfirm={confirmPreparedImport}
                >
                  <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    loading={importing}
                    disabled={!canConfirmAssistantImport(importState)}
                  >
                    确认导入 {importState.preview.material_count} 条材料
                  </Button>
                </Popconfirm>
                <Button
                  disabled={importing}
                  onClick={() => setImportState(clearAssistantImport<AssistantImportPreview>())}
                >
                  放弃本次预览
                </Button>
              </Space>
            </Space>
          </Card>
        )}

        {analysisCards.map((analysis) => (
          <MeasurementAnalysisCard key={analysis.analysis_id} analysis={analysis} />
        ))}

        {knowledgeCards.map((knowledge, index) => (
          <ResearchKnowledgeCard key={`${knowledge.query}-${index}`} knowledge={knowledge} />
        ))}

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
        <Space wrap style={{ marginBottom: 8 }}>
          <Upload
            accept=".xlsx"
            maxCount={1}
            showUploadList={false}
            disabled={sending || importing}
            beforeUpload={(file) => {
              const next = selectAssistantExcelFile(fileState, file);
              setFileState(next);
              if (next.error) {
                antdMessage.error(next.error);
              } else {
                setImportState(clearAssistantImport<AssistantImportPreview>());
                void loadSheetNames(file);
              }
              return Upload.LIST_IGNORE;
            }}
          >
            <Button icon={<PaperClipOutlined />} disabled={sending || importing}>
              选择 Excel
            </Button>
          </Upload>
          {fileState.file && (
            <Tag
              color="blue"
              icon={<PaperClipOutlined />}
              closable={!sending && !importing}
              onClose={() => {
                setFileState(removeAssistantExcelFile<File>());
                clearSheetSelection();
                setImportState(clearAssistantImport<AssistantImportPreview>());
              }}
            >
              当前文件：{fileState.file.name}
            </Tag>
          )}
          {fileState.file && (
            <Select
              aria-label="选择要导入的工作表"
              value={selectedSheetName}
              placeholder={loadingSheetNames ? '正在读取工作表…' : '选择工作表'}
              loading={loadingSheetNames}
              disabled={sending || importing || loadingSheetNames || Boolean(sheetNameError)}
              options={sheetNames.map((name) => ({ label: name, value: name }))}
              onChange={(name) => {
                setSelectedSheetName(name);
                setImportState(clearAssistantImport<AssistantImportPreview>());
              }}
              style={{ minWidth: 180 }}
            />
          )}
          {fileState.file && (
            <Button
              type="primary"
              ghost
              disabled={sending || importing || loadingSheetNames || !selectedSheetName || Boolean(sheetNameError)}
              onClick={() => sendMessage('请读取当前 Excel，按照平台字段和数据格式进行订正，并准备可确认的导入预览。')}
            >
              格式化并准备导入
            </Button>
          )}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            支持 .xlsx，最大 5 MiB；AI 可生成订正副本和待确认的导入预览。
          </Typography.Text>
          {sheetNameError && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {sheetNameError}
            </Typography.Text>
          )}
        </Space>
        <Input.TextArea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onPressEnter={(event) => {
            if (!event.shiftKey) {
              event.preventDefault();
              sendMessage();
            }
          }}
          placeholder="询问材料知识、查询平台数据，或选择 Excel 后让我格式化并准备导入…"
          autoSize={{ minRows: 2, maxRows: 5 }}
          maxLength={20000}
          disabled={sending || importing}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={() => sendMessage()}
          loading={sending}
          disabled={
            importing
            || !canSendAssistantRequest(input, fileState)
            || Boolean(fileState.file && (
              loadingSheetNames || !selectedSheetName || sheetNameError
            ))
          }
          block
          style={{ marginTop: 8 }}
        >
          发送
        </Button>
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
          原始 Excel 始终只读；AI 可准备订正副本和导入预览，只有点击“确认导入”才会写入平台。
        </Typography.Text>
      </div>
    </div>
  );
}
