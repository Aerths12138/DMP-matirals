import { Form, Input, InputNumber, Select, Switch } from 'antd';

import type { MetadataTemplate } from '../../types/dataStandard';

interface MetadataFieldsProps {
  template?: MetadataTemplate;
}

export default function MetadataFields({ template }: MetadataFieldsProps) {
  if (!template) return null;

  return (
    <>
      {template.fields.map((field) => {
        const label = field.unit ? `${field.label}（${field.unit}）` : field.label;
        const rules = field.required
          ? [{ required: true, message: `请填写${field.label}` }]
          : undefined;
        let control = <Input />;

        if (field.options.length) {
          control = <Select options={field.options.map((value) => ({ value, label: value }))} />;
        } else if (field.value_type === 'number' || field.value_type === 'integer') {
          control = (
            <InputNumber
              precision={field.value_type === 'integer' ? 0 : undefined}
              style={{ width: '100%' }}
            />
          );
        } else if (field.value_type === 'boolean') {
          return (
            <Form.Item
              key={field.key}
              name={['metadata', field.key]}
              label={label}
              valuePropName="checked"
              extra={field.description}
            >
              <Switch />
            </Form.Item>
          );
        }

        return (
          <Form.Item
            key={field.key}
            name={['metadata', field.key]}
            label={label}
            rules={rules}
            extra={field.description}
          >
            {control}
          </Form.Item>
        );
      })}
    </>
  );
}
