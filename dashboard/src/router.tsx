import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from './layouts';
import {
  DashboardPage,
  CasesPage,
  JobsPage,
  JobDetailPage,
  ReportsPage,
  ReportViewerPage,
  SettingsPage,
  PipelinesPage,
  PipelineDetailPage,
  PipelineCreatePage,
  SweepsPage,
  SweepCreatePage,
  SweepDetailPage,
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
      { path: 'reports/:reportId', element: <ReportViewerPage /> },
      { path: 'pipelines', element: <PipelinesPage /> },
      { path: 'pipelines/new', element: <PipelineCreatePage /> },
      { path: 'pipelines/:pipelineId', element: <PipelineDetailPage /> },
      { path: 'sweeps', element: <SweepsPage /> },
      { path: 'sweeps/new', element: <SweepCreatePage /> },
      { path: 'sweeps/:sweepId', element: <SweepDetailPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]);
