import React, { useState } from 'react';
import { Calculator, Plus, Trash2, ArrowRight, ShieldCheck, HelpCircle, Layers, Activity } from 'lucide-react';
import { createEstimate } from '../api/client';
import { BOMItem, LaborItem, UnifiedEstimateResult } from '../types';

interface EstimatePageProps {
  currency: string;
}

export const EstimatePage: React.FC<EstimatePageProps> = ({ currency }) => {
  const [projectName, setProjectName] = useState('Smart Building Controller Prototype');

  // BOM items state
  const [bomItems, setBomItems] = useState<BOMItem[]>([
    { item_name: 'Microcontroller Boards', quantity: 15, unit_price: 3200, unit: 'units', currency, category: 'materials' },
    { item_name: 'Environmental Sensors', quantity: 30, unit_price: 850, unit: 'units', currency, category: 'materials' },
    { item_name: 'Cloud Dev Environment (3 months)', quantity: 1, unit_price: 45000, unit: 'license', currency, category: 'software' },
  ]);

  // Labor items state
  const [laborItems, setLaborItems] = useState<LaborItem[]>([
    { role_name: 'Lead Embedded Engineer', hourly_rate: 1800, hours: 120, currency, personnel_count: 1 },
    { role_name: 'Firmware Developer', hourly_rate: 1100, hours: 200, currency, personnel_count: 2 },
    { role_name: 'QA & Compliance Specialist', hourly_rate: 950, hours: 60, currency, personnel_count: 1 },
  ]);

  // Rules state
  const [overheadPct, setOverheadPct] = useState(15.0);
  const [contingencyPct, setContingencyPct] = useState(10.0);
  const [taxPct, setTaxPct] = useState(18.0);

  // ML Features
  const [mlFeatures, setMlFeatures] = useState({
    TeamExp: 3,
    ManagerExp: 4,
    Length: 12,
    Transactions: 250,
    Entities: 90,
    PointsAjust: 320,
  });

  const [result, setResult] = useState<UnifiedEstimateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // BOM handlers
  const addBOMItem = () => {
    setBomItems([
      ...bomItems,
      { item_name: 'New Component', quantity: 1, unit_price: 100, unit: 'units', currency, category: 'materials' },
    ]);
  };

  const removeBOMItem = (index: number) => {
    setBomItems(bomItems.filter((_, i) => i !== index));
  };

  const updateBOMItem = (index: number, field: keyof BOMItem, value: any) => {
    const updated = [...bomItems];
    updated[index] = { ...updated[index], [field]: value };
    setBomItems(updated);
  };

  // Labor handlers
  const addLaborItem = () => {
    setLaborItems([
      ...laborItems,
      { role_name: 'Engineering Role', hourly_rate: 800, hours: 40, currency, personnel_count: 1 },
    ]);
  };

  const removeLaborItem = (index: number) => {
    setLaborItems(laborItems.filter((_, i) => i !== index));
  };

  const updateLaborItem = (index: number, field: keyof LaborItem, value: any) => {
    const updated = [...laborItems];
    updated[index] = { ...updated[index], [field]: value };
    setLaborItems(updated);
  };

  const handleComputeEstimate = async () => {
    setLoading(true);
    setErrorMsg('');

    try {
      const res = await createEstimate({
        project_name: projectName,
        currency,
        bom_items: bomItems,
        labor_items: laborItems,
        rules: {
          overhead_percentage: Number(overheadPct),
          contingency_percentage: Number(contingencyPct),
          tax_percentage: Number(taxPct),
          currency,
        },
        ml_features: mlFeatures,
        target_metric: 'Effort',
        analogy_dataset_id: 'desharnais_software_projects_38c5d000',
      });
      setResult(res);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '30px auto', padding: '0 20px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Cost & Effort Estimation Workspace</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Transparent baseline BOM & labor arithmetic (Rule R1 & R2) combined with Monte Carlo simulation and offline ML.
        </p>
      </div>

      {errorMsg && (
        <div style={{ padding: '12px 16px', background: 'var(--danger-bg)', color: 'var(--danger)', borderRadius: 'var(--radius-sm)', marginBottom: '20px' }}>
          {errorMsg}
        </div>
      )}

      {/* Scope Header */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
              Project Name
            </label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '4px' }}>
              Currency
            </label>
            <input type="text" value={currency} disabled style={{ width: '100%', background: 'var(--bg-surface-elevated)' }} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '4px' }}>
                Overhead %
              </label>
              <input
                type="number"
                value={overheadPct}
                onChange={(e) => setOverheadPct(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '4px' }}>
                Contingency %
              </label>
              <input
                type="number"
                value={contingencyPct}
                onChange={(e) => setContingencyPct(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '4px' }}>
                Tax %
              </label>
              <input
                type="number"
                value={taxPct}
                onChange={(e) => setTaxPct(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Bill of Materials (BOM) */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Bill of Materials, Software & Equipment</h2>
          <button onClick={addBOMItem} className="btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem' }}>
            <Plus size={14} /> Add BOM Item
          </button>
        </div>

        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Item / Material Description</th>
                <th style={{ width: '120px' }}>Quantity</th>
                <th style={{ width: '100px' }}>Unit</th>
                <th style={{ width: '140px' }}>Unit Price ({currency})</th>
                <th style={{ width: '140px' }}>Category</th>
                <th style={{ width: '140px' }}>Subtotal ({currency})</th>
                <th style={{ width: '60px' }}></th>
              </tr>
            </thead>
            <tbody>
              {bomItems.map((item, idx) => (
                <tr key={idx}>
                  <td>
                    <input
                      type="text"
                      value={item.item_name}
                      onChange={(e) => updateBOMItem(idx, 'item_name', e.target.value)}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={item.quantity}
                      onChange={(e) => updateBOMItem(idx, 'quantity', Number(e.target.value))}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={item.unit}
                      onChange={(e) => updateBOMItem(idx, 'unit', e.target.value)}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={item.unit_price}
                      onChange={(e) => updateBOMItem(idx, 'unit_price', Number(e.target.value))}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <select
                      value={item.category}
                      onChange={(e) => updateBOMItem(idx, 'category', e.target.value)}
                      style={{ width: '100%' }}
                    >
                      <option value="materials">Materials</option>
                      <option value="equipment">Equipment</option>
                      <option value="software">Software / Licenses</option>
                      <option value="infrastructure">Infrastructure</option>
                    </select>
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {(item.quantity * item.unit_price).toLocaleString()}
                  </td>
                  <td>
                    <button
                      onClick={() => removeBOMItem(idx)}
                      className="btn-outline"
                      style={{ color: 'var(--danger)', padding: '4px 8px' }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Labor & Personnel */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Personnel, Staffing & Labor Roles</h2>
          <button onClick={addLaborItem} className="btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem' }}>
            <Plus size={14} /> Add Labor Role
          </button>
        </div>

        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Engineering / Operational Role</th>
                <th style={{ width: '140px' }}>Hourly Rate ({currency})</th>
                <th style={{ width: '120px' }}>Hours</th>
                <th style={{ width: '100px' }}>Staff Count</th>
                <th style={{ width: '160px' }}>Subtotal ({currency})</th>
                <th style={{ width: '60px' }}></th>
              </tr>
            </thead>
            <tbody>
              {laborItems.map((item, idx) => (
                <tr key={idx}>
                  <td>
                    <input
                      type="text"
                      value={item.role_name}
                      onChange={(e) => updateLaborItem(idx, 'role_name', e.target.value)}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={item.hourly_rate}
                      onChange={(e) => updateLaborItem(idx, 'hourly_rate', Number(e.target.value))}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={item.hours}
                      onChange={(e) => updateLaborItem(idx, 'hours', Number(e.target.value))}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={item.personnel_count}
                      onChange={(e) => updateLaborItem(idx, 'personnel_count', Number(e.target.value))}
                      style={{ width: '100%' }}
                    />
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {(item.hourly_rate * item.hours * item.personnel_count).toLocaleString()}
                  </td>
                  <td>
                    <button
                      onClick={() => removeLaborItem(idx)}
                      className="btn-outline"
                      style={{ color: 'var(--danger)', padding: '4px 8px' }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action Button */}
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <button
          onClick={handleComputeEstimate}
          disabled={loading}
          className="btn-primary"
          style={{ fontSize: '1.05rem', padding: '12px 36px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <Calculator size={20} />
          {loading ? 'Computing Engine Estimates...' : 'Compute Full Cost & Effort Estimate'}
        </button>
      </div>

      {/* Results View */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '24px' }}>
          {/* Baseline Summary Card */}
          <div className="card">
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '16px' }}>
              Transparent Baseline Summary
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '6px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Direct Materials & Equipment:</span>
                <span style={{ fontWeight: 600 }}>{result.baseline_estimate.direct_materials_cost.toLocaleString()} {currency}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '6px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Direct Labor & Staffing:</span>
                <span style={{ fontWeight: 600 }}>{result.baseline_estimate.direct_labor_cost.toLocaleString()} {currency}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '6px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Overhead ({result.baseline_estimate.overhead_percentage}%):</span>
                <span style={{ fontWeight: 600 }}>{result.baseline_estimate.overhead_amount.toLocaleString()} {currency}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '6px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Contingency Buffer ({result.baseline_estimate.contingency_percentage}%):</span>
                <span style={{ fontWeight: 600 }}>{result.baseline_estimate.contingency_amount.toLocaleString()} {currency}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '6px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Taxes / GST ({result.baseline_estimate.tax_percentage}%):</span>
                <span style={{ fontWeight: 600 }}>{result.baseline_estimate.tax_amount.toLocaleString()} {currency}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '8px', fontSize: '1.2rem', fontWeight: 800, color: 'var(--primary)' }}>
                <span>TOTAL PROJECT COST:</span>
                <span>{result.baseline_estimate.total_project_cost.toLocaleString()} {currency}</span>
              </div>
            </div>

            {/* Traceable assumptions */}
            <div style={{ marginTop: '20px', padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem' }}>
              <div style={{ fontWeight: 600, marginBottom: '6px' }}>Traceable Arithmetic Assumptions:</div>
              <ul style={{ paddingLeft: '18px', color: 'var(--text-secondary)' }}>
                {result.baseline_estimate.traceable_assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Monte Carlo Uncertainty Card */}
          {result.monte_carlo_uncertainty && (
            <div className="card">
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={20} color="var(--primary)" /> Monte Carlo Range (Seed: {result.monte_carlo_uncertainty.random_seed})
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '20px' }}>
                <div style={{ padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Low (P10)</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{result.monte_carlo_uncertainty.p10.toLocaleString()}</div>
                </div>
                <div style={{ padding: '12px', background: 'var(--primary-light)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>Expected (P50)</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--primary)' }}>{result.monte_carlo_uncertainty.simulated_median_p50.toLocaleString()}</div>
                </div>
                <div style={{ padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>High (P90)</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{result.monte_carlo_uncertainty.p90.toLocaleString()}</div>
                </div>
              </div>

              {/* Top sensitivity drivers */}
              <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '8px' }}>
                Top Cost Drivers by Variance Contribution (Sensitivity):
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {result.monte_carlo_uncertainty.top_cost_drivers.slice(0, 4).map((d, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '6px 8px', background: 'var(--bg-surface-elevated)', borderRadius: '4px' }}>
                    <span>{d.name}</span>
                    <span style={{ fontWeight: 600 }}>{d.variance_contribution_pct}% contribution</span>
                  </div>
                ))}
              </div>

              {/* ML Prediction Badge if active */}
              {result.ml_prediction && (
                <div style={{ marginTop: '20px', padding: '12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>ML Predicted Effort ({result.ml_prediction.algorithm}):</span>
                    <span style={{ fontWeight: 700, color: 'var(--primary)' }}>
                      {result.ml_prediction.prediction?.toLocaleString()} person-hours
                    </span>
                  </div>
                  {result.ml_prediction.interval && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      80% interval: [{result.ml_prediction.interval.low.toLocaleString()} - {result.ml_prediction.interval.high.toLocaleString()} hrs]
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
