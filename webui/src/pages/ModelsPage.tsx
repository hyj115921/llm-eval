import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, Space, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ApiOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { modelsAPI } from '../services/api';
import type { LLMModel } from '../types';

function ModelsPage() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [form] = Form.useForm();
  const [pingResult, setPingResult] = useState<Record<number, string>>({});

  const fetchModels = async () => {
    setLoading(true);
    try {
      const res = await modelsAPI.list(1, 100);
      setModels(res.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '获取模型列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const openCreateModal = () => {
    setEditingModel(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (model: LLMModel) => {
    setEditingModel(model);
    form.setFieldsValue(model);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await modelsAPI.delete(id);
      message.success('删除成功');
      fetchModels();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const handlePing = async (id: number) => {
    try {
      const res = await modelsAPI.ping(id);
      setPingResult((prev) => ({ ...prev, [id]: res.data?.message || '连接成功' }));
      message.success('连接测试成功');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      const errMsg = error?.response?.data?.detail || '连接失败';
      setPingResult((prev) => ({ ...prev, [id]: errMsg }));
      message.error('连接测试失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingModel) {
        await modelsAPI.update(editingModel.id, values);
        message.success('更新成功');
      } else {
        await modelsAPI.create(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchModels();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const columns: ColumnsType<LLMModel> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '提供商', dataIndex: 'provider', key: 'provider', width: 100 },
    {
      title: '模型类型',
      dataIndex: 'model_type',
      key: 'model_type',
      width: 100,
      render: (t: string) => <Tag>{t || '-'}</Tag>,
    },
    { title: '模型标识符', dataIndex: 'model_identifier', key: 'model_identifier', width: 150 },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => (
        <Tag color={v ? 'green' : 'red'}>{v ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '连接测试',
      key: 'ping',
      width: 120,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<ApiOutlined />} onClick={() => handlePing(record.id)}>
            测试
          </Button>
          {pingResult[record.id] && (
            <Tag color={pingResult[record.id].includes('成功') ? 'green' : 'red'}>
              {pingResult[record.id].length > 10
                ? pingResult[record.id].substring(0, 10) + '...'
                : pingResult[record.id]}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            编辑
          </Button>
          <Popconfirm title="确定删除此模型？" onConfirm={() => handleDelete(record.id)}>
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
        <h2 style={{ margin: 0 }}>模型管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          添加模型
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={models}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={editingModel ? '编辑模型' : '添加模型'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如: GPT-4o" />
          </Form.Item>
          <Form.Item name="provider" label="提供商" rules={[{ required: true, message: '请输入提供商' }]}>
            <Input placeholder="例如: OpenAI" />
          </Form.Item>
          <Form.Item
            name="model_type"
            label="模型类型"
            rules={[{ required: true, message: '请选择模型类型' }]}
          >
            <Select placeholder="选择模型类型">
              <Select.Option value="chat">对话 (Chat)</Select.Option>
              <Select.Option value="completion">补全 (Completion)</Select.Option>
              <Select.Option value="embedding">嵌入 (Embedding)</Select.Option>
              <Select.Option value="multimodal">多模态 (Multimodal)</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="api_base" label="API Base URL" rules={[{ required: true, message: '请输入API地址' }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="API密钥" />
          </Form.Item>
          <Form.Item
            name="model_identifier"
            label="模型标识符"
            rules={[{ required: true, message: '请输入模型标识符' }]}
          >
            <Input placeholder="例如: gpt-4o" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="模型描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default ModelsPage;
