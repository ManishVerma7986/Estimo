import React, { useEffect, useState } from 'react';
import { Cpu, Play, CheckCircle2, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { fetchDatasets, startTrainingJob, fetchTrainingJobs, fetchJobStatus } from '../api/client';
import { DatasetSummary, TrainingJob } from '../types';
import { EmptyState } from '../components/EmptyState';

export const TrainingPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [targetColumn, setTargetColumn] = useState('Effort');
  const [splitStrategy, setSplitStrategy] = useState('random');
  const [randomSeed, setRandomSeed] = useState(42);

  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<TrainingJob | null>(null);
  const [pastJobs, setPastJobs] = useState<TrainingJob[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    fetchDatasets()
      .then((data) => {
        setDatasets(data);
        if (data.length > 0) {
          setSelectedDataset(data[0].dataset_id);
          // Auto-select Effort or actual if available
          const cand = data[0].columns.find((c) => ['effort', 'actual', 'totallaborcost', 'dev.eff.hrs.'].includes(c.toLowerCase()));
          if (cand) setTargetColumn(cand);
        }
      })
      .catch(() => {});

    fetchTrainingJobs().then(setPastJobs).catch(() => {});
  }, []);

  // Poll active job status
  useEffect(() => {
    if (!activeJobId) return;

    const interval = setInterval(async () => {
      try {
        const st = await fetchJobStatus(activeJobId);
        setActiveJob(st);
        if (st.status === 'COMPLETED' || st.status === 'FAILED' || st.status === 'CANCELLED') {
          clearInterval(interval);
          fetchTrainingJobs().then(setPastJobs);
        }
      } catch (err) {
        clearInterval(interval);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [activeJobId]);

  const handleStartTraining = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDataset || !targetColumn) {
      setErrorMsg('Please select a dataset and target metric.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');

    try {
      const res = await startTrainingJob({
        dataset_id: selectedDataset,
        target_column: targetColumn,
        split_strategy: splitStrategy,
        random_seed: Number(randomSeed),
      });
      setActiveJobId(res.job_id);
      setActiveJob(null);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const selectedDsObj = datasets.find((d) => d.dataset_id === selectedDataset);

  if (datasets.length === 0) {
    return (
      <div style={{ maxWidth: '1000px', margin: '40px auto', padding: '0 20px' }}>
        <EmptyState
          title="No dataset available for training"
          message="You must import a dataset before launching training runs."
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1400px', margin: '30px auto', padding: '0 20px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Model Training Studio</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Train candidate algorithms on your datasets with strict holdout gates (PRED(25) &ge; 30%, MAE &lt; Baseline).
        </p>
      </div>

      {errorMsg && (
        <div style={{ padding: '12px 16px', background: 'var(--danger-bg)', color: 'var(--danger)', borderRadius: 'var(--radius-sm)', marginBottom: '20px' }}>
          {errorMsg}
        </div>
      )}

      {/* Grid: Training Form + Job Status */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px', marginBottom: '32px' }}>
        {/* Form Card */}
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={18} /> Configure Training Job
          </h2>

          <form onSubmit={handleStartTraining} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                Select Dataset
              </label>
              <select
                value={selectedDataset}
                onChange={(e) => {
                  setSelectedDataset(e.target.value);
                  const d = datasets.find((x) => x.dataset_id === e.target.value);
                  if (d && d.columns.length > 0) {
                    setTargetColumn(d.columns[d.columns.length - 1]);
                  }
                }}
                style={{ width: '100%' }}
              >
                {datasets.map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>
                    {d.name} ({d.row_count} rows)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                Target Column (Effort, Cost, Actual)
              </label>
              <select
                value={targetColumn}
                onChange={(e) => setTargetColumn(e.target.value)}
                style={{ width: '100%' }}
              >
                {selectedDsObj?.columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                  Split Strategy
                </label>
                <select value={splitStrategy} onChange={(e) => setSplitStrategy(e.target.value)} style={{ width: '100%' }}>
                  <option value="random">Random Holdout (80/20)</option>
                  <option value="time">Time-based Holdout</option>
                  <option value="group">Group / Project Split</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                  Fixed Random Seed (R4)
                </label>
                <input
                  type="number"
                  value={randomSeed}
                  onChange={(e) => setRandomSeed(Number(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            <button type="submit" disabled={submitting} className="btn-primary" style={{ marginTop: '8px' }}>
              {submitting ? 'Initiating Job...' : 'Launch Training Pipeline'}
            </button>
          </form>
        </div>

        {/* Live Job Monitor */}
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RefreshCw size={18} /> Training Job Monitor
          </h2>

          {!activeJob ? (
            <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              {activeJobId ? 'Waiting for worker status...' : 'Launch a training job to view real-time pipeline execution.'}
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Job ID: <code>{activeJob.job_id}</code></span>
                <span
                  className={`badge ${
                    activeJob.status === 'COMPLETED'
                      ? 'badge-approved'
                      : activeJob.status === 'FAILED'
                      ? 'badge-rejected'
                      : 'badge-experimental'
                  }`}
                >
                  {activeJob.status}
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ width: '100%', height: '8px', background: 'var(--border)', borderRadius: '4px', overflow: 'hidden', marginBottom: '16px' }}>
                <div
                  style={{
                    width: `${activeJob.progress_percentage}%`,
                    height: '100%',
                    background: 'var(--primary)',
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>

              {/* Live Logs */}
              <div
                style={{
                  background: 'var(--bg-primary)',
                  padding: '12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  maxHeight: '180px',
                  overflowY: 'auto',
                }}
              >
                {activeJob.logs.map((log, i) => (
                  <div key={i} style={{ marginBottom: '4px' }}>{log}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results Table for Completed Run */}
      {activeJob?.result && (
        <div className="card" style={{ marginTop: '24px' }}>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '16px' }}>
            Candidate Evaluation Results: {activeJob.result.dataset_id}
          </h2>

          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Algorithm</th>
                  <th>Gate Status</th>
                  <th>MAE</th>
                  <th>PRED(25)</th>
                  <th>MMRE</th>
                  <th>Decision Rationale</th>
                </tr>
              </thead>
              <tbody>
                {activeJob.result.candidates.map((cand: any, idx: number) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600 }}>{cand.algorithm}</td>
                    <td>
                      <span
                        className={`badge ${
                          cand.status === 'APPROVED'
                            ? 'badge-approved'
                            : cand.status === 'EXPERIMENTAL'
                            ? 'badge-experimental'
                            : cand.status === 'BASELINE'
                            ? 'badge-baseline'
                            : 'badge-rejected'
                        }`}
                      >
                        {cand.status}
                      </span>
                    </td>
                    <td>{cand.metrics?.MAE ?? '-'}</td>
                    <td>{cand.metrics?.PRED25 ? `${(cand.metrics.PRED25 * 100).toFixed(1)}%` : '-'}</td>
                    <td>{cand.metrics?.MMRE ?? '-'}</td>
                    <td style={{ fontSize: '0.8rem', color: cand.status === 'REJECTED' ? 'var(--danger)' : 'var(--text-secondary)' }}>
                      {cand.reasons?.length > 0 ? cand.reasons.join('; ') : 'Passed all evaluation gates'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {activeJob.result.saved_model && (
            <div style={{ marginTop: '16px', padding: '12px 16px', background: 'var(--success-bg)', color: 'var(--success)', borderRadius: 'var(--radius-sm)', fontWeight: 600 }}>
              ✓ Model saved & activated on disk: {activeJob.result.saved_model.model_key}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
