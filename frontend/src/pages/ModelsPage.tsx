import React, { useEffect, useState } from 'react';
import { Layers, ShieldCheck, RotateCcw, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { fetchModels, activateModel, rollbackModel, verifyModels } from '../api/client';
import { ModelItem } from '../types';
import { EmptyState } from '../components/EmptyState';

export const ModelsPage: React.FC = () => {
  const [models, setModels] = useState<ModelItem[]>([]);
  const [verifications, setVerifications] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadData = () => {
    setLoading(true);
    Promise.all([fetchModels(), verifyModels()])
      .then(([m, v]) => {
        setModels(m);
        setVerifications(v);
        setLoading(false);
      })
      .catch((err) => {
        setActionMsg({ type: 'error', text: err.message });
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleActivate = async (target: string, version: string) => {
    try {
      await activateModel(target, version);
      setActionMsg({ type: 'success', text: `Activated version '${version}' for target '${target}'.` });
      loadData();
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.message });
    }
  };

  const handleRollback = async (target: string) => {
    try {
      const res = await rollbackModel(target);
      setActionMsg({ type: 'success', text: res.message });
      loadData();
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.message });
    }
  };

  const handleVerify = async () => {
    try {
      const v = await verifyModels();
      setVerifications(v);
      setActionMsg({ type: 'success', text: 'All disk model artifacts verified against signed SHA-256 manifests.' });
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.message });
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center' }}>Loading model registry...</div>;
  }

  if (models.length === 0) {
    return (
      <div style={{ maxWidth: '1000px', margin: '40px auto', padding: '0 20px' }}>
        <EmptyState
          title="No models registered"
          message="No trained models currently exist on disk. Train a model from the Training studio."
        />
      </div>
    );
  }

  // Group models by target
  const targets = Array.from(new Set(models.map((m) => m.target)));

  return (
    <div style={{ maxWidth: '1400px', margin: '30px auto', padding: '0 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Model Registry & Governance</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Versioned offline artifacts on disk with cryptographic tamper verification (Rule R6).
          </p>
        </div>
        <button onClick={handleVerify} className="btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <ShieldCheck size={16} /> Verify Disk Checksums
        </button>
      </div>

      {actionMsg && (
        <div
          style={{
            padding: '12px 16px',
            background: actionMsg.type === 'success' ? 'var(--success-bg)' : 'var(--danger-bg)',
            color: actionMsg.type === 'success' ? 'var(--success)' : 'var(--danger)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          {actionMsg.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          {actionMsg.text}
        </div>
      )}

      {targets.map((tgt) => {
        const targetModels = models.filter((m) => m.target === tgt);
        const activeModel = targetModels.find((m) => m.is_active);

        return (
          <div key={tgt} className="card" style={{ marginBottom: '28px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                  Target Metric: <code>{tgt}</code>
                </h2>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Currently Active: {activeModel ? <strong>{activeModel.algorithm} ({activeModel.version})</strong> : 'None'}
                </div>
              </div>

              <button
                onClick={() => handleRollback(tgt)}
                className="btn-outline"
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
              >
                <RotateCcw size={15} /> Rollback to Previous Version
              </button>
            </div>

            <div className="table-responsive">
              <table>
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Algorithm</th>
                    <th>Version</th>
                    <th>Held-Out MAE</th>
                    <th>PRED(25)</th>
                    <th>MMRE</th>
                    <th>SHA-256 Integrity</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {targetModels.map((m) => {
                    const isIntegrityOk = verifications[m.model_key] !== false;
                    return (
                      <tr key={m.model_key} style={{ background: m.is_active ? 'var(--primary-light)' : 'transparent' }}>
                        <td>
                          {m.is_active ? (
                            <span className="badge badge-approved">ACTIVE</span>
                          ) : (
                            <span className="badge badge-baseline">ARCHIVED</span>
                          )}
                        </td>
                        <td style={{ fontWeight: 600 }}>{m.algorithm}</td>
                        <td><code>{m.version}</code></td>
                        <td>{m.metrics?.MAE ?? '-'}</td>
                        <td>{m.metrics?.PRED25 ? `${(m.metrics.PRED25 * 100).toFixed(1)}%` : '-'}</td>
                        <td>{m.metrics?.MMRE ?? '-'}</td>
                        <td>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.75rem',
                              color: isIntegrityOk ? 'var(--success)' : 'var(--danger)',
                              fontWeight: 600,
                            }}
                          >
                            <ShieldCheck size={14} />
                            {isIntegrityOk ? 'VALID (MATCH)' : 'CORRUPT!'}
                          </span>
                        </td>
                        <td>
                          {!m.is_active && (
                            <button
                              onClick={() => handleActivate(m.target, m.version)}
                              className="btn-primary"
                              style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                            >
                              Activate
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
};
