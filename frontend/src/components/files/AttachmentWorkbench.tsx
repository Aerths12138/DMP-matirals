import { useState } from 'react';
import {
  Button,
  Card,
  Empty,
  Input,
  message,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd';
import type { UploadProps } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
  InboxOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  deleteAttachment,
  downloadAttachment,
  fetchAttachments,
  uploadAttachment,
} from '../../api/files';
import type { FileAttachment, FileParentType } from '../../types/file';

const { Dragger } = Upload;
const { Paragraph, Text } = Typography;

const FILE_TYPE_OPTIONS = [
  { value: 'other', label: '其他文件' },
  { value: 'sem_image', label: 'SEM 图像' },
  { value: 'tem_image', label: 'TEM 图像' },
  { value: 'xrd_raw', label: 'XRD 原始数据' },
  { value: 'spectrum', label: '光谱数据' },
  { value: 'spreadsheet', label: '表格数据' },
  { value: 'cif_file', label: '晶体结构文件' },
  { value: 'document', label: '文档' },
];

interface AttachmentWorkbenchProps {
  parentType: FileParentType;
  parentId: string;
  canEdit: boolean;
  title?: string;
}

interface PreviewState {
  attachment: FileAttachment;
  kind: 'image' | 'pdf' | 'text' | 'unsupported';
  objectUrl?: string;
  text?: string;
}

function getErrorMessage(error: unknown, fallback: string) {
  const responseError = error as { response?: { data?: { detail?: string } } };
  return responseError.response?.data?.detail || fallback;
}

