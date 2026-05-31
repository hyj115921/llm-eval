import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

import MainLayout from './components/MainLayout';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import ModelsPage from './pages/ModelsPage';
import DatasetsPage from './pages/DatasetsPage';
import DatasetDetail from './pages/DatasetDetail';
import MetricsPage from './pages/MetricsPage';
import PromptsPage from './pages/PromptsPage';
import PromptOptimization from './pages/PromptOptimization';
import EvalTasksPage from './pages/EvalTasksPage';
import EvalReportPage from './pages/EvalReportPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectDashboard from './pages/ProjectDashboard';
import UsersPage from './pages/UsersPage';
import OptimizationReportPage from './pages/OptimizationReportPage';
import LeaderboardPage from './pages/LeaderboardPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  return (
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#1677ff' } }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<PrivateRoute><MainLayout /></PrivateRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="datasets" element={<DatasetsPage />} />
            <Route path="datasets/:id" element={<DatasetDetail />} />
            <Route path="metrics" element={<MetricsPage />} />
            <Route path="prompts" element={<PromptsPage />} />
            <Route path="prompts/optimization/:id" element={<PromptOptimization />} />
            <Route path="eval-tasks" element={<EvalTasksPage />} />
            <Route path="eval-tasks/:id/report" element={<EvalReportPage />} />
            <Route path="optimization/:id/report" element={<OptimizationReportPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="projects/:id" element={<ProjectDashboard />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="leaderboard" element={<LeaderboardPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
