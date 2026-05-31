import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Table, Button, Space, Tag, message, Spin, Descriptions, Statistic,
} from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import * as echarts from 'echarts';
import type { ColumnsType } from 'antd/es/table';
import { promptsAPI } from '../services/api';
import type { OptimizationTask, OptimizationRound } from '../types';

function PromptOptimization() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<OptimizationTask | null>(null);
  const [rounds, setRounds] = useState<OptimizationRound[]>([]);
  const [loading, setLoading] = useState(true);
  const chartRef = useRef<HTMLDivElement>(null);

  const fetchTask = useCallback(async () => {
    if (!id) return;
    try {
      const res = await promptsAPI.getOptimization(Number(id));
      setTask(res.data);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载任务失败');
    }
  }, [id]);

  const fetchRounds = useCallback(async () => {
    if (!id) return;
    try {
      const res = await promptsAPI.optimizationRounds(Number(id));
      setRounds(res.data.items || res.data || []);
    } catch {
      // ignore
    }
  }, [id]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchTask(), fetchRounds()]);
      setLoading(false);
    };
    load();
  }, [fetchTask, fetchRounds]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (task && task.status === 'running') {
      interval = setInterval(() => {
        fetchTask();
        fetchRounds();
      }, 3000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [task?.status, fetchTask, fetchRounds]);

  useEffect(() => {
    if (!chartRef.current || rounds.length === 0) return;
    const chart = echarts.init(chartRef.current);
    const sortedRounds = [...rounds].sort((a, b) => a.round_number - b.round_number);
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['优化前', '优化后'] },
      xAxis: { type: 'category', data: sortedRounds.map((r) => `第${r.round_number}轮`) },
      yAxis: { type: 'value', name: '分数' },
      series: [
        {
          name: '优化前', type: 'line',
          data: sortedRounds.map((r) => r.score_before),
          lineStyle: { color: '#ff4d4f' },
        },
        {
          name: '优化后', type: 'line',
          data: sortedRounds.map((r) => r.score_after),
          lineStyle: { color: '#52c41a' },
        },
      ],
    });
    return () => chart.dispose();
  }, [rounds]);

  const handleStart = async () => {
    if (!id) return;
    try {
      await promptsAPI.startOptimization(Number(id));
      message.success('优化任务已启动');
      fetchTask();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '启动失败');
    }
  };

  const handleCancel = async () => {
    if (!id) return;
    try {
      await promptsAPI.cancelOptimization(Number(id));
      message.success('任务已取消');
      fetchTask();
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

  const columns: ColumnsType<OptimizationRound> = [
    { title: '轮次', dataIndex: 'round_number', key: 'round_number', width: 80 },
    {
      title: '优化前得分', dataIndex: 'score_before', key: 'score_before', width: 120,
      render: (v: number) => v != null ? v.toFixed(4) : '-',
    },
    {
      title: '优化后得分', dataIndex: 'score_after', key: 'score_after', width: 120,
      render: (v: number) => v != null ? v.toFixed(4) : '-',
    },
    {
      title: '提升', key: 'improvement', width: 100,
      render: (_, r) => {
        const diff = (r.score_after || 0) - (r.score_before || 0);
        return <span style={{ color: diff >= 0 ? '#52c41a' : '#ff4d4f' }}>{diff >= 0 ? '+' : ''}{diff.toFixed(4)}</span>;
      },
    },
    { title: '最佳Prompt', dataIndex: 'best_prompt_after', key: 'best_prompt_after', ellipsis: true },
  ];

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompts')} style={{ marginBottom: 16 }}>
        返回
      </Button>

      {task && (
        <>
          <Card style={{ marginBottom: 16 }}>
            <Descriptions title={task.name} column={4} size="small">
              <Descriptions.Item label="状态">{statusTag(task.status)}</Descriptions.Item>
              <Descriptions.Item label="基线得分">
                {task.baseline_score != null ? task.baseline_score.toFixed(4) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="最佳得分">
                <Statistic
                  value={task.best_score != null ? task.best_score.toFixed(4) : '-'}
                  valueStyle={{ fontSize: 16, color: '#1677ff' }}
                />
              </Descriptions.Item>
              <Descriptions.Item label="进度">
                {task.current_round || 0} / {task.max_rounds || 0}
              </Descriptions.Item>
            </Descriptions>
            <Space style={{ marginTop: 12 }}>
              {task.status === 'pending' && (
                <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>
                  开始优化
                </Button>
              )}
              {task.status === 'running' && (
                <Button danger icon={<PauseCircleOutlined />} onClick={handleCancel}>
                  取消
                </Button>
              )}
            </Space>
          </Card>

          <Card title="得分历史" style={{ marginBottom: 16 }}>
            {rounds.length > 0 ? (
              <div ref={chartRef} style={{ height: 300 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无数据</div>
            )}
          </Card>

          <Card title="优化轮次" style={{ marginBottom: 16 }}>
            <Table columns={columns} dataSource={rounds} rowKey="id" pagination={false} size="small" />
          </Card>

          {task.best_prompt && (
            <Card title="当前最佳Prompt">
              <pre style={{
                background: '#f5f5f5', padding: 16, borderRadius: 8,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 400, overflow: 'auto',
              }}>
                {task.best_prompt}
              </pre>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default PromptOptimization;