function formatFileSize(size?: number) {
  if (size === undefined || size === null) return '-';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function getPreviewKind(attachment: FileAttachment): PreviewState['kind'] {
  const mime = attachment.mime_type || '';
  const extension = attachment.original_name.toLowerCase().split('.').pop() || '';
  if (mime.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(extension)) {
    return 'image';
  }
  if (mime === 'application/pdf' || extension === 'pdf') return 'pdf';
  if (
    mime.startsWith('text/') ||
    ['txt', 'csv', 'json', 'xml', 'log', 'md'].includes(extension)
  ) {
    return 'text';
  }
  return 'unsupported';
}

export default function AttachmentWorkbench({
  parentType,
  parentId,
  canEdit,
  title = '原始数据与附件',
}: AttachmentWorkbenchProps) {
  const queryClient = useQueryClient();
  const [fileType, setFileType] = useState('other');
  const [description, setDescription] = useState('');
  const [uploadProgress, setUploadProgress] = useState<number>();
  const [preview, setPreview] = useState<PreviewState>();
  const [previewLoading, setPreviewLoading] = useState(false);

  const queryKey = ['attachments', parentType, parentId];
  const attachmentsQuery = useQuery({
    queryKey,
    queryFn: () =>
      fetchAttachments({ parent_type: parentType, parent_id: parentId, size: 100 }),
    enabled: Boolean(parentId),
  });
  const attachments = attachmentsQuery.data?.items || [];

  const refresh = () => queryClient.invalidateQueries({ queryKey });
  const deleteMutation = useMutation({
    mutationFn: deleteAttachment,
    onSuccess: () => {
      refresh();
      message.success('附件已删除');
    },
    onError: (error: unknown) => {
      message.error(getErrorMessage(error, '删除附件失败'));
    },
  });

  const uploadRequest: UploadProps['customRequest'] = async ({
    file,
    onError,
    onProgress,
    onSuccess,
  }) => {
    setUploadProgress(0);
    try {
      const result = await uploadAttachment(
        file as File,
        {
          parent_type: parentType,
          parent_id: parentId,
          file_type: fileType,
          description,
        },
        (percent) => {
          setUploadProgress(percent);
          onProgress?.({ percent });
        }
      );
      onSuccess?.(result);
      setUploadProgress(undefined);
      setDescription('');
      refresh();
      message.success('附件上传成功');
    } catch (error) {
      setUploadProgress(undefined);
      onError?.(error as Error);
      message.error(getErrorMessage(error, '附件上传失败'));
    }
  };

  const handleDownload = async (attachment: FileAttachment) => {
    try {
      const blob = await downloadAttachment(attachment.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = attachment.original_name;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      message.error(getErrorMessage(error, '下载附件失败'));
    }
  };

  const handlePreview = async (attachment: FileAttachment) => {
    const kind = getPreviewKind(attachment);
    if (kind === 'unsupported') {
      setPreview({ attachment, kind });
      return;
    }
    setPreviewLoading(true);
    try {
      const blob = await downloadAttachment(attachment.id);
      if (kind === 'text') {
        setPreview({ attachment, kind, text: await blob.text() });
      } else {
        setPreview({ attachment, kind, objectUrl: URL.createObjectURL(blob) });
      }
    } catch (error) {
      message.error(getErrorMessage(error, '加载预览失败'));
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    if (preview?.objectUrl) URL.revokeObjectURL(preview.objectUrl);
    setPreview(undefined);
  };

  const columns: ColumnsType<FileAttachment> = [
    {
      title: '文件',
      dataIndex: 'original_name',
      key: 'original_name',
      render: (name: string, row) => (
        <div>
          <Space>
            <PaperClipOutlined />
            <Text>{name}</Text>
          </Space>
          {row.description && (
            <Paragraph type="secondary" ellipsis={{ rows: 1 }} style={{ margin: 0 }}>
              {row.description}
            </Paragraph>
          )}
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 130,
      render: (value?: string) => (
        <Tag>{FILE_TYPE_OPTIONS.find((option) => option.value === value)?.label || value || '其他文件'}</Tag>
      ),
    },
    {
      title: '大小',
      dataIndex: 'file_size_bytes',
      key: 'file_size_bytes',
      width: 100,
      render: formatFileSize,
    },
    {
      title: 'SHA-256',
      dataIndex: 'checksum_sha256',
      key: 'checksum_sha256',
      width: 120,
      render: (value?: string) =>
        value ? (
          <Tooltip title={value}>
            <Text code>{value.slice(0, 10)}…</Text>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (value: string) => new Date(value).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: canEdit ? 220 : 150,
      fixed: 'right',
      render: (_, row) => (
        <Space size="small">
          <Button type="link" icon={<EyeOutlined />} onClick={() => handlePreview(row)}>
            预览
          </Button>
          <Button type="link" icon={<DownloadOutlined />} onClick={() => handleDownload(row)}>
            下载
          </Button>
          {canEdit && (
            <Popconfirm title="确定删除该附件吗？" onConfirm={() => deleteMutation.mutate(row.id)}>
              <Button type="link" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card title={title}>
        {canEdit && (
          <div style={{ marginBottom: 16 }}>
            <Space wrap style={{ marginBottom: 10 }}>
              <Select value={fileType} options={FILE_TYPE_OPTIONS} onChange={setFileType} style={{ width: 180 }} />
              <Input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="附件说明（可选）"
                maxLength={500}
                style={{ width: 360 }}
              />
            </Space>
            <Dragger
              multiple={false}
              showUploadList={false}
              customRequest={uploadRequest}
              disabled={uploadProgress !== undefined}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p>点击或拖拽一个原始数据文件到此处</p>
              <Text type="secondary">系统会计算 SHA-256，并阻止重复附件。</Text>
            </Dragger>
            {uploadProgress !== undefined && <Progress percent={uploadProgress} style={{ marginTop: 8 }} />}
          </div>
        )}
        <Table
          columns={columns}
          dataSource={attachments}
          rowKey="id"
          loading={attachmentsQuery.isLoading}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          scroll={{ x: 850 }}
          locale={{ emptyText: <Empty description="暂无附件" /> }}
        />
      </Card>

      <Modal
        title={preview?.attachment.original_name || '附件预览'}
        open={Boolean(preview) || previewLoading}
        onCancel={closePreview}
        footer={
          preview ? (
            <Button type="primary" icon={<DownloadOutlined />} onClick={() => handleDownload(preview.attachment)}>
              下载原文件
            </Button>
          ) : null
        }
        width={920}
      >
        {previewLoading && <Spin style={{ display: 'block', margin: 80 }} />}
        {preview?.kind === 'image' && preview.objectUrl && (
          <img src={preview.objectUrl} alt={preview.attachment.original_name} style={{ display: 'block', maxWidth: '100%', maxHeight: '70vh', margin: '0 auto' }} />
        )}
        {preview?.kind === 'pdf' && preview.objectUrl && (
          <iframe title={preview.attachment.original_name} src={preview.objectUrl} style={{ width: '100%', height: '70vh', border: 0 }} />
        )}
        {preview?.kind === 'text' && (
          <pre style={{ maxHeight: '70vh', overflow: 'auto', padding: 16, background: '#f5f5f5', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {preview.text}
          </pre>
        )}
        {preview?.kind === 'unsupported' && (
          <Empty description="该文件类型暂不支持在线预览，请下载后查看" style={{ margin: 80 }} />
        )}
      </Modal>
    </>
  );
}
