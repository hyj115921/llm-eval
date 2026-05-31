import { useEffect, useState, useRef } from 'react';
import { Row, Col, Card, Statistic, Spin, message } from 'antd';
import {
  ProjectOutlined,
  ApiOutlined,
  PlayCircleOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { projectsAPI, modelsAPI, evalsAPI, datasetsAPI } from '../services/api';
import type { Project, LLMModel, EvalTask } from '../types';

function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [evalTasks, setEvalTasks] = useState<EvalTask[]>([]);
  const [datasetCount, setDatasetCount] = useState(0);

  const scoreChartRef = useRef<HTMLDivElement>(null);
  const pieChartRef = useRef<HTMLDivElement>(null);
  const statusChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [pjRes, mdRes, evRes, dsRes] = await Promise.all([
          projectsAPI.list(1, 100),
          modelsAPI.list(1, 100),
          evalsAPI.list(1, 100),
          datasetsAPI.list(1, 1),
        ]);
        setProjects(pjRes.data.items || []);
        setModels(mdRes.data.items || []);
        setEvalTasks(evRes.data.items || []);
        setDatasetCount(dsRes.data.total || 0);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        message.error(error?.response?.data?.detail || '加载仪表盘数据失败');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    if (scoreChartRef.current && evalTasks.length > 0) {
      const chart = echarts.init(scoreChartRef.current);
      const tasksWithScore = evalTasks.filter((t) => t.overall_score != null);
      const names = tasksWithScore.map((t) => t.name.length > 15 ? t.name.substring(0, 15) + '...' : t.name);
      const scores = tasksWithScore.map((t) => t.overall_score);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: names, axisLabel: { rotate: 30 } },
        yAxis: { type: 'value', name: '分数', max: 100 },
        series: [{ data: scores, type: 'bar', itemStyle: { color: '#1677ff' } }],
      });
      return () => chart.dispose();
    }
  }, [evalTasks]);

  useEffect(() => {
    if (pieChartRef.current && models.length > 0) {
      const chart = echarts.init(pieChartRef.current);
      const typeMap: Record<string, number> = {};
      models.forEach((m) => {
        typeMap[m.provider] = (typeMap[m.provider] || 0) + 1;
      });
      chart.setOption({
        tooltip: { trigger: 'item' },
        series: [
          {
            type: 'pie',
            radius: ['40%', '70%'],
            data: Object.entries(typeMap).map(([name, value]) => ({ name, value })),
          },
        ],
      });
      return () => chart.dispose();
    }
  }, [models]);

  useEffect(() => {
    if (statusChartRef.current && evalTasks.length > 0) {
      const chart = echarts.init(statusChartRef.current);
      const statusMap: Record<string, number> = {};
      evalTasks.forEach((t) => {
        statusMap[t.status] = (statusMap[t.status] || 0) + 1;
      });
      chart.setOption({
        tooltip: { trigger: 'item' },
        series: [
          {
            type: 'pie',
            data: Object.entries(statusMap).map(([name, value]) => ({ name, value })),
          },
        ],
      });
      return () => chart.dispose();
    }
  }, [evalTasks]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  const activeEvalTasks = evalTasks.filter(
    (t) => t.status === 'running' || t.status === 'pending'
  ).length;

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>
      <Row gutter={[24, 24]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="项目总数"
              value={projects.length}
              prefix={<ProjectOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="模型总数"
              value={models.length}
              prefix={<ApiOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="活跃评测任务"
              value={activeEvalTasks}
              prefix={<PlayCircleOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="数据集总数"
              value={datasetCount}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="评测任务得分">
            {evalTasks.length > 0 ? (
              <div ref={scoreChartRef} style={{ height: 300 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无数据</div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="模型提供商分布">
            {models.length > 0 ? (
              <div ref={pieChartRef} style={{ height: 300 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无数据</div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card title="任务状态概览">
            {evalTasks.length > 0 ? (
              <div ref={statusChartRef} style={{ height: 300 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无数据</div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default Dashboard;
