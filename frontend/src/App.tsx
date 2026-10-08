import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/Dashboard/DashboardPage';
import MaterialsListPage from './pages/Materials/MaterialsListPage';
import MaterialDetailPage from './pages/Materials/MaterialDetailPage';
import MaterialFormPage from './pages/Materials/MaterialFormPage';
import UserManagementPage from './pages/Users/UserManagementPage';
import SearchPage from './pages/Search/SearchPage';
import DataImportPage from './pages/DataImport/DataImportPage';
import CollectionsPage from './pages/Collections/CollectionsPage';
import AuditLogPage from './pages/Audit/AuditLogPage';
import ProjectsPage from './pages/Projects/ProjectsPage';
import ProjectDetailPage from './pages/Projects/ProjectDetailPage';
import VisualizationPage from './pages/Visualization/VisualizationPage';
import MeasurementDatasetPage from './pages/MeasurementDatasets/MeasurementDatasetPage';
import AIAssistantPage from './pages/Assistant/AIAssistantPage';
import ProtectedRoute from './components/auth/ProtectedRoute';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="assistant" element={<AIAssistantPage />} />
          <Route path="materials" element={<MaterialsListPage />} />
          <Route path="materials/new" element={<MaterialFormPage />} />
          <Route path="materials/:id" element={<MaterialDetailPage />} />
          <Route path="materials/:id/edit" element={<MaterialFormPage />} />
          <Route path="visualizations" element={<VisualizationPage />} />
          <Route path="measurement-datasets/:id" element={<MeasurementDatasetPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="import" element={<DataImportPage />} />
          <Route path="collections" element={<CollectionsPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:id" element={<ProjectDetailPage />} />
          <Route path="audit-logs" element={<AuditLogPage />} />
          <Route path="users" element={<UserManagementPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
