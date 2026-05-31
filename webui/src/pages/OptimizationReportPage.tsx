import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Table, Descriptions, Statistic, Row, Col, Spin, message, Button,
} from 'antd';
import { ArrowLeftOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';
import type { ColumnsType } from 'antd/es/table';
import { reportsAPI } from '../services/api';
import type { OptimizationReport } from '../types';

function OptimizationReportPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [loading, setLoading] = useState(true);

  const scoreChartRef = useRef<HTMLDivElement>(null);
  const improvementChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const res = await reportsAPI.optimizationReport(Number(id));
        setReport(res.data);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        message.error(error?.response?.data?.detail || '加载优化报告失败');
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [id]);

  useEffect(() => {
    if (!report?.charts?.score_history) return;
    const sh = report.charts.score_history;
    if (scoreChartRef.current && sh.rounds) {
      const chart = echarts.init(scoreChartRef.current);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: sh.rounds },
        yAxis: { type: 'value', name: '最佳得分' },
        series: [{
          data: sh.scores, type: 'line',
          markLine: {
            silent: true,
            data: [{ yAxis: report.baseline_score, label: { formatter: '基线' } }],
            lineStyle: { type: 'dashed', color: '#ff4d4f' },
          },
        }],
      });
      return () => chart.dispose();
    }
  }, [report]);

  useEffect(() => {
    if (!report?.charts?.improvement_per_round) return;
    const ipr = report.charts.improvement_per_round;
    if (improvementChartRef.current && ipr.rounds) {
      const chart = echarts.init(improvementChartRef.current);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: ipr.rounds.map((r: number) => `第${r}轮`) },
        yAxis: { type: 'value', name: '提升' },
        series: [{
          data: ipr.improvements, type: 'bar',
          itemStyle: {
            color: function (params: { value: number }) {
              return params.value >= 0 ? '#52c41a' : '#ff4d4f';
            },
          },
        }],
      });
      return () => chart.dispose();
    }
  }, [report]);

  const roundColumns: ColumnsType<OptimizationReport['rounds'][number]> = [
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
      title: '提升', dataIndex: 'improvement', key: 'improvement', width: 100,
      render: (v: number) => {
        const color = v >= 0 ? '#52c41a' : '#ff4d4f';
        return <span style={{ color }}>{v >= 0 ? '+' : ''}{v != null ? v.toFixed(4) : '-'}</span>;
      },
    },
    {
      title: '候选数', key: 'candidates', width: 80,
      render: (_, r) => (r.candidates?.length || 0),
    },
  ];

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  if (!report) {
    return <div style={{ textAlign: 'center', padding: 100 }}>加载报告失败</div>;
  }

  const improvement = report.improvement;
  const isPositive = improvement >= 0;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompts')} style={{ marginBottom: 16 }}>
        返回
      </Button>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions title={report.task_name} column={4} size="small">
          <Descriptions.Item label="状态">{report.status}</Descriptions.Item>
          <Descriptions.Item label="总轮次">{report.total_rounds}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="基线得分"
              value={report.baseline_score != null ? report.baseline_score.toFixed(4) : '-'}
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="最佳得分"
              value={report.best_score != null ? report.best_score.toFixed(4) : '-'}
              valueStyle={{ fontSize: 20, color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="总提升"
              value={improvement != null ? improvement.toFixed(4) : '-'}
              prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              valueStyle={{ fontSize: 20, color: isPositive ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <Card title="得分历史">
          <div ref={scoreChartRef} style={{ height: 300 }} />
        </Card>
        <Card title="每轮提升">
          <div ref={improvementChartRef} style={{ height: 300 }} />
        </Card>
      </div>

      <Card title="轮次详情" style={{ marginBottom: 16 }}>
        <Table columns={roundColumns} dataSource={report.rounds || []} rowKey="round_number" pagination={false} size="small" />
      </Card>

      {report.best_prompt && (
        <Card title="最佳Prompt">
          <pre style={{
            background: '#f5f5f5', padding: 16, borderRadius: 8,
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 400, overflow: 'auto',
          }}>
            {report.best_prompt}
          </pre>
        </Card>
      )}
    </div>
  );
}

export default OptimizationReportPage;
