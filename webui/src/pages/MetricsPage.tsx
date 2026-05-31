import { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, message, Popconfirm,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { metricsAPI } from '../services/api';
import type { Metric } from '../types';

const BUILTIN_METRICS: Array<{ name: string; code: string; description: string }> = [
  { name: '完全匹配 (EM)', code: 'exact_match', description: '精确字符串匹配' },
  { name: 'BLEU', code: 'bleu', description: '基于n-gram的相似度' },
  { name: 'ROUGE-L', code: 'rouge_l', description: '最长公共子序列匹配' },
  { name: 'F1 Score', code: 'f1', description: '精确率和召回率的调和平均' },
  { name: 'LLM法官', code: 'llm_judge', description: '使用LLM作为评判者打分' },
];

function MetricsPage() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<Metric | null>(null);
  const [form] = Form.useForm();

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await metricsAPI.list(1, 100);
      setMetrics(res.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载评测标准失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const openCreateModal = () => {
    setEditingMetric(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (metric: Metric) => {
    setEditingMetric(metric);
    form.setFieldsValue(metric);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await metricsAPI.delete(id);
      message.success('删除成功');
      fetchMetrics();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values };
      if (!payload.config_json || typeof payload.config_json === 'object') {
        payload.config_json = JSON.stringify(payload.config_json || {});
      }
      if (editingMetric) {
        await metricsAPI.update(editingMetric.id, payload);
        message.success('更新成功');
      } else {
        await metricsAPI.create(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchMetrics();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const columns: ColumnsType<Metric> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '代号', dataIndex: 'code', key: 'code', width: 120 },
    {
      title: '类型',
      dataIndex: 'metric_type',
      key: 'metric_type',
      width: 120,
      render: (t: string) => {
        const labelMap: Record<string, string> = {
          builtin: '内置',
          llm_based: 'LLM评估',
          custom: '自定义',
        };
        return <Tag>{labelMap[t] || t}</Tag>;
      },
    },
    { title: '描述', dataIndex: 'description', key: 'description', width: 200, ellipsis: true },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => (
        <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => {
        const isBuiltin = record.metric_type === 'builtin' || record.code === 'exact_match' || record.code === 'bleu' || record.code === 'rouge_l' || record.code === 'f1' || record.code === 'llm_judge';
        if (isBuiltin) return <Tag color="blue">内置</Tag>;
        return (
          <Space>
            <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
              编辑
            </Button>
            <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  const allMetrics = [
    ...BUILTIN_METRICS.map((bm) => ({
      id: -Math.abs(bm.code.charCodeAt(0)),
      name: bm.name,
      code: bm.code,
      description: bm.description,
      metric_type: 'builtin',
      config_json: '{}',
      status: 'approved',
      is_active: true,
      created_at: '',
    })),
    ...metrics.filter((m) => !['exact_match', 'bleu', 'rouge_l', 'f1', 'llm_judge'].includes(m.code)),
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>评测标准管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          创建标准
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={allMetrics}
        rowKey={(r) => String(r.id)}
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={editingMetric ? '编辑评测标准' : '创建评测标准'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="评测标准名称" />
          </Form.Item>
          <Form.Item name="code" label="代号" rules={[{ required: true, message: '请输入代号' }]}>
            <Input placeholder="唯一代号，如 my_custom_metric" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="描述（可选）" />
          </Form.Item>
          <Form.Item name="metric_type" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select placeholder="选择类型">
              <Select.Option value="builtin">内置</Select.Option>
              <Select.Option value="llm_based">LLM评估</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="config_json" label="配置JSON">
            <Input.TextArea
              rows={4}
              placeholder='{"judge_prompt": "请评估以下回答的准确性...", "model_id": 1}'
            />
          </Form.Item>
          <Form.Item name="custom_code" label="自定义代码（可选）">
            <Input.TextArea
              rows={6}
              placeholder="自定义评估逻辑代码（Python/JavaScript）"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default MetricsPage;
