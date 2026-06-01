import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, message, Card, Descriptions, Spin, Popconfirm,
} from 'antd';
import { PlusOutlined, DeleteOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { datasetsAPI } from '../services/api';
import type { Dataset, DatasetItem } from '../types';

function DatasetDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [items, setItems] = useState<DatasetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [importForm] = Form.useForm();

  const fetchData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [dsRes, itemsRes] = await Promise.all([
        datasetsAPI.get(Number(id)),
        datasetsAPI.items(Number(id), 1, 100),
      ]);
      setDataset(dsRes.data);
      setItems(itemsRes.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载数据集失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleAddItem = async () => {
    try {
      const values = await form.validateFields();
      await datasetsAPI.addItems(Number(id), [values]);
      message.success('添加成功');
      setModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '添加失败');
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    try {
      await datasetsAPI.deleteItem(Number(id), itemId);
      message.success('删除成功');
      fetchData();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const handleImport = async () => {
    try {
      const values = await importForm.validateFields();
      const { importText } = values;
      if (!importText?.trim()) {
        message.warning('请输入数据');
        return;
      }
      let parsedItems: Array<{ input_text: string; expected_output: string }> = [];
      try {
        const json = JSON.parse(importText);
        if (Array.isArray(json)) {
          parsedItems = json;
        } else {
          message.error('JSON格式错误，需要数组');
          return;
        }
      } catch {
        const lines = importText.trim().split('\n').filter(Boolean);
        parsedItems = lines.map((line: string) => {
          const parts = line.split('||');
          return { input_text: parts[0]?.trim() || '', expected_output: parts[1]?.trim() || '' };
        });
      }
      await datasetsAPI.addItems(Number(id), parsedItems);
      message.success(`成功导入 ${parsedItems.length} 条数据`);
      setImportModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '导入失败');
    }
  };

  const columns: ColumnsType<DatasetItem> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '输入文本', dataIndex: 'input_text', key: 'input_text', width: 250, ellipsis: true },
    { title: '期望输出', dataIndex: 'expected_output', key: 'expected_output', width: 250, ellipsis: true },
    {
      title: '难度', dataIndex: 'difficulty', key: 'difficulty', width: 80,
      render: (v: string) => {
        const colorMap: Record<string, string> = { easy: 'green', medium: 'orange', hard: 'red' };
        return <Tag color={colorMap[v] || 'default'}>{v || '-'}</Tag>;
      },
    },
    { title: '场景标签', dataIndex: 'scene_label', key: 'scene_label', width: 100, render: (v: string) => <Tag>{v || '-'}</Tag> },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_, record) => (
        <Popconfirm title="确定删除？" onConfirm={() => handleDeleteItem(record.id)}>
          <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/datasets')} style={{ marginBottom: 16 }}>
          返回列表
        </Button>
      </div>

      {dataset && (
        <Card style={{ marginBottom: 16 }}>
          <Descriptions title={dataset.name} column={3} size="small">
            <Descriptions.Item label="场景">{dataset.scene}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={dataset.status === 'approved' ? 'green' : 'default'}>{dataset.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="条目数">{dataset.item_count}</Descriptions.Item>
            <Descriptions.Item label="版本">{dataset.version}</Descriptions.Item>
            <Descriptions.Item label="描述">{dataset.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {dataset.created_at ? new Date(dataset.created_at).toLocaleString() : '-'}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>数据集条目</h3>
        <Space>
          <Button onClick={() => { form.resetFields(); setModalOpen(true); }} icon={<PlusOutlined />}>
            添加条目
          </Button>
          <Button onClick={() => { importForm.resetFields(); setImportModalOpen(true); }}>
            批量导入
          </Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title="添加条目"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleAddItem}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="input_text" label="输入文本" rules={[{ required: true, message: '请输入' }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="expected_output" label="期望输出" rules={[{ required: true, message: '请输入' }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="difficulty" label="难度" initialValue="medium">
            <Select>
              <Select.Option value="easy">简单</Select.Option>
              <Select.Option value="medium">中等</Select.Option>
              <Select.Option value="hard">困难</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量导入数据"
        open={importModalOpen}
        onCancel={() => setImportModalOpen(false)}
        onOk={handleImport}
        width={700}
        destroyOnClose
      >
        <Form form={importForm} layout="vertical" preserve={false}>
          <Form.Item
            name="importText"
            label="数据内容"
            extra="支持JSON数组格式，或每行一条的格式: 输入文本||期望输出"
          >
            <Input.TextArea
              rows={12}
              placeholder={'[\n  {"input_text": "你好", "expected_output": "你好！有什么可以帮你的？"}\n]\n\n或\n\n你好||你好！有什么可以帮你的？'}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default DatasetDetail;
