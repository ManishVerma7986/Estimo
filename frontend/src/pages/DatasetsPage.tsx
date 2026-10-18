import React, { useEffect, useState } from 'react';
import { Upload, Trash2, Eye, ShieldAlert, Check, FileCheck } from 'lucide-react';
import { fetchDatasets, uploadDataset, deleteDataset, fetchQualityReport } from '../api/client';
import { DatasetSummary } from '../types';
import { EmptyState } from '../components/EmptyState';

export const DatasetsPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedQuality, setSelectedQuality] = useState<any | null>(null);

  // Upload Form State
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('software');
  const [license, setLicense] = useState('PROMISE Repository Research Use');
  const [source, setSource] = useState('http://promise.site.uottawa.ca/SERepository');
  const [notes, setNotes] = useState('');
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const loadData = () => {
    setLoading(true);
    fetchDatasets()
      .then((data) => {
        setDatasets(data);
        setLoading(false);
      })
      .catch((err) => {
        setErrorMsg(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !name || !license || !source) {
      setErrorMsg('Please provide file, name, license, and source origin (Rule R1).');
      return;
    }

    setUploading(true);
    setErrorMsg('');

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('name', name);
    formData.append('domain', domain);
    formData.append('license', license);
    formData.append('source', source);
    formData.append('notes', notes);

    try {
      await uploadDataset(formData);
      setUploadFile(null);
      setName('');
      setNotes('');
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (datasetId: string) => {
    if (confirm(`Are you sure you want to delete dataset '${datasetId}'?`)) {
      await deleteDataset(datasetId);
      loadData();
      if (selectedQuality?.dataset_id === datasetId) {
        setSelectedQuality(null);
      }
    }
  };

  const viewQuality = async (datasetId: string) => {
    const report = await fetchQualityReport(datasetId);
    setSelectedQuality(report);
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '30px auto', padding: '0 20px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Dataset Registry</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Bring Your Own Dataset (CSV, ARFF, Excel, Parquet). Cryptographic manifests generated on ingestion.
        </p>
      </div>

      {errorMsg && (
        <div style={{ padding: '12px 16px', background: 'var(--danger-bg)', color: 'var(--danger)', borderRadius: 'var(--radius-sm)', marginBottom: '20px' }}>
          {errorMsg}
        </div>
      )}

      {/* Grid: Upload Form + Datasets List */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px', marginBottom: '32px' }}>
        {/* Upload Form */}
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Upload size={18} /> Ingest New Dataset
          </h2>

          <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                Dataset File (.csv, .arff, .xlsx, .parquet) *
              </label>
              <input
                type="file"
                accept=".csv,.arff,.xlsx,.parquet"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                required
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                Dataset Name *
              </label>
              <input
                type="text"
                placeholder="e.g. Desharnais Software Projects"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                  Domain
                </label>
                <select value={domain} onChange={(e) => setDomain(e.target.value)} style={{ width: '100%' }}>
                  <option value="software">Software Projects</option>
                  <option value="building_products">Building Products</option>
                  <option value="custom">Custom Industry</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                  License / Terms *
                </label>
                <input
                  type="text"
                  value={license}
                  onChange={(e) => setLicense(e.target.value)}
                  required
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                Source Origin / URL *
              </label>
              <input
                type="text"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                required
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
                Notes / Methodology
              </label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                style={{ width: '100%' }}
                placeholder="Optional provenance details..."
              />
            </div>

            <button type="submit" disabled={uploading} className="btn-primary" style={{ marginTop: '8px' }}>
              {uploading ? 'Processing & Ingesting...' : 'Ingest Dataset & Generate Manifest'}
            </button>
          </form>
        </div>

        {/* Datasets Table */}
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px' }}>
            Registered Datasets ({datasets.length})
          </h2>

          {datasets.length === 0 ? (
            <EmptyState
              title="No datasets registered"
              message="Upload a dataset on the left or use the CLI to import public benchmarks."
            />
          ) : (
            <div className="table-responsive">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Rows</th>
                    <th>Cols</th>
                    <th>Domain</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((d) => (
                    <tr key={d.dataset_id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{d.name}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          SHA-256: <code>{d.sha256.slice(0, 10)}...</code>
                        </div>
                      </td>
                      <td>{d.row_count}</td>
                      <td>{d.column_count}</td>
                      <td><span className="badge badge-baseline">{d.domain}</span></td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => viewQuality(d.dataset_id)}
                            className="btn-outline"
                            title="View Data Quality Report"
                            style={{ padding: '4px 8px' }}
                          >
                            <Eye size={14} />
                          </button>
                          <button
                            onClick={() => handleDelete(d.dataset_id)}
                            className="btn-outline"
                            title="Delete Dataset"
                            style={{ padding: '4px 8px', color: 'var(--danger)' }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Quality Report Modal / Inspection Panel */}
      {selectedQuality && (
        <div className="card" style={{ marginTop: '24px', border: '2px solid var(--primary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                Data Quality Report: {selectedQuality.name}
              </h2>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                SHA-256: <code>{selectedQuality.sha256}</code>
              </div>
            </div>
            <button onClick={() => setSelectedQuality(null)} className="btn-outline">
              Close Report
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div style={{ padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Rows</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{selectedQuality.row_count}</div>
            </div>
            <div style={{ padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Missing Values</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{selectedQuality.overall_missing_percentage}%</div>
            </div>
            <div style={{ padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Duplicate Rows</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{selectedQuality.duplicate_rows}</div>
            </div>
            <div style={{ padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sample Size Gate</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: selectedQuality.sample_size_adequate ? 'var(--success)' : 'var(--warning)' }}>
                {selectedQuality.sample_size_adequate ? '✓ Adequate for ML' : '⚠ Small (<25)'}
              </div>
            </div>
          </div>

          {selectedQuality.potential_leakage_warnings?.length > 0 && (
            <div style={{ padding: '12px 16px', background: 'var(--warning-bg)', color: 'var(--warning)', borderRadius: 'var(--radius-sm)', marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ShieldAlert size={16} /> Leakage Warnings Detected:
              </div>
              <ul style={{ paddingLeft: '20px', fontSize: '0.85rem', marginTop: '6px' }}>
                {selectedQuality.potential_leakage_warnings.map((w: any, idx: number) => (
                  <li key={idx}><strong>{w.column}:</strong> {w.reason}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
