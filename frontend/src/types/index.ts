export interface BOMItem {
  item_name: string;
  quantity: number;
  unit_price: number;
  unit: string;
  currency: string;
  category: string;
  source?: string;
  date?: string;
  region?: string;
}

export interface LaborItem {
  role_name: string;
  hourly_rate: number;
  hours: number;
  currency: string;
  personnel_count: number;
  notes?: string;
}

export interface CalculationRules {
  overhead_percentage: number;
  contingency_percentage: number;
  tax_percentage: number;
  currency: string;
}

export interface CostBreakdownItem {
  category: string;
  subtotal: number;
  percentage_of_direct: number;
  items_count: number;
}

export interface BaselineCostReport {
  currency: string;
  direct_materials_cost: number;
  direct_labor_cost: number;
  direct_total_cost: number;
  overhead_amount: number;
  overhead_percentage: number;
  subtotal_with_overhead: number;
  contingency_amount: number;
  contingency_percentage: number;
  subtotal_before_tax: number;
  tax_amount: number;
  tax_percentage: number;
  total_project_cost: number;
  breakdown_by_category: Record<string, CostBreakdownItem>;
  traceable_assumptions: string[];
}

export interface MonteCarloSimulationReport {
  iterations: number;
  random_seed: number;
  base_cost: number;
  simulated_mean: number;
  simulated_median_p50: number;
  p10: number;
  p25: number;
  p75: number;
  p90: number;
  std_dev: number;
  currency: string;
  top_cost_drivers: Array<{
    name: string;
    variance_contribution_pct: number;
    std_deviation: number;
  }>;
  confidence_80_range: [number, number];
  simulation_histogram: {
    bins: number[];
    counts: number[];
  };
}

export interface MLPrediction {
  target: string;
  status: string;
  model_version?: string;
  dataset_version?: string;
  algorithm?: string;
  input_snapshot_hash: string;
  prediction?: number;
  interval?: {
    coverage: number;
    low: number;
    expected: number;
    high: number;
  };
  metrics?: Record<string, any>;
  warnings: string[];
  warning?: string;
}

export interface UnifiedEstimateResult {
  project_name: string;
  currency: string;
  baseline_estimate: BaselineCostReport;
  monte_carlo_uncertainty?: MonteCarloSimulationReport;
  ml_prediction?: MLPrediction;
  analogy_estimate?: any;
}

export interface DatasetSummary {
  dataset_id: string;
  name: string;
  domain: string;
  license: string;
  source: string;
  row_count: number;
  column_count: number;
  sha256: string;
  ingestion_timestamp: string;
  columns: string[];
}

export interface ModelItem {
  model_key: string;
  target: string;
  version: string;
  algorithm: string;
  dataset_id: string;
  status: string;
  is_active: boolean;
  sha256: string;
  metrics: Record<string, any>;
  registered_at: string;
}

export interface ModelHealthReport {
  status: string;
  models_available: boolean;
  active_models_count: number;
  active_models: Record<string, string>;
  checksum_verification: Record<string, boolean>;
  offline_capable: boolean;
}

export interface TrainingJob {
  job_id: string;
  dataset_id: string;
  target_column: string;
  status: string;
  progress_percentage: number;
  started_at: string;
  completed_at?: string;
  logs: string[];
  result?: any;
  error?: string;
}
