import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, message,
} from 'antd';
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined, BarChartOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { evalsAPI, projectsAPI, modelsAPI, datasetsAPI, metricsAPI } from '../services/api';
import type { EvalTask, Project, LLMModel, Dataset, Metric } from '../types';

function EvalTasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<EvalTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [projects, setProjects] = useState<Project[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [metricsList, setMetricsList] = useState<Metric[]>([]);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await evalsAPI.list(1, 100);
      setTasks(res.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载评测任务失败');
    } finally {
      setLoading(false);
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
    fetchTasks();
  }, []);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values };
      if (Array.isArray(payload.metric_ids)) {
        payload.metric_ids = payload.metric_ids.join(',');
      }
      await evalsAPI.create(payload);
      message.success('创建成功');
      setModalOpen(false);
      fetchTasks();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const handleStart = async (id: number) => {
    try {
      await evalsAPI.start(id);
      message.success('任务已启动');
      fetchTasks();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '启动失败');
    }
  };

  const handleCancel = async (id: number) => {
    try {
      await evalsAPI.cancel(id);
      message.success('任务已取消');
      fetchTasks();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const statusTag = (status: string) => {
    const colorMap: Record<string, string> = {
      pending: 'default', running: 'processing', completed: 'success',
      failed: 'error', cancelled: 'warning',
    };
    const labelMap: Record<string, string> = {
      pending: '等待中', running: '运行中', completed: '已完成',
      failed: '失败', cancelled: '已取消',
    };
    return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
  };

  const columns: ColumnsType<EvalTask> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (s: string) => statusTag(s) },
    {
      title: '模型', dataIndex: 'model_id', key: 'model_id', width: 80,
      render: (v: number) => {
        const m = models.find((x) => x.id === v);
        return m?.name || `#${v}`;
      },
    },
    {
      title: '数据集', dataIndex: 'dataset_id', key: 'dataset_id', width: 100,
      render: (v: number) => {
        const d = datasets.find((x) => x.id === v);
        return d?.name || `#${v}`;
      },
    },
    {
      title: '综合得分', dataIndex: 'overall_score', key: 'overall_score', width: 100,
      render: (v: number) => v != null ? v.toFixed(2) : '-',
    },
    {
      title: '进度', key: 'progress', width: 80,
      render: (_, r) => `${r.completed_items || 0}/${r.total_items || 0}`,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '操作', key: 'actions', width: 240,
      render: (_, record) => (
        <Space>
          {record.status === 'pending' && (
            <Button type="link" icon={<PlayCircleOutlined />} onClick={() => handleStart(record.id)}>
              开始
            </Button>
          )}
          {record.status === 'running' && (
            <Button type="link" danger icon={<PauseCircleOutlined />} onClick={() => handleCancel(record.id)}>
              取消
            </Button>
          )}
          <Button type="link" icon={<BarChartOutlined />} onClick={() => navigate(`/eval-tasks/${record.id}/report`)}>
            报告
          </Button>
        </Space>
      ),
    },
  ];

  useEffect(() => {
    if (tasks.length > 0) fetchRefs();
  }, [tasks.length]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>评测任务</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { fetchRefs(); form.resetFields(); setModalOpen(true); }}>
          创建任务
        </Button>
      </div>

      <Table columns={columns} dataSource={tasks} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />

      <Modal
        title="创建评测任务"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleCreate}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入' }]}>
            <Input placeholder="评测任务名称" />
          </Form.Item>
          <Form.Item name="project_id" label="所属项目">
            <Select placeholder="选择项目" allowClear>
              {projects.map((p) => <Select.Option key={p.id} value={p.id}>{p.name}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="model_id" label="评测模型" rules={[{ required: true, message: '请选择' }]}>
            <Select placeholder="选择模型">
              {models.map((m) => <Select.Option key={m.id} value={m.id}>{m.name}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="dataset_id" label="数据集" rules={[{ required: true, message: '请选择' }]}>
            <Select placeholder="选择数据集">
              {datasets.map((d) => <Select.Option key={d.id} value={d.id}>{d.name}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="metric_ids" label="评测标准" rules={[{ required: true, message: '请选择' }]}>
            <Select mode="multiple" placeholder="选择评测标准">
              {metricsList.map((m) => <Select.Option key={m.id} value={m.id}>{m.name}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="prompt_content" label="Prompt内容">
            <Input.TextArea rows={5} placeholder="{input} 会被替换为数据集中的输入文本" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default EvalTasksPage;
