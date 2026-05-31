import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Table, Descriptions, Statistic, Spin, message, Button } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';
import type { ColumnsType } from 'antd/es/table';
import { reportsAPI } from '../services/api';
import type { EvalReport } from '../types';

function EvalReportPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);

  const distChartRef = useRef<HTMLDivElement>(null);
  const metricChartRef = useRef<HTMLDivElement>(null);
  const itemChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const res = await reportsAPI.evalReport(Number(id));
        setReport(res.data);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        message.error(error?.response?.data?.detail || '加载报告失败');
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [id]);

  useEffect(() => {
    if (!report) return;
    const { charts } = report;

    if (distChartRef.current && charts?.score_distribution?.categories) {
      const chart = echarts.init(distChartRef.current);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: charts.score_distribution.categories },
        yAxis: { type: 'value', name: '数量' },
        series: [{ data: charts.score_distribution.values, type: 'bar', itemStyle: { color: '#1677ff' } }],
      });
      return () => chart.dispose();
    }
  }, [report]);

  useEffect(() => {
    if (!report?.charts?.metric_comparison) return;
    const { metric_comparison: mc } = report.charts;
    if (metricChartRef.current && mc.metrics) {
      const chart = echarts.init(metricChartRef.current);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: mc.metrics },
        yAxis: { type: 'value', name: '平均分', max: 100 },
        series: [{ data: mc.avg_scores, type: 'bar', itemStyle: { color: '#52c41a' } }],
      });
      return () => chart.dispose();
    }
  }, [report]);

  useEffect(() => {
    if (!report?.charts?.item_scores) return;
    const { item_scores: is } = report.charts;
    if (itemChartRef.current && is.ids) {
      const chart = echarts.init(itemChartRef.current);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: is.ids.map((v: number) => `#${v}`) },
        yAxis: { type: 'value', name: '分数' },
        series: [{ data: is.scores, type: 'line', itemStyle: { color: '#faad14' } }],
      });
      return () => chart.dispose();
    }
  }, [report]);

  const itemColumns: ColumnsType<EvalReport['item_details'][number]> = [
    { title: 'ID', dataIndex: 'result_id', key: 'result_id', width: 60 },
    { title: '模型输出', dataIndex: 'model_output', key: 'model_output', width: 250, ellipsis: true },
    { title: '期望输出', dataIndex: 'expected_output', key: 'expected_output', width: 250, ellipsis: true },
    {
      title: '得分', dataIndex: 'avg_score', key: 'avg_score', width: 80,
      render: (v: number) => v != null ? v.toFixed(2) : '-',
    },
    {
      title: '延迟', dataIndex: 'latency_ms', key: 'latency_ms', width: 80,
      render: (v: number) => v != null ? `${v}ms` : '-',
    },
  ];

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  if (!report) {
    return <div style={{ textAlign: 'center', padding: 100 }}>加载报告失败</div>;
  }

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/eval-tasks')} style={{ marginBottom: 16 }}>
        返回
      </Button>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions title={report.task_name} column={3} size="small">
          <Descriptions.Item label="综合得分">
            <Statistic value={report.overall_score != null ? report.overall_score.toFixed(2) : '-'} valueStyle={{ fontSize: 18, color: '#1677ff' }} />
          </Descriptions.Item>
          <Descriptions.Item label="总条目数">{report.total_items}</Descriptions.Item>
          <Descriptions.Item label="状态">{report.status}</Descriptions.Item>
        </Descriptions>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <Card title="得分分布">
          <div ref={distChartRef} style={{ height: 300 }} />
        </Card>
        <Card title="指标对比">
          <div ref={metricChartRef} style={{ height: 300 }} />
        </Card>
      </div>

      <Card title="逐项得分" style={{ marginBottom: 16 }}>
        <div ref={itemChartRef} style={{ height: 300 }} />
      </Card>

      <Card title="评测详情">
        <Table
          columns={itemColumns}
          dataSource={report.item_details || []}
          rowKey="result_id"
          pagination={{ pageSize: 20 }}
          size="small"
        />
      </Card>
    </div>
  );
}

export default EvalReportPage;
