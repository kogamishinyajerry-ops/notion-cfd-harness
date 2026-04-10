/**
 * JobsPage - Main job monitoring page
 * Displays job queue with real-time updates
 */

import JobQueueView from '../components/JobQueueView';
import type { Job } from '../services/types';

export default function JobsPage() {
  return (
    <div className="page jobs-page">
      <h1>Job Monitoring</h1>
      <p>Monitor simulation jobs with real-time status updates</p>
      <JobQueueView />
    </div>
  );
}
