import { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, message, Tabs, Popconfirm, Empty,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import { promptsAPI, projectsAPI, modelsAPI, datasetsAPI, metricsAPI } from '../services/api';
import type { Prompt, PromptVersion, OptimizationTask, Project, LLMModel, Dataset, Metric } from '../types';

interface OptTaskDisplay {
  id: number;
  name: string;
  status: string;
  best_score: number;
  current_round: number;
  max_rounds: number;
}

function PromptsPage() {
  const navigate = useNavigate();
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [optTasks, setOptTasks] = useState<OptTaskDisplay[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('prompts');
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [optModalOpen, setOptModalOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [metricsList, setMetricsList] = useState<Metric[]>([]);
  const [promptForm] = Form.useForm();
  const [optForm] = Form.useForm();
  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null);

  const fetchPrompts = async () => {
    setLoading(true);
    try {
      const res = await promptsAPI.list(1, 100);
      setPrompts(res.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载Prompt列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchOptTasks = async () => {
    try {
      const res = await promptsAPI.listOptimization(1, 100);
      setOptTasks(res.data.items || []);
    } catch {
      setOptTasks([]);
    }
  };

  const fetchRefs = async () => {
    try {
      const [pjRes, mdRes, dsRes, mtRes] = await Promise.all([
        projectsAPI.list(1, 100),
        modelsAPI.list(1, 100),
        datasetsAPI.list(1, 100),
        metricsAPI.list(1, 100),
      ]);
      setProjects(pjRes.data.items || []);
      setModels(mdRes.data.items || []);
      setDatasets(dsRes.data.items || []);
      setMetricsList(mtRes.data.items || []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchPrompts();
    fetchOptTasks();
  }, []);

  const handlePromptSubmit = async () => {
    try {
      const values = await promptForm.validateFields();
      if (editingPrompt) {
        await promptsAPI.update(editingPrompt.id, values);
        message.success('更新成功');
      } else {
        await promptsAPI.create(values);
        message.success('创建成功');
      }
      setPromptModalOpen(false);
      fetchPrompts();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const handleOptSubmit = async () => {
    try {
      const values = await optForm.validateFields();
      if (Array.isArray(values.metric_ids)) {
        values.metric_ids = values.metric_ids.join(',');
      }
      const res = await promptsAPI.createOptimization(values);
      message.success('优化任务创建成功');
      setOptModalOpen(false);
      const created: OptimizationTask = res.data;
      if (created?.id) {
        navigate(`/prompts/optimization/${created.id}`);
      } else {
        fetchOptTasks();
      }
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const handleDeletePrompt = async (id: number) => {
    try {
      await promptsAPI.delete(id);
      message.success('删除成功');
      fetchPrompts();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const handleShowVersions = async (record: Prompt) => {
    setSelectedPrompt(record);
    setVersionModalOpen(true);
    setVersionsLoading(true);
    try {
      const res = await promptsAPI.versions(record.id);
      setVersions(res.data.items || []);
    } catch {
      setVersions([]);
    } finally {
      setVersionsLoading(false);
    }
  };

  const statusTag = (status: string) => {
    const colorMap: Record<string, string> = {
      pending: 'default',
      running: 'processing',
      completed: 'success',
      failed: 'error',
      cancelled: 'warning',
    };
    const labelMap: Record<string, string> = {
      pending: '等待中',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消',
    };
    return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
  };

  const promptColumns: ColumnsType<Prompt> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '场景', dataIndex: 'scene', key: 'scene', width: 100,
      render: (s: string) => <Tag>{s || '-'}</Tag>,
    },
    {
      title: '最佳得分',
      dataIndex: 'best_score',
      key: 'best_score',
      width: 100,
      render: (v: number) => (v != null ? v.toFixed(2) : '-'),
    },
    { title: '版本', dataIndex: 'current_version', key: 'current_version', width: 80 },
    {
      title: '来源', dataIndex: 'source', key: 'source', width: 100,
      render: (s: string) => {
        const map: Record<string, { label: string; color: string }> = {
          prompt_page: { label: 'Prompt页面', color: 'blue' },
          eval_task: { label: '评测任务', color: 'green' },
        };
        const info = map[s] || { label: s || '-', color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingPrompt(record);
              promptForm.setFieldsValue(record);
              setPromptModalOpen(true);
            }}
          >
            编辑
          </Button>
          <Button
            type="link"
            icon={<ThunderboltOutlined />}
            onClick={() => {
              fetchRefs();
              optForm.resetFields();
              optForm.setFieldsValue({
                prompt_id: record.id,
                initial_prompt: record.current_content,
                name: `${record.name} - 优化`,
              });
              setOptModalOpen(true);
            }}
          >
            优化
          </Button>
          <Button type="link" onClick={() => handleShowVersions(record)}>
            版本
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDeletePrompt(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const optColumns: ColumnsType<OptTaskDisplay> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => statusTag(s),
    },
    {
      title: '最佳得分',
      dataIndex: 'best_score',
      key: 'best_score',
      width: 100,
      render: (v: number) => (v != null ? v.toFixed(2) : '-'),
    },
    {
      title: '进度', key: 'progress', width: 100,
      render: (_, r) => `${r.current_round || 0}/${r.max_rounds || 0}`,
    },
    {
      title: '操作', key: 'actions', width: 100,
      render: (_, record) => (
        <Button type="link" onClick={() => navigate(`/prompts/optimization/${record.id}`)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Prompt管理</h2>
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <Tabs.TabPane tab="Prompt列表" key="prompts">
          <div style={{ marginBottom: 16, textAlign: 'right' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingPrompt(null);
                promptForm.resetFields();
                setPromptModalOpen(true);
              }}
            >
              创建Prompt
            </Button>
          </div>
          <Table
            columns={promptColumns}
            dataSource={prompts}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 20 }}
          />
        </Tabs.TabPane>
        <Tabs.TabPane tab="优化任务" key="optimization">
          <div style={{ marginBottom: 16, textAlign: 'right' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                fetchRefs();
                optForm.resetFields();
                setOptModalOpen(true);
              }}
            >
              新建优化任务
            </Button>
          </div>
          {optTasks.length > 0 ? (
            <Table
              columns={optColumns}
              dataSource={optTasks}
              rowKey="id"
              pagination={{ pageSize: 20 }}
            />
          ) : (
            <Empty description="暂无优化任务，请先从Prompt列表中选择一个进行优化" />
          )}
        </Tabs.TabPane>
      </Tabs>

      <Modal
        title={editingPrompt ? '编辑Prompt' : '创建Prompt'}
        open={promptModalOpen}
        onCancel={() => setPromptModalOpen(false)}
        onOk={handlePromptSubmit}
        width={600}
        destroyOnClose
      >
        <Form form={promptForm} layout="vertical" preserve={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="Prompt名称" />
          </Form.Item>
          <Form.Item name="scene" label="场景">
            <Select placeholder="选择场景">
              <Select.Option value="chat">Chat</Select.Option>
              <Select.Option value="code">Code</Select.Option>
              <Select.Option value="qa">QA</Select.Option>
              <Select.Option value="multimodal">Multimodal</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="content"
            label="Prompt内容"
            rules={[{ required: true, message: '请输入内容' }]}
          >
            <Input.TextArea rows={6} placeholder="输入Prompt模板..." />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="新建优化任务"
        open={optModalOpen}
        onCancel={() => setOptModalOpen(false)}
        onOk={handleOptSubmit}
        width={700}
        destroyOnClose
      >
        <Form form={optForm} layout="vertical" preserve={false}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入' }]}>
            <Input placeholder="优化任务名称" />
          </Form.Item>
          <Form.Item name="project_id" label="所属项目">
            <Select placeholder="选择项目" allowClear>
              {projects.map((p) => (
                <Select.Option key={p.id} value={p.id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="model_id" label="目标模型" rules={[{ required: true, message: '请选择' }]}>
            <Select placeholder="选择要优化的模型">
              {models.map((m) => (
                <Select.Option key={m.id} value={m.id}>
                  {m.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="optimizer_model_id" label="优化器模型" rules={[{ required: true, message: '请选择' }]}>
            <Select placeholder="选择用于优化的模型">
              {models.map((m) => (
                <Select.Option key={m.id} value={m.id}>
                  {m.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="dataset_id" label="数据集" rules={[{ required: true, message: '请选择' }]}>
            <Select placeholder="选择评测数据集">
              {datasets.map((d) => (
                <Select.Option key={d.id} value={d.id}>
                  {d.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="metric_ids" label="评测标准">
            <Select mode="multiple" placeholder="选择评测标准">
              {metricsList.map((m) => (
                <Select.Option key={m.id} value={m.id}>
                  {m.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="prompt_id" hidden>
            <Input />
          </Form.Item>
          <Form.Item name="initial_prompt" label="初始Prompt" rules={[{ required: true, message: '请输入' }]}>
            <Input.TextArea rows={4} placeholder="初始Prompt模板（支持 {input} 变量和 [SYSTEM]...[/SYSTEM] 格式）" />
          </Form.Item>
          <Form.Item name="strategy" label="优化策略" initialValue="balanced">
            <Select>
              <Select.Option value="conservative">保守模式 — 小步迭代，精细调优（5轮×2候选）</Select.Option>
              <Select.Option value="balanced">均衡模式 — 兼顾深度与效率（10轮×3候选）</Select.Option>
              <Select.Option value="aggressive">激进模式 — 大幅探索，更快收敛（15轮×5候选）</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="max_rounds" label="最大轮次（0=按策略）" initialValue={0}>
            <Input type="number" min={0} max={50} />
          </Form.Item>
          <Form.Item name="candidates_per_round" label="每轮候选数（0=按策略）" initialValue={0}>
            <Input type="number" min={0} max={20} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={selectedPrompt ? `版本历史 - ${selectedPrompt.name}` : '版本历史'}
        open={versionModalOpen}
        onCancel={() => setVersionModalOpen(false)}
        footer={null}
        width={800}
      >
        <Table
          dataSource={versions}
          rowKey="id"
          loading={versionsLoading}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
            { title: '得分', dataIndex: 'score', key: 'score', width: 80, render: (v: number) => v?.toFixed(4) || '-' },
            {
              title: '来源', dataIndex: 'source', key: 'source', width: 80,
              render: (s: string) => {
                const map: Record<string, string> = { initial: '初始', manual: '手动', optimization: '优化' };
                return <Tag>{map[s] || s}</Tag>;
              },
            },
            {
              title: '内容', dataIndex: 'content', key: 'content', ellipsis: true,
              render: (c: string) => (
                <div style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c}
                </div>
              ),
            },
            {
              title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
              render: (v: string) => v ? new Date(v).toLocaleString() : '-',
            },
          ]}
        />
      </Modal>
    </div>
  );
}

export default PromptsPage;
