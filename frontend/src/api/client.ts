import {
  BaselineCostReport,
  DatasetSummary,
  ModelHealthReport,
  ModelItem,
  TrainingJob,
  UnifiedEstimateResult,
} from '../types';

const API_BASE = '/api';

export async function fetchHealth(): Promise<ModelHealthReport> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Failed to fetch health status');
  return res.json();
}

export async function fetchDatasets(): Promise<DatasetSummary[]> {
  const res = await fetch(`${API_BASE}/datasets`);
  if (!res.ok) throw new Error('Failed to fetch datasets');
  return res.json();
}

export async function uploadDataset(formData: FormData): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function fetchQualityReport(datasetId: string, target?: string): Promise<any> {
  const url = target
    ? `${API_BASE}/datasets/${datasetId}/quality-report?target=${encodeURIComponent(target)}`
    : `${API_BASE}/datasets/${datasetId}/quality-report`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch quality report');
  return res.json();
}

export async function deleteDataset(datasetId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets/${datasetId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete dataset');
  return res.json();
}

export async function fetchModels(): Promise<ModelItem[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) throw new Error('Failed to fetch models');
  return res.json();
}

export async function activateModel(target: string, version: string): Promise<any> {
  const res = await fetch(`${API_BASE}/models/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target, version }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Activation failed' }));
    throw new Error(err.detail || 'Activation failed');
  }
  return res.json();
}

export async function rollbackModel(target: string): Promise<any> {
  const res = await fetch(`${API_BASE}/models/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Rollback failed' }));
    throw new Error(err.detail || 'Rollback failed');
  }
  return res.json();
}

export async function verifyModels(): Promise<Record<string, boolean>> {
  const res = await fetch(`${API_BASE}/models/verify`);
  if (!res.ok) throw new Error('Failed to verify models');
  return res.json();
}

export async function startTrainingJob(payload: {
  dataset_id: string;
  target_column: string;
  split_strategy?: string;
  random_seed?: number;
}): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/training/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to start training job');
  return res.json();
}

export async function fetchTrainingJobs(): Promise<TrainingJob[]> {
  const res = await fetch(`${API_BASE}/training/jobs`);
  if (!res.ok) throw new Error('Failed to fetch training jobs');
  return res.json();
}

export async function fetchJobStatus(jobId: string): Promise<TrainingJob> {
  const res = await fetch(`${API_BASE}/training/jobs/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch job status');
  return res.json();
}

export async function createEstimate(payload: any): Promise<UnifiedEstimateResult> {
  const res = await fetch(`${API_BASE}/estimates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Estimation failed' }));
    throw new Error(err.detail || 'Estimation failed');
  }
  return res.json();
}

export async function fetchEstimateHistory(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/estimates/history`);
  if (!res.ok) throw new Error('Failed to fetch estimate history');
  return res.json();
}

export async function compareScenarios(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/scenarios/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to compare scenarios');
  return res.json();
}
