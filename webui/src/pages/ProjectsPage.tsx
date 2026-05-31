import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, message, Popconfirm,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { projectsAPI } from '../services/api';
import type { Project } from '../types';

function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [form] = Form.useForm();

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const res = await projectsAPI.list(1, 100);
      setProjects(res.data.items || []);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '加载项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const openCreateModal = () => {
    setEditingProject(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (project: Project) => {
    setEditingProject(project);
    form.setFieldsValue(project);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await projectsAPI.delete(id);
      message.success('删除成功');
      fetchProjects();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingProject) {
        await projectsAPI.update(editingProject.id, values);
        message.success('更新成功');
      } else {
        await projectsAPI.create(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchProjects();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '操作失败');
    }
  };

  const statusTag = (status: string) => {
    const colorMap: Record<string, string> = {
      active: 'green', inactive: 'default', archived: 'warning',
    };
    const labelMap: Record<string, string> = {
      active: '活跃', inactive: '未激活', archived: '已归档',
    };
    return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
  };

  const typeTag = (ptype: string) => {
    const colorMap: Record<string, string> = {
      chat: 'blue', multimodal: 'purple', code: 'orange',
    };
    return <Tag color={colorMap[ptype] || 'default'}>{ptype || '-'}</Tag>;
  };

  const columns: ColumnsType<Project> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
    { title: '类型', dataIndex: 'project_type', key: 'project_type', width: 120, render: (t: string) => typeTag(t) },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (s: string) => statusTag(s) },
    { title: '描述', dataIndex: 'description', key: 'description', width: 200, ellipsis: true },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '操作', key: 'actions', width: 220,
      render: (_, record) => (
        <Space>
          <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/projects/${record.id}`)}>
            详情
          </Button>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>项目管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          创建项目
        </Button>
      </div>

      <Table columns={columns} dataSource={projects} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />

      <Modal
        title={editingProject ? '编辑项目' : '创建项目'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={500}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="项目名称" />
          </Form.Item>
          <Form.Item name="project_type" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select placeholder="选择项目类型">
              <Select.Option value="chat">对话 (Chat)</Select.Option>
              <Select.Option value="multimodal">多模态 (Multimodal)</Select.Option>
              <Select.Option value="code">代码 (Code)</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="项目描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default ProjectsPage;
