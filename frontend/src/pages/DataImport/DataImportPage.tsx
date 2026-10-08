import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, Button, Table, Tag, Typography, Space, Alert, Statistic,
  Card, Row, Col, Select, Descriptions, Input, Tooltip, Checkbox,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined,
  FileTextOutlined, EyeOutlined, CloudUploadOutlined,
  QuestionCircleOutlined, RobotOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { parseFile, autoMapColumns } from '../../utils/fileParser';
import type { StructuredDatasetPreview } from '../../utils/structuredImport';
import { cleanImportCell, parseImportNumber, type ImportCell } from '../../utils/importNormalization';
import { downloadCorrectedImport, downloadImportQualityReport } from '../../utils/importCorrectedExport';
import { analyzeImportQuality, summarizeImportQuality } from '../../utils/importQuality';
import {
  applyImportAlignmentFailure,
  applyImportAlignmentSuccess,
  confirmImport,
  type ImportAlignmentViewState,
} from '../../utils/importAlignmentFlow';
import { alignImportData } from '../../api/importAlignment';
import type { ImportAlignmentResponse } from '../../api/importAlignment';
import { importMaterials } from '../../api/materials';
import type { ImportResult } from '../../api/materials';
import { fetchProjects } from '../../api/projects';
import { fetchSamples } from '../../api/samples';
import { createMeasurementDataset, updateMeasurementDataset, type MeasurementDataset } from '../../api/measurementDatasets';
import { uploadAttachment } from '../../api/files';

const { Title, Text } = Typography;
const { Dragger } = Upload;

const FIXED_FIELDS = ['name', 'material_type', 'formula_string', 'hill_formula', 'aliases', 'description'];

