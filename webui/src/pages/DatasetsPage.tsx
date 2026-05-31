import { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, message, Popconfirm,
} from 'antd';
import { PlusOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import { datasetsAPI } from '../services/api';
import type { Dataset } from '../types';

function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [filters, setFilters] = useState<{ scene?: string; status?: string }>({});
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const res = await datasetsAPI.list(1, 100, filters);
      setDatasets(res.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载数据集失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, [filters]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const { itemsText, ...rest } = values;
      const payload: Record<string, unknown> = { ...rest };
      if (itemsText && itemsText.trim()) {
        const lines = itemsText.trim().split('\n').filter(Boolean);
        const items = lines.map((line: string) => {
          const parts = line.split('||');
          return { input_text: parts[0]?.trim() || '', expected_output: parts[1]?.trim() || '' };
        });
        payload.items = items;
      }
      await datasetsAPI.create(payload);
      message.success('创建成功');
      setModalOpen(false);
      fetchDatasets();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await datasetsAPI.delete(id);
      message.success('删除成功');
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const handleSubmitReview = async (id: number) => {
    try {
      await datasetsAPI.submitReview(id);
      message.success('已提交审核');
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '提交审核失败');
    }
  };

  const handleReview = async (id: number, status: string) => {
    try {
      await datasetsAPI.review(id, status, '');
      message.success(status === 'approved' ? '已通过审核' : '已驳回');
      fetchDatasets();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '审核操作失败');
    }
  };

  const statusTag = (status: string) => {
    const colorMap: Record<string, string> = {
      draft: 'default',
      pending_review: 'processing',
      approved: 'success',
      rejected: 'error',
    };
    const labelMap: Record<string, string> = {
      draft: '草稿',
      pending_review: '待审核',
      approved: '已通过',
      rejected: '已驳回',
    };
    return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
  };

  const columns: ColumnsType<Dataset> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
    { title: '场景', dataIndex: 'scene', key: 'scene', width: 100, render: (s: string) => <Tag>{s || '-'}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (s: string) => statusTag(s) },
    { title: '条目数', dataIndex: 'item_count', key: 'item_count', width: 80 },
    {
      title: '版本', dataIndex: 'version', key: 'version', width: 80,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_, record) => (
        <Space wrap>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/datasets/${record.id}`)}
          >
            详情
          </Button>
          {record.status === 'draft' && (
            <Button
              type="link"
              onClick={() => handleSubmitReview(record.id)}
            >
              提交审核
            </Button>
          )}
          {record.status === 'pending_review' && (
            <>
              <Button
                type="link"
                style={{ color: '#52c41a' }}
                onClick={() => handleReview(record.id, 'approved')}
              >
                通过
              </Button>
              <Button
                type="link"
                danger
                onClick={() => handleReview(record.id, 'rejected')}
              >
                驳回
              </Button>
            </>
          )}
          <Popconfirm title="确定删除此数据集？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>数据集管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModalOpen(true); }}>
          添加数据集
        </Button>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Space>
          <Select
            placeholder="场景筛选"
            allowClear
            style={{ width: 150 }}
            value={filters.scene}
            onChange={(val) => setFilters((prev) => ({ ...prev, scene: val }))}
          >
            <Select.Option value="chat">Chat</Select.Option>
            <Select.Option value="code">Code</Select.Option>
            <Select.Option value="qa">QA</Select.Option>
            <Select.Option value="multimodal">Multimodal</Select.Option>
          </Select>
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 150 }}
            value={filters.status}
            onChange={(val) => setFilters((prev) => ({ ...prev, status: val }))}
          >
            <Select.Option value="draft">草稿</Select.Option>
            <Select.Option value="pending_review">待审核</Select.Option>
            <Select.Option value="approved">已通过</Select.Option>
            <Select.Option value="rejected">已驳回</Select.Option>
          </Select>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={datasets}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title="添加数据集"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleCreate}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="数据集名称" />
          </Form.Item>
          <Form.Item name="scene" label="场景" rules={[{ required: true, message: '请选择场景' }]}>
            <Select placeholder="选择场景">
              <Select.Option value="chat">Chat</Select.Option>
              <Select.Option value="code">Code</Select.Option>
              <Select.Option value="qa">QA</Select.Option>
              <Select.Option value="multimodal">Multimodal</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="描述（可选）" />
          </Form.Item>
          <Form.Item
            name="itemsText"
            label="数据集条目"
            extra="每行一条，格式: 输入文本||期望输出"
          >
            <Input.TextArea
              rows={8}
              placeholder={'天空是什么颜色的？||天空是蓝色的。\n1+1等于几？||2'}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default DatasetsPage;
