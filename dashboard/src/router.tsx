import { createBrowserRouter } from 'react-router-dom';
import App from './App';
import {
  DashboardPage,
  CasesPage,
  JobsPage,
  ReportsPage,
  SettingsPage,
} from './pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'cases', element: <CasesPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]);