export default function DataImportPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<ImportCell[][]>([]);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [testGroupMapping, setTestGroupMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [alignmentResult, setAlignmentResult] = useState<ImportAlignmentResponse | null>(null);
  const [alignmentError, setAlignmentError] = useState<string | null>(null);
  const [structuredDataset, setStructuredDataset] = useState<StructuredDatasetPreview | null>(null);
  const [datasetTitle, setDatasetTitle] = useState('');
  const [xColumnIndex, setXColumnIndex] = useState(0);
  const [seriesColumnIndexes, setSeriesColumnIndexes] = useState<number[]>([]);
  const [projectId, setProjectId] = useState<string>();
  const [sampleId, setSampleId] = useState<string>();
  const [datasetResult, setDatasetResult] = useState<MeasurementDataset | null>(null);

  const projectsQuery = useQuery({
    queryKey: ['projects', 'measurement-dataset-import'],
    queryFn: () => fetchProjects({ page: 1, size: 100 }),
    enabled: structuredDataset !== null && step === 1,
  });
  const samplesQuery = useQuery({
    queryKey: ['samples', projectId, 'measurement-dataset-import'],
    queryFn: () => fetchSamples({ project_id: projectId!, page: 1, size: 100 }),
    enabled: structuredDataset !== null && step === 1 && Boolean(projectId),
  });

  const applyAlignmentState = (next: ImportAlignmentViewState) => {
    setRows(next.rows);
    setColumnMapping(next.columnMapping);
    setAlignmentResult(next.alignmentResult);
    setAlignmentError(next.alignmentError);
  };

  const currentAlignmentState = (): ImportAlignmentViewState => ({
    rows,
    columnMapping,
    alignmentResult,
    alignmentError,
  });
  const qualityIssues = useMemo(
    () => analyzeImportQuality(headers, rows, columnMapping),
    [headers, rows, columnMapping],
  );
  const qualitySummary = useMemo(
    () => summarizeImportQuality(qualityIssues),
    [qualityIssues],
  );

  // Step 0: Handle file upload
  const handleFile = async (f: File) => {
    setFile(f);
    setParseError(null);
    setAlignmentResult(null);
    setAlignmentError(null);
    try {
      const csvData = await parseFile(f);
      if (csvData.structuredDataset) {
        setStructuredDataset(csvData.structuredDataset);
        setDatasetTitle(csvData.structuredDataset.title);
        setXColumnIndex(Math.max(0, csvData.structuredDataset.xColumnIndex));
        setSeriesColumnIndexes(csvData.structuredDataset.suggestedSeriesColumnIndexes);
        setProjectId(undefined);
        setSampleId(undefined);
        setDatasetResult(null);
        setStep(1);
        return false;
      }
      setStructuredDataset(null);
      if (csvData.headers.length === 0) {
        setParseError('文件中未检测到表头，请检查文件格式');
        return false;
      }
      if (csvData.rows.length === 0) {
        setParseError('文件中未检测到数据行，请检查文件内容');
        return false;
      }
      setHeaders(csvData.headers);
      setRows(csvData.rows);
      // Auto-detect column mapping
      const mapping = autoMapColumns(csvData.headers);
      setColumnMapping(mapping);

      // Initialize empty test group mappings (user fills manually)
      setTestGroupMapping({});

      setStep(1);
    } catch (err: any) {
      setParseError(err?.message || '文件解析失败，请确认文件未损坏且格式正确');
    }
    return false; // prevent upload
  };

  // Step 1 → 2: Build rows and submit
  const importMutation = useMutation({
    mutationFn: importMaterials,
    onSuccess: (res) => {
      setResult(res);
      setStep(2);
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
  });

  const alignmentMutation = useMutation({
    mutationFn: alignImportData,
    onSuccess: (data) => {
      applyAlignmentState(applyImportAlignmentSuccess(currentAlignmentState(), data));
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error?.message || '格式对齐失败';
      applyAlignmentState(applyImportAlignmentFailure(currentAlignmentState(), message));
    },
  });

  const datasetMutation = useMutation({
    mutationFn: async (body: Parameters<typeof createMeasurementDataset>[0]) => {
      const created = await createMeasurementDataset(body);
      if (!file) return created;
      const uploaded = await uploadAttachment(file, {
        parent_type: 'characterization',
        parent_id: created.characterization_id,
        file_type: 'spreadsheet',
        description: '测量数据集原始文件',
      });
      return updateMeasurementDataset(created.id, { source_file_id: uploaded.id });
    },
    onSuccess: (data) => {
      setDatasetResult(data);
      setStep(2);
      queryClient.invalidateQueries({ queryKey: ['measurement-datasets', data.characterization_id] });
    },
  });

  const submitDatasetImport = () => {
    if (!structuredDataset || !sampleId) return;
    const xColumn = structuredDataset.columns[xColumnIndex];
    const numericColumns = structuredDataset.columns.filter((column, columnIndex) => (
      seriesColumnIndexes.includes(columnIndex)
      && columnIndex !== xColumnIndex
      && structuredDataset.rows.every((row) => parseImportNumber(row[columnIndex]) !== null)
    ));
    const points = structuredDataset.rows.flatMap((row, rowIndex) => {
      const xValue = parseImportNumber(row[xColumnIndex]);
      if (xValue === null) return [];
      const values: Record<string, number> = {};
      numericColumns.forEach((column) => {
        const columnIndex = structuredDataset.columns.indexOf(column);
        const value = parseImportNumber(row[columnIndex]);
        if (value !== null) values[column.key] = value;
      });
      return [{ sequence: rowIndex + 1, x_value: xValue, values }];
    });
    datasetMutation.mutate({
      sample_id: sampleId,
      name: datasetTitle.trim(),
      x_name: xColumn.name,
      x_unit: xColumn.unit,
      series_schema: numericColumns.map(({ key, name, unit }) => ({ key, name, unit })),
      points,
      provenance: {
        source_filename: file?.name,
        parser: 'structure-driven-v1',
        header_row: structuredDataset.headerRow,
        unit_row: structuredDataset.unitRow,
        source_rows: structuredDataset.sourceRows,
        excluded_derived_rows: structuredDataset.excludedRows,
        metadata: structuredDataset.metadata,
        excluded_derived_columns: structuredDataset.columns
          .filter((_, index) => index !== xColumnIndex && !seriesColumnIndexes.includes(index))
          .map(({ name, unit }) => ({ name, unit })),
      },
    });
  };

  const submitImport = () => {
    const importRows: any[] = [];

    rows.forEach((row) => {
      const material: Record<string, unknown> = {
        name: '',
        material_type: 'other',
        properties: {} as Record<string, number | string>,
      };
      const aliases: string[] = [];
      const testInfo: Record<string, string> = {};

      // Helper: strip dedup suffix from header names for clean property names
      const baseHeader = (h: string) => h.replace(/_\d+$/, '');

      // Group result/condition columns by their test group → one test per group
      // Structure: { [groupName]: { conditions: {}, measurements: {} } }
      const testGroups: Record<string, { conditions: Record<string, string>; measurements: Record<string, number | string> }> = {};

      row.forEach((value, colIdx) => {
        const header = headers[colIdx];
        const target = columnMapping[header] || 'ignore';
        const cleaned = cleanImportCell(value);
        if (!cleaned) return;

        if (target === 'ignore') return;
        if (target === 'aliases') {
          aliases.push(...cleaned.split(/[,;，；]/).map((s) => s.trim()).filter(Boolean));
        } else if (FIXED_FIELDS.includes(target)) {
          material[target] = cleaned;
        } else if (target === 'test_name' || target === 'test_method') {
          testInfo[target] = cleaned;
        } else if (target === 'condition') {
          const group = testGroupMapping[header]?.trim() || '默认';
          if (!testGroups[group]) testGroups[group] = { conditions: {}, measurements: {} };
          testGroups[group].conditions[baseHeader(header.trim())] = cleaned;
        } else if (target === 'result') {
          const group = testGroupMapping[header]?.trim() || '默认';
          if (!testGroups[group]) testGroups[group] = { conditions: {}, measurements: {} };
          const num = parseImportNumber(value);
          testGroups[group].measurements[baseHeader(header.trim())] = num === null ? cleaned : num;
        } else if (target === 'property') {
          const num = parseImportNumber(value);
          (material.properties as Record<string, unknown>)[baseHeader(header.trim())] = num === null ? cleaned : num;
        }
      });

      if (aliases.length > 0) material['aliases'] = aliases.join(',');
      material['name'] = material['name'] || (row[0] === undefined ? '' : cleanImportCell(row[0]));
      if (!material['name']) return;

      // Build test entries from groups
      const testEntries: any[] = [];
      const groupNames = Object.keys(testGroups);
      if (groupNames.length > 0) {
        groupNames.forEach((groupName) => {
          const g = testGroups[groupName];
          if (Object.keys(g.measurements).length === 0) return; // skip groups with no measurements
          testEntries.push({
            test_name: groupName === '默认'
              ? (testInfo['test_name'] || '导入测试')
              : (testInfo['test_name'] ? `${testInfo['test_name']} - ${groupName}` : groupName),
            test_method: testInfo['test_method'] || undefined,
            conditions: g.conditions,
            measurements: g.measurements,
          });
        });
      }

      material['_tests'] = testEntries;
      importRows.push(material);
    });

    // Group rows by material name, merging tests
    const grouped = new Map<string, any>();
    for (const row of importRows) {
      const name = row.name;
      if (!grouped.has(name)) {
        grouped.set(name, {
          ...row,
          _tests: row._tests || [],
        });
      } else {
        const existing = grouped.get(name);
        if (row._tests) existing._tests.push(...row._tests);
        // Merge properties
        if (row.properties) {
          Object.assign(existing.properties, row.properties);
        }
        // Prefer first non-empty values for fixed fields
        for (const field of FIXED_FIELDS) {
          if (!existing[field] && row[field]) {
            existing[field] = row[field];
          }
        }
      }
    }
    const finalRows = Array.from(grouped.values());

    // Build API-compatible rows with tests
    const apiRows = finalRows.map((r) => {
      const apiRow: any = {
        name: r.name,
        material_type: r.material_type || 'other',
        formula_string: r.formula_string || undefined,
        hill_formula: r.hill_formula || undefined,
        aliases: r.aliases || undefined,
        description: r.description || undefined,
        properties: r.properties || {},
      };
      if (r._tests && r._tests.length > 0) {
        apiRow.tests = r._tests.map((t: any) => ({
          test_name: t.test_name,
          test_method: t.test_method,
          conditions: t.conditions,
          measurements: Object.entries(t.measurements).map(([k, v]) => ({
            property_name: k,
            value_number: typeof v === 'number' ? v : undefined,
            value_text: typeof v === 'string' ? v : undefined,
          })),
        }));
      }
      return apiRow;
    });

    importMutation.mutate({ rows: apiRows });
  };

  const handleImport = () => confirmImport(submitImport, qualitySummary.blockingCount === 0);

  const handleDownloadCorrected = () => {
    downloadCorrectedImport(headers, rows, columnMapping, file?.name, qualityIssues);
  };

  const handleDownloadQualityReport = () => {
    downloadImportQualityReport(headers, rows, columnMapping, qualityIssues, file?.name);
  };

  const handleReset = () => {
    setStep(0);
    setFile(null);
    setHeaders([]);
    setRows([]);
    setColumnMapping({});
    setTestGroupMapping({});
    setResult(null);
    setAlignmentResult(null);
    setAlignmentError(null);
    setStructuredDataset(null);
    setDatasetTitle('');
    setSeriesColumnIndexes([]);
    setProjectId(undefined);
    setSampleId(undefined);
    setDatasetResult(null);
  };

  // --- Test group names (derived from current mappings) ---
  const usedGroups = useMemo(() => {
    const groups = new Set<string>();
    headers.forEach((h) => {
      const target = columnMapping[h] || 'ignore';
      if (target === 'result' || target === 'condition') {
        groups.add(testGroupMapping[h]?.trim() || '默认');
      }
    });
    return Array.from(groups);
  }, [headers, columnMapping, testGroupMapping]);

  // --- Step 0: Upload ---
  if (step === 0) {
    return (
      <div>
        <Title level={4}>数据导入</Title>
        <Card style={{ maxWidth: 700, margin: '0 auto' }}>
          <Dragger
            accept=".csv,.xlsx,.xls"
            showUploadList={false}
            beforeUpload={handleFile}
            style={{ padding: '40px 0' }}
          >
            <p className="ant-upload-drag-icon">
              <CloudUploadOutlined style={{ fontSize: 48, color: '#1677ff' }} />
            </p>
            <Title level={5}>点击或拖拽文件到此处</Title>
            <Text type="secondary">支持 .csv / .xlsx / .xls 格式，自动识别中文编码</Text>
          </Dragger>

          {parseError && (
            <Alert type="error" message={parseError} style={{ marginTop: 16 }} closable onClose={() => setParseError(null)} />
          )}

          <Alert
            type="info"
            style={{ marginTop: 24 }}
            message="文件格式说明"
            description={
              <div>
                <p><strong>固定列</strong>（自动识别列名）：名称、类型、化学式、Hill公式、别名、描述</p>
                <p><strong>测试条件 / 测试结果</strong>：可指定"实验组"将结果分到不同的测试中</p>
                <p>第一行为表头，支持中英文列名。示例：</p>
                <code>名称,类型,化学式,温度,频率,介电常数,介电损耗,拉伸强度</code><br />
                <code>PVDF-HFP,聚合物,(C2H2F2)n-(C3F6)m,25,1k,3.5,0.02,45</code>
              </div>
            }
          />
        </Card>
      </div>
    );
  }

  if (step === 1 && structuredDataset) {
    const xColumn = structuredDataset.columns[xColumnIndex];
    const numericSeries = structuredDataset.columns.filter((_, columnIndex) => (
      seriesColumnIndexes.includes(columnIndex)
      && columnIndex !== xColumnIndex
      && structuredDataset.rows.every((row) => parseImportNumber(row[columnIndex]) !== null)
    ));
    const xValuesValid = structuredDataset.rows.every((row) => parseImportNumber(row[xColumnIndex]) !== null);
    const canImport = Boolean(sampleId && datasetTitle.trim() && xValuesValid && numericSeries.length > 0);
    const errorDetail = (datasetMutation.error as any)?.response?.data?.detail
      || (datasetMutation.error as Error | null)?.message;
    const previewColumns = structuredDataset.columns.map((column, index) => ({
      title: `${column.name}${column.unit ? ` (${column.unit})` : ''}`,
      key: column.key,
      render: (_: unknown, row: ImportCell[]) => row[index] === '' ? '-' : row[index],
    }));
    return (
      <div>
        <Title level={4}><EyeOutlined /> 测量数据集预览</Title>
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message={`已识别为连续/重复测量数据：${structuredDataset.rows.length} 个有效测点`}
          description={`字段位于第 ${structuredDataset.headerRow} 行${structuredDataset.unitRow ? `，单位位于第 ${structuredDataset.unitRow} 行` : ''}；已排除 ${structuredDataset.excludedRows.length} 条派生统计记录。确认前不会写入数据库。`}
        />
        {structuredDataset.excludedRows.length > 0 && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="未导入的派生统计行"
            description={structuredDataset.excludedRows.map((row) => `${row.label}（源文件第 ${row.sourceRow} 行）`).join('、')}
          />
        )}
        {structuredDataset.metadata.length > 0 && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message={`已提取 ${structuredDataset.metadata.length} 项测试说明，将保存到溯源信息`}
            description={structuredDataset.metadata.slice(0, 8).map((item) => `${item.name}：${item.value}${item.unit ? ` ${item.unit}` : ''}`).join('；')}
          />
        )}
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Text strong>数据集名称</Text>
              <Input value={datasetTitle} onChange={(event) => setDatasetTitle(event.target.value)} style={{ marginTop: 8 }} />
            </Col>
            <Col span={24}>
              <Text strong>保存的原始数值列</Text>
              <Checkbox.Group
                value={seriesColumnIndexes}
                onChange={(values) => setSeriesColumnIndexes(values as number[])}
                options={structuredDataset.columns.map((column, index) => ({
                  value: index,
                  disabled: index === xColumnIndex,
                  label: `${column.name}${column.unit ? ` (${column.unit})` : ''}${structuredDataset.suggestedSeriesColumnIndexes.includes(index) ? '（建议保留）' : '（派生列）'}`,
                })).filter((option) => option.value !== xColumnIndex)}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text strong>横坐标</Text>
              <Select
                value={xColumnIndex}
                onChange={setXColumnIndex}
                options={structuredDataset.columns.map((column, index) => ({
                  value: index,
                  label: `${column.name}${column.unit ? ` (${column.unit})` : ''}`,
                }))}
                style={{ width: '100%', marginTop: 8 }}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text strong>所属项目</Text>
              <Select
                value={projectId}
                onChange={(value) => { setProjectId(value); setSampleId(undefined); }}
                options={projectsQuery.data?.items.map((project) => ({ value: project.id, label: project.name }))}
                loading={projectsQuery.isLoading}
                showSearch
                optionFilterProp="label"
                placeholder="选择项目"
                style={{ width: '100%', marginTop: 8 }}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text strong>所属样品</Text>
              <Select
                value={sampleId}
                onChange={setSampleId}
                options={samplesQuery.data?.items.map((sample) => ({ value: sample.id, label: sample.sample_code }))}
                loading={samplesQuery.isLoading}
                disabled={!projectId}
                showSearch
                optionFilterProp="label"
                placeholder="选择样品"
                style={{ width: '100%', marginTop: 8 }}
              />
            </Col>
          </Row>
        </Card>
        {!xValuesValid && <Alert type="error" showIcon message="所选横坐标包含非数值，不能导入" style={{ marginBottom: 16 }} />}
        {errorDetail && <Alert type="error" showIcon message="数据集导入失败" description={errorDetail} style={{ marginBottom: 16 }} />}
        <Descriptions size="small" bordered style={{ marginBottom: 16 }}>
          <Descriptions.Item label="源文件">{file?.name}</Descriptions.Item>
          <Descriptions.Item label="有效测点">{structuredDataset.rows.length}</Descriptions.Item>
          <Descriptions.Item label="保存序列">{numericSeries.length}</Descriptions.Item>
          <Descriptions.Item label="排除派生列">{structuredDataset.columns.length - numericSeries.length - 1}</Descriptions.Item>
          <Descriptions.Item label="横坐标">{xColumn.name}{xColumn.unit ? ` (${xColumn.unit})` : ''}</Descriptions.Item>
        </Descriptions>
        <Table
          columns={previewColumns}
          dataSource={structuredDataset.rows.slice(0, 10)}
          rowKey={(_, index) => String(index)}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={handleReset}>重新上传</Button>
          <Button
            type="primary"
            onClick={() => confirmImport(submitDatasetImport)}
            loading={datasetMutation.isPending}
            disabled={!canImport}
          >
            确认导入数据集
          </Button>
        </Space>
      </div>
    );
  }

  // --- Step 1: Preview & Column Mapping ---
  if (step === 1) {
    const previewRows = rows.slice(0, 5);
    const totalRows = rows.length;

    // Build preview table columns
    const previewColumns = headers.map((h) => ({
      title: (
        <div style={{ minWidth: 110 }}>
          <div style={{ fontWeight: 600, marginBottom: 4, wordBreak: 'break-all' }}>{h}</div>
          <Select
            size="small"
            value={columnMapping[h] || 'ignore'}
            onChange={(v) => setColumnMapping({ ...columnMapping, [h]: v })}
            style={{ width: '100%', marginBottom: 4 }}
            options={[
              { label: '→ 材料名称', value: 'name' },
              { label: '→ 材料类型', value: 'material_type' },
              { label: '→ 化学式', value: 'formula_string' },
              { label: '→ Hill公式', value: 'hill_formula' },
              { label: '→ 别名', value: 'aliases' },
              { label: '→ 描述', value: 'description' },
              { label: '→ 测试名称', value: 'test_name' },
              { label: '→ 测试方法', value: 'test_method' },
              { label: '→ 属性', value: 'property' },
              { label: '→ 测试条件', value: 'condition' },
              { label: '→ 测试结果', value: 'result' },
              { label: '忽略', value: 'ignore' },
            ]}
          />
          {(columnMapping[h] === 'result' || columnMapping[h] === 'condition') && (
            <Input
              size="small"
              placeholder="实验组（默认）"
              value={testGroupMapping[h] || ''}
              onChange={(e) => setTestGroupMapping({ ...testGroupMapping, [h]: e.target.value })}
              style={{ width: '100%', fontSize: 11 }}
            />
          )}
        </div>
      ),
      dataIndex: h,
      key: h,
      render: (value: ImportCell) => <Text>{value === '' ? '-' : value}</Text>,
    }));

    const hasName = Object.values(columnMapping).includes('name');
    const resultCols = headers.filter((h) => (columnMapping[h] || 'ignore') === 'result');
    const conditionCols = headers.filter((h) => (columnMapping[h] || 'ignore') === 'condition');

    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>
            <EyeOutlined /> 预览数据
          </Title>
          <Space>
            <Button onClick={handleReset}>重新上传</Button>
            <Button
              icon={<RobotOutlined />}
              onClick={() => alignmentMutation.mutate({ headers, rows })}
              loading={alignmentMutation.isPending}
            >
              AI 助手格式对齐
            </Button>
            {alignmentResult && (
              <Button icon={<DownloadOutlined />} onClick={handleDownloadCorrected}>
                下载订正数据
              </Button>
            )}
            <Button
              type="primary"
              onClick={handleImport}
              loading={importMutation.isPending}
              disabled={!hasName || qualitySummary.blockingCount > 0}
            >
              确认导入（{totalRows} 行）
            </Button>
          </Space>
        </div>

        <Alert
          type={qualitySummary.blockingCount > 0 ? 'error' : qualitySummary.warningCount > 0 ? 'warning' : 'success'}
          showIcon
          style={{ marginBottom: 16 }}
          message={qualitySummary.issueCount === 0
            ? '数据质量预检通过，可以确认导入'
            : `数据质量预检：${qualitySummary.blockingCount} 个阻断问题，${qualitySummary.warningCount} 个警告`}
          description={qualityIssues.length > 0
            ? qualityIssues.slice(0, 5).map((issue) => (
              <div key={`${issue.code}-${issue.sourceRow || 0}-${issue.column || ''}`}>
                {issue.sourceRow ? `源文件第 ${issue.sourceRow} 行：` : ''}{issue.message}
              </div>
            ))
            : '已检查材料名称完整性、文件内重复名称和数值列类型一致性。'}
          action={qualityIssues.length > 0 ? (
            <Button size="small" icon={<DownloadOutlined />} onClick={handleDownloadQualityReport}>
              下载质量报告
            </Button>
          ) : undefined}
        />

        <Descriptions size="small" bordered style={{ marginBottom: 16 }}>
          <Descriptions.Item label="文件">{file?.name}</Descriptions.Item>
          <Descriptions.Item label="数据行">{totalRows} 行</Descriptions.Item>
          <Descriptions.Item label="列数">{headers.length} 列</Descriptions.Item>
        </Descriptions>

        {alignmentResult && (
          <Alert
            type="success"
            showIcon
            closable
            onClose={() => setAlignmentResult(null)}
            style={{ marginBottom: 16 }}
            message={`格式对齐预览已应用，共规范化 ${alignmentResult.conversion_count} 个值`}
            description={alignmentResult.warnings.length > 0
              ? alignmentResult.warnings.join('；')
              : '已根据系统导入字段核对列映射；仅将完整、无歧义的科学计数法文本转换为数字。请继续核对后再确认导入。'}
          />
        )}
        {alignmentError && (
          <Alert
            type="error"
            showIcon
            closable
            onClose={() => setAlignmentError(null)}
            style={{ marginBottom: 16 }}
            message="AI 助手格式对齐失败"
            description={alignmentError}
          />
        )}

        {/* Test group summary */}
        {(resultCols.length > 0 || conditionCols.length > 0) && usedGroups.length > 0 && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message={
              <Space size="small" wrap>
                <Text>实验组划分：</Text>
                {usedGroups.map((g) => {
                  const cols = headers.filter(
                    (h) => (testGroupMapping[h]?.trim() || '默认') === g && ['result', 'condition'].includes(columnMapping[h] || '')
                  );
                  return (
                    <Tag key={g} color="blue">
                      {g === '默认' ? '默认组' : g}（{cols.length} 列）
                    </Tag>
                  );
                })}
              </Space>
            }
            description={
              <span>
                同一「实验组」的结果列会合并到一个测试中。不同组的列分开为独立测试。
                <Tooltip title={'例如：将「介电常数」和「介电损耗」设为组A，「拉伸强度」设为组B → 生成2个测试'}>
                  <QuestionCircleOutlined style={{ marginLeft: 4, color: '#1677ff' }} />
                </Tooltip>
              </span>
            }
          />
        )}

        <div style={{ marginBottom: 12, fontSize: 13 }}>
          <Text type="secondary">
            每列标题下方的下拉框选择映射目标，输入框指定实验组（同组结果列合并为一个测试）。
            系统已自动识别，请核对后点击"确认导入"。
          </Text>
        </div>

        <Table
          columns={previewColumns}
          dataSource={previewRows.map((row, i) => {
            const obj: Record<string, ImportCell> = { key: String(i) };
            headers.forEach((h, j) => { obj[h] = row[j] ?? ''; });
            return obj;
          })}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="small"
        />
      </div>
    );
  }

  // --- Step 2: Import Result ---
  const success = result?.created || 0;
  const failed = result?.failed || 0;

  if (datasetResult) {
    return (
      <div>
        <Title level={4}>数据集导入完成</Title>
        <Alert
          type="success"
          showIcon
          message={`已保存数据集“${datasetResult.name}”`}
          description={`共 ${datasetResult.row_count} 个测点、${datasetResult.series_schema.length} 个数值序列；数据可通过测量数据集接口读取并用于可视化。`}
          style={{ marginBottom: 16 }}
        />
        <Descriptions bordered style={{ marginBottom: 16 }}>
          <Descriptions.Item label="数据集 ID">{datasetResult.id}</Descriptions.Item>
          <Descriptions.Item label="横坐标">{datasetResult.x_name}{datasetResult.x_unit ? ` (${datasetResult.x_unit})` : ''}</Descriptions.Item>
          <Descriptions.Item label="测点数量">{datasetResult.row_count}</Descriptions.Item>
        </Descriptions>
        <Space>
          <Button type="primary" onClick={() => navigate(`/measurement-datasets/${datasetResult.id}`)}>查看、修改与可视化</Button>
          <Button onClick={handleReset}>继续导入</Button>
        </Space>
      </div>
    );
  }

  return (
    <div>
      <Title level={4}>导入结果</Title>

      <Row gutter={24} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="总计" value={result?.total || 0} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="成功"
              value={success}
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="失败"
              value={failed}
              valueStyle={{ color: failed > 0 ? '#cf1322' : undefined }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {failed > 0 && result?.errors && (
        <Card title="失败明细" style={{ marginBottom: 24 }}>
          {result.errors.map((e, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <Text type="danger">
                · 第 {e.row} 行: {e.message}
              </Text>
            </div>
          ))}
        </Card>
      )}

      <Space>
        <Button type="primary" onClick={handleReset}>继续导入</Button>
        <Button onClick={() => navigate('/materials')}>查看材料列表</Button>
      </Space>
    </div>
  );
}

