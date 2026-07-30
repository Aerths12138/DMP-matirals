import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, Button, Table, Tag, Typography, Space, Alert, Statistic,
  Card, Row, Col, Select, Descriptions, Input, Tooltip,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined,
  FileTextOutlined, EyeOutlined, CloudUploadOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { parseFile, autoMapColumns } from '../../utils/fileParser';
import { importMaterials } from '../../api/materials';
import type { ImportResult } from '../../api/materials';

const { Title, Text } = Typography;
const { Dragger } = Upload;

const FIXED_FIELDS = ['name', 'material_type', 'formula_string', 'hill_formula', 'aliases', 'description'];

export default function DataImportPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [testGroupMapping, setTestGroupMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  // Step 0: Handle file upload
  const handleFile = async (f: File) => {
    setFile(f);
    setParseError(null);
    try {
      const csvData = await parseFile(f);
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

  const handleImport = () => {
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
        const cleaned = value.trim();
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
          const num = Number(cleaned);
          testGroups[group].measurements[baseHeader(header.trim())] = isNaN(num) ? cleaned : num;
        } else if (target === 'property') {
          const num = Number(cleaned);
          (material.properties as Record<string, unknown>)[baseHeader(header.trim())] = isNaN(num) ? cleaned : num;
        }
      });

      if (aliases.length > 0) material['aliases'] = aliases.join(',');
      material['name'] = material['name'] || row[0]?.trim() || '';
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

  const handleReset = () => {
    setStep(0);
    setFile(null);
    setHeaders([]);
    setRows([]);
    setColumnMapping({});
    setTestGroupMapping({});
    setResult(null);
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
      render: (value: string) => <Text>{value || '-'}</Text>,
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
            <Button type="primary" onClick={handleImport} loading={importMutation.isPending} disabled={!hasName}>
              确认导入（{totalRows} 行）
            </Button>
          </Space>
        </div>

        {!hasName && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message={'请将一列映射为「材料名称」（必填）'}
          />
        )}

        <Descriptions size="small" bordered style={{ marginBottom: 16 }}>
          <Descriptions.Item label="文件">{file?.name}</Descriptions.Item>
          <Descriptions.Item label="数据行">{totalRows} 行</Descriptions.Item>
          <Descriptions.Item label="列数">{headers.length} 列</Descriptions.Item>
        </Descriptions>

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
            const obj: Record<string, string> = { key: String(i) };
            headers.forEach((h, j) => { obj[h] = row[j] || ''; });
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

