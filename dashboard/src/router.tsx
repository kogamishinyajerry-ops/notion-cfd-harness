import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from './layouts';
import {
  DashboardPage,
  CasesPage,
  JobsPage,
  JobDetailPage,
  ReportsPage,
  SettingsPage,
} from './pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'cases', element: <CasesPage /> },
      { path: 'cases/new', element: <CasesPage /> },
      { path: 'cases/edit/:caseId', element: <CasesPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'jobs/:jobId', element: <JobDetailPage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]);
