import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Row, Col, Card, Statistic, Table, Tag, Descriptions, Spin, message, Button,
} from 'antd';
import {
  DatabaseOutlined, PlayCircleOutlined, ExperimentOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { projectsAPI, evalsAPI } from '../services/api';
import type { ProjectDashboard as PDashboard, EvalTask, OptimizationTask } from '../types';

function ProjectDashboard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<PDashboard | null>(null);
  const [evalTasks, setEvalTasks] = useState<EvalTask[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const [dbRes, evRes] = await Promise.all([
          projectsAPI.dashboard(Number(id)),
          evalsAPI.list(1, 100, { project_id: Number(id) }),
        ]);
        setDashboard(dbRes.data);
        setEvalTasks(evRes.data.items || []);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        message.error(error?.response?.data?.detail || '加载项目信息失败');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const evalColumns: ColumnsType<EvalTask> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default', running: 'processing', completed: 'success',
          failed: 'error', cancelled: 'warning',
        };
        return <Tag color={colorMap[s] || 'default'}>{s}</Tag>;
      },
    },
    {
      title: '得分', dataIndex: 'overall_score', key: 'overall_score', width: 80,
      render: (v: number) => v != null ? v.toFixed(2) : '-',
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '', key: 'go', width: 80,
      render: (_, r) => (
        <Button type="link" size="small" onClick={() => navigate(`/eval-tasks/${r.id}/report`)}>
          查看
        </Button>
      ),
    },
  ];

  const optColumns: ColumnsType<OptimizationTask> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default', running: 'processing', completed: 'success',
          failed: 'error', cancelled: 'warning',
        };
        return <Tag color={colorMap[s] || 'default'}>{s}</Tag>;
      },
    },
    {
      title: '最佳得分', dataIndex: 'best_score', key: 'best_score', width: 100,
      render: (v: number) => v != null ? v.toFixed(2) : '-',
    },
    {
      title: '', key: 'go', width: 80,
      render: (_, r) => (
        <Button type="link" size="small" onClick={() => navigate(`/prompts/optimization/${r.id}`)}>
          查看
        </Button>
      ),
    },
  ];

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  const project = dashboard?.project;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')} style={{ marginBottom: 16 }}>
        返回项目列表
      </Button>

      {project && (
        <Card style={{ marginBottom: 16 }}>
          <Descriptions title={project.name} column={3} size="small">
            <Descriptions.Item label="类型">
              <Tag color="blue">{project.project_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">{project.status}</Descriptions.Item>
            <Descriptions.Item label="描述">{project.description || '-'}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="数据集数量"
              value={dashboard?.dataset_count || 0}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="评测任务数量"
              value={dashboard?.eval_task_count || 0}
              prefix={<PlayCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="优化任务数量"
              value={dashboard?.optimization_task_count || 0}
              prefix={<ExperimentOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="最近评测任务" style={{ marginBottom: 16 }}>
        <Table columns={evalColumns} dataSource={evalTasks} rowKey="id" pagination={false} size="small" />
      </Card>

      <Card title="最近优化任务">
        <Table columns={optColumns} dataSource={[]} rowKey="id" pagination={false} size="small" />
      </Card>
    </div>
  );
}

export default ProjectDashboard;
