import React, { useState } from 'react';
import { GitCompare, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';
import { compareScenarios } from '../api/client';

interface ScenariosPageProps {
  currency: string;
}

export const ScenariosPage: React.FC<ScenariosPageProps> = ({ currency }) => {
  const [laborMultiplier, setLaborMultiplier] = useState(1.15); // +15%
  const [bomPriceMultiplier, setBomPriceMultiplier] = useState(1.10); // +10%
  const [contingencyOverride, setContingencyOverride] = useState(15.0); // 15%

  const [comparisonResult, setComparisonResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const runComparison = async () => {
    setLoading(true);

    const baseProject = {
      project_name: 'Scenario Reference Model',
      currency,
      bom_items: [
        { item_name: 'Key Hardware Components', quantity: 20, unit_price: 5000, unit: 'units', currency, category: 'materials' },
        { item_name: 'Software Tools & Toolchains', quantity: 2, unit_price: 30000, unit: 'license', currency, category: 'software' },
      ],
      labor_items: [
        { role_name: 'Core Engineering Team', hourly_rate: 1500, hours: 240, currency, personnel_count: 2 },
      ],
      rules: {
        overhead_percentage: 15.0,
        contingency_percentage: 10.0,
        tax_percentage: 18.0,
        currency,
      },
    };

    const variations = {
      'Labor Rate Surge (+15%)': { labor_rate_multiplier: Number(laborMultiplier) },
      'Supply Chain Material Spike (+10%)': { bom_price_multiplier: Number(bomPriceMultiplier) },
      'High Uncertainty Buffer (15% Contingency)': { contingency_percentage: Number(contingencyOverride) },
      'Combined Worst Case': {
        labor_rate_multiplier: Number(laborMultiplier),
        bom_price_multiplier: Number(bomPriceMultiplier),
        contingency_percentage: Number(contingencyOverride),
      },
    };

    try {
      const res = await compareScenarios({ base_project: baseProject, what_if_scenarios: variations });
      setComparisonResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '30px auto', padding: '0 20px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>What-If Scenario Planner</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Simulate labor rate shocks, supply chain material spikes, and risk buffers side-by-side.
        </p>
      </div>

      {/* Configuration Card */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', alignItems: 'end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>
              Labor Rate Shock Multiplier (e.g. 1.15 = +15%)
            </label>
            <input
              type="number"
              step="0.05"
              value={laborMultiplier}
              onChange={(e) => setLaborMultiplier(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>
              Material Price Inflation (e.g. 1.10 = +10%)
            </label>
            <input
              type="number"
              step="0.05"
              value={bomPriceMultiplier}
              onChange={(e) => setBomPriceMultiplier(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>
              High-Risk Contingency Target (%)
            </label>
            <input
              type="number"
              value={contingencyOverride}
              onChange={(e) => setContingencyOverride(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <button
              onClick={runComparison}
              disabled={loading}
              className="btn-primary"
              style={{ width: '100%', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
            >
              <RefreshCw size={16} />
              {loading ? 'Evaluating Scenarios...' : 'Evaluate What-If Matrix'}
            </button>
          </div>
        </div>
      </div>

      {/* Comparison Results */}
      {comparisonResult && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              Scenario Comparison Matrix
            </h2>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Baseline Cost: <strong>{comparisonResult.baseline_scenario.total_project_cost?.toLocaleString()} {currency}</strong>
            </div>
          </div>

          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Scenario Name</th>
                  <th>Simulated Total ({currency})</th>
                  <th>Cost Delta vs Baseline ({currency})</th>
                  <th>Impact (%)</th>
                  <th>Sensitivity Classification</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ background: 'var(--bg-surface-elevated)' }}>
                  <td style={{ fontWeight: 700 }}>Baseline Reference</td>
                  <td style={{ fontWeight: 700 }}>{comparisonResult.baseline_scenario.total_project_cost?.toLocaleString()}</td>
                  <td>-</td>
                  <td>0.0%</td>
                  <td><span className="badge badge-baseline">REFERENCE</span></td>
                </tr>
                {comparisonResult.scenarios.map((sc: any, idx: number) => {
                  const isIncrease = sc.cost_difference_vs_baseline > 0;
                  return (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600 }}>{sc.scenario_name}</td>
                      <td>{sc.total_cost?.toLocaleString()}</td>
                      <td style={{ color: isIncrease ? 'var(--danger)' : 'var(--success)', fontWeight: 600 }}>
                        {isIncrease ? '+' : ''}{sc.cost_difference_vs_baseline?.toLocaleString()}
                      </td>
                      <td style={{ fontWeight: 700 }}>
                        {isIncrease ? <TrendingUp size={14} style={{ display: 'inline', marginRight: '4px' }} /> : <TrendingDown size={14} style={{ display: 'inline', marginRight: '4px' }} />}
                        {sc.percentage_change}%
                      </td>
                      <td>
                        <span className={`badge ${Math.abs(sc.percentage_change) > 10 ? 'badge-rejected' : 'badge-experimental'}`}>
                          {Math.abs(sc.percentage_change) > 10 ? 'HIGH SENSITIVITY' : 'MODERATE SENSITIVITY'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
