import { useEffect, useState, useRef } from 'react';
import { Card, Table, Tag, Spin, Empty, Descriptions, Alert } from 'antd';
import { TrophyOutlined, DashboardOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import * as echarts from 'echarts';
import { leaderboardAPI } from '../services/api';

interface ModelEntry {
  rank: number;
  task_id: number;
  model_name: string;
  overall_score: number;
  avg_latency_ms: number;
  total_items: number;
  metric_scores: Record<string, { avg: number; max: number; min: number }>;
  status: string;
}

interface ComparisonData {
  tasks: ModelEntry[];
  best: ModelEntry | null;
  recommendation: string;
  charts: {
    comparison: {
      names: string[];
      scores: number[];
      latencies: number[];
    };
  };
}

function LeaderboardPage() {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const barRef = useRef<HTMLDivElement>(null);
  const radarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    leaderboardAPI.compare()
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!data) return;

    // 柱状图：分数对比
    if (barRef.current) {
      const chart = echarts.init(barRef.current);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['综合得分', '延迟(ms)'] },
        xAxis: { type: 'category', data: data.charts.comparison.names },
        yAxis: [
          { type: 'value', name: '得分', min: 0, max: 1 },
          { type: 'value', name: '延迟(ms)' },
        ],
        series: [
          {
            name: '综合得分', type: 'bar',
            data: data.charts.comparison.scores,
            itemStyle: { color: '#1677ff' },
            label: { show: true, position: 'top', formatter: (p: { value: number }) => p.value.toFixed(2) },
          },
          {
            name: '延迟(ms)', type: 'bar',
            yAxisIndex: 1,
            data: data.charts.comparison.latencies,
            itemStyle: { color: '#ff7875' },
            label: { show: true, position: 'top' },
          },
        ],
      });
      return () => chart.dispose();
    }

    // 雷达图：综合对比
    if (radarRef.current && data.tasks.length > 1) {
      const chart = echarts.init(radarRef.current);
      const metrics = Object.keys(data.tasks[0]?.metric_scores || {});
      chart.setOption({
        tooltip: {},
        legend: { data: data.tasks.map((t) => t.model_name) },
        radar: {
          indicator: metrics.map((m) => ({ name: m.toUpperCase(), max: 1 })),
        },
        series: [{
          type: 'radar',
          data: data.tasks.map((t) => ({
            name: t.model_name,
            value: metrics.map((m) => t.metric_scores[m]?.avg || 0),
          })),
        }],
      });
      return () => chart.dispose();
    }
  }, [data]);

  const columns: ColumnsType<ModelEntry> = [
    {
      title: '排名', dataIndex: 'rank', key: 'rank', width: 60,
      render: (r: number) => {
        const colors = ['#FFD700', '#C0C0C0', '#CD7F32'];
        return <Tag color={r <= 3 ? undefined : 'default'} style={r <= 3 ? { background: colors[r - 1], border: 'none', fontWeight: 'bold' } : {}}>{r}</Tag>;
      },
    },
    { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 160 },
    {
      title: '综合得分', dataIndex: 'overall_score', key: 'overall_score', width: 100,
      render: (v: number) => <strong>{v?.toFixed(3)}</strong>,
    },
    {
      title: '延迟', dataIndex: 'avg_latency_ms', key: 'latency', width: 80,
      render: (v: number) => `${v}ms`,
    },
    {
      title: '样本数', dataIndex: 'total_items', key: 'items', width: 70,
    },
    {
      title: '指标详情', key: 'metrics', width: 300,
      render: (_, r) => (
        <div style={{ fontSize: 12 }}>
          {Object.entries(r.metric_scores || {}).map(([code, s]) => (
            <Tag key={code} color="blue">
              {code}: {(s as { avg: number }).avg?.toFixed(2)}
            </Tag>
          ))}
        </div>
      ),
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />;
  if (!data) return <Empty description="暂无对比数据" />;

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>
        <TrophyOutlined /> 模型选型榜单
      </h2>

      {data.recommendation && (
        <Alert
          type="success"
          message="推荐结论"
          description={data.recommendation}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {data.best && (
        <Card size="small" style={{ marginBottom: 16, background: '#f6ffed' }}>
          <Descriptions title="最佳模型" column={4} size="small">
            <Descriptions.Item label="模型">{data.best.model_name}</Descriptions.Item>
            <Descriptions.Item label="综合得分">{data.best.overall_score?.toFixed(3)}</Descriptions.Item>
            <Descriptions.Item label="平均延迟">{data.best.avg_latency_ms}ms</Descriptions.Item>
            <Descriptions.Item label="级别评级">
              <Tag color="gold">
                {data.best.overall_score >= 0.8 ? 'A级-推荐上线' : data.best.overall_score >= 0.6 ? 'B级-需优化' : 'C级-需改进'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <Card title={<><DashboardOutlined /> 得分与延迟对比</>} style={{ flex: 1, minWidth: 400 }}>
          <div ref={barRef} style={{ height: 300 }} />
        </Card>
        <Card title={<><DashboardOutlined /> 多维度雷达图</>} style={{ flex: 1, minWidth: 400 }}>
          <div ref={radarRef} style={{ height: 300 }} />
        </Card>
      </div>

      <Card title="排行榜">
        <Table
          columns={columns}
          dataSource={data.tasks}
          rowKey="task_id"
          pagination={false}
          size="middle"
        />
      </Card>
    </div>
  );
}

export default LeaderboardPage;
