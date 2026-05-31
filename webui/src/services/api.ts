import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

const API_BASE = '/api/v1';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Request interceptor - add auth token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ---- Auth ----
export const authAPI = {
  login: (data: { username: string; password: string }) => api.post('/auth/login', data),
  register: (data: { username: string; password: string; email?: string; display_name?: string }) =>
    api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
};

// ---- Users ----
export const usersAPI = {
  list: (page = 1, pageSize = 20) => api.get('/users/', { params: { page, page_size: pageSize } }),
  get: (id: number) => api.get(`/users/${id}`),
  create: (data: any) => api.post('/users/', data),
  update: (id: number, data: any) => api.put(`/users/${id}`, data),
  delete: (id: number) => api.delete(`/users/${id}`),
};

// ---- Models ----
export const modelsAPI = {
  list: (page = 1, pageSize = 20) => api.get('/models/', { params: { page, page_size: pageSize } }),
  get: (id: number) => api.get(`/models/${id}`),
  create: (data: any) => api.post('/models/', data),
  update: (id: number, data: any) => api.put(`/models/${id}`, data),
  delete: (id: number) => api.delete(`/models/${id}`),
  ping: (id: number) => api.post(`/models/${id}/ping`),
};

// ---- Datasets ----
export const datasetsAPI = {
  list: (page = 1, pageSize = 20, filters?: { scene?: string; status?: string }) =>
    api.get('/datasets/', { params: { page, page_size: pageSize, ...filters } }),
  get: (id: number) => api.get(`/datasets/${id}`),
  create: (data: any) => api.post('/datasets/', data),
  update: (id: number, data: any) => api.put(`/datasets/${id}`, data),
  delete: (id: number) => api.delete(`/datasets/${id}`),
  submitReview: (id: number) => api.post(`/datasets/${id}/submit-review`),
  review: (id: number, status: string, comment: string) =>
    api.post(`/datasets/${id}/review`, { status, comment }),
  items: (id: number, page = 1, pageSize = 50) =>
    api.get(`/datasets/${id}/items`, { params: { page, page_size: pageSize } }),
  addItems: (id: number, items: any[]) => api.post(`/datasets/${id}/items`, items),
  deleteItem: (datasetId: number, itemId: number) =>
    api.delete(`/datasets/${datasetId}/items/${itemId}`),
};

// ---- Metrics ----
export const metricsAPI = {
  list: (page = 1, pageSize = 20) => api.get('/metrics/', { params: { page, page_size: pageSize } }),
  get: (id: number) => api.get(`/metrics/${id}`),
  create: (data: any) => api.post('/metrics/', data),
  update: (id: number, data: any) => api.put(`/metrics/${id}`, data),
  delete: (id: number) => api.delete(`/metrics/${id}`),
  submitReview: (id: number) => api.post(`/metrics/${id}/submit-review`),
  review: (id: number, status: string, comment: string) =>
    api.post(`/metrics/${id}/review`, { status, comment }),
};

// ---- Evals ----
export const evalsAPI = {
  list: (page = 1, pageSize = 20, filters?: { status?: string; project_id?: number }) =>
    api.get('/evals/', { params: { page, page_size: pageSize, ...filters } }),
  get: (id: number) => api.get(`/evals/${id}`),
  create: (data: any) => api.post('/evals/', data),
  start: (id: number) => api.post(`/evals/${id}/start`),
  cancel: (id: number) => api.post(`/evals/${id}/cancel`),
  results: (id: number, page = 1, pageSize = 50) =>
    api.get(`/evals/${id}/results`, { params: { page, page_size: pageSize } }),
};

// ---- Prompts ----
export const promptsAPI = {
  list: (page = 1, pageSize = 20) => api.get('/prompts/', { params: { page, page_size: pageSize } }),
  get: (id: number) => api.get(`/prompts/${id}`),
  create: (data: any) => api.post('/prompts/', data),
  update: (id: number, data: any) => api.put(`/prompts/${id}`, data),
  delete: (id: number) => api.delete(`/prompts/${id}`),
  versions: (id: number) => api.get(`/prompts/${id}/versions`),
  createOptimization: (data: any) => api.post('/prompts/optimization', data),
  getOptimization: (id: number) => api.get(`/prompts/optimization/${id}`),
  startOptimization: (id: number) => api.post(`/prompts/optimization/${id}/start`),
  cancelOptimization: (id: number) => api.post(`/prompts/optimization/${id}/cancel`),
  optimizationRounds: (id: number) => api.get(`/prompts/optimization/${id}/rounds`),
  listOptimization: (page = 1, pageSize = 100, filters?: { status?: string }) =>
    api.get('/prompts/optimization', { params: { page, page_size: pageSize, ...filters } }),
};

// ---- Projects ----
export const projectsAPI = {
  list: (page = 1, pageSize = 20, filters?: { project_type?: string }) =>
    api.get('/projects/', { params: { page, page_size: pageSize, ...filters } }),
  get: (id: number) => api.get(`/projects/${id}`),
  create: (data: any) => api.post('/projects/', data),
  update: (id: number, data: any) => api.put(`/projects/${id}`, data),
  delete: (id: number) => api.delete(`/projects/${id}`),
  dashboard: (id: number) => api.get(`/projects/${id}/dashboard`),
};

// ---- Reports ----
export const reportsAPI = {
  evalReport: (taskId: number) => api.get(`/reports/eval/${taskId}`),
  exportEvalReport: (taskId: number) => api.get(`/reports/eval/${taskId}/export`),
  optimizationReport: (taskId: number) => api.get(`/reports/optimization/${taskId}`),
};

// ---- Leaderboard ----
export const leaderboardAPI = {
  compare: (filters?: { dataset_id?: number; model_ids?: string }) =>
    api.get('/reports/comparison', { params: { ...filters } }),
};

export default api;
