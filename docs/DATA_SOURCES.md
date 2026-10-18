# Data Sources & Provenance Documentation

All datasets bundled in the `dataset/` directory originate from the **PROMISE Software Engineering Repository** (or documented public engineering benchmarks) made publicly available for repeatable, verifiable, and refutable predictive modeling.

## Policy & Non-Negotiable Integrity Rules
1. **NO DUMMY DATA:** No faker libraries, random number generators, fabricated rows, or synthetic figures are used.
2. **Honest Empty State:** When first started without imported data, the application displays:
   `"No dataset loaded. Import a dataset to begin."`
3. **Traceability:** Every dataset has a cryptographic SHA-256 digest recorded in its manifest (`data/manifests/<dataset_id>.json`).

---

## Bundled PROMISE Software Engineering Datasets

| Dataset | Format | Rows | Features | Target Column | Target Unit | Domain | License / Terms |
|---------|--------|------|----------|---------------|-------------|--------|-----------------|
| **Albrecht** | ARFF | 24 | 7 | `Effort` | person-months | MIS / Function Points | PROMISE Repository / Research Use |
| **China** | ARFF | 499 | 17 | `Effort` | person-hours | Function Points | PROMISE Repository / Research Use |
| **COCOMO-81** | CSV | 63 | 17 | `actual` | person-months | Embedded/Organic Systems | Boehm COCOMO / Public Domain |
| **Desharnais** | CSV | 81 | 11 | `Effort` | person-hours | MIS / Traditional Projects | PROMISE Repository / Research Use |
| **Finnish** | ARFF | 38 | 6 | `dev.eff.hrs.` | person-hours | Function Points | PROMISE Repository / Research Use |
| **Kitchenham** | ARFF | 145 | 7 | `Actual.effort` | person-hours | Industrial Maintenance & Enhancements | Kitchenham et al. / Research Use |
| **Maxwell** | ARFF | 62 | 25 | `Effort` | person-hours | Telecom / Space Products | PROMISE Repository / Research Use |
| **Miyazaki94** | ARFF | 48 | 7 | `MM` | person-months | Fujitsu Business Systems | Miyazaki et al. / Research Use |
| **NASA93** | ARFF | 93 | 22 | `act_effort` | person-months | Aerospace / Ground Systems | NASA / PROMISE Repository |
| **Renzo-Pomodoro** | CSV | 10,661 | 5 | `actual` | pomodori (25 min) | Agile Iterative Engineering Tasks | Open Source Agile Log |
| **Subbiah** | CSV | 72 | 9 | `TotalLaborCost` | USD (labor cost) | Function Point Labor Cost | PROMISE Repository / Research Use |
| **UCP_Dataset** | CSV | 71 | 15 | `Real_Effort_Person_Hours` | person-hours | Use Case Points Systems | Research Benchmark |
| **Valdes-Souto** | CSV | 57 | 4 | `Effort` | person-hours | COSMIC Function Points | Research Benchmark |

---

## Leakage Prevention Rules
Before any training, the following variables are strictly excluded to avoid data leakage:
- Derived ratio metrics computed using the actual target (e.g., `CostPerFP` in Subbiah, `Real_P20` in UCP, `HH_CFP` in Valdes-Souto).
- Post-completion actual metrics unavailable during initial estimation (e.g., `Time` in Maxwell, actual completion dates in Kitchenham).
- Redundant target copies (e.g., `N_effort` in China, `lneff` and `lnsize` in Finnish).

---

## Metric Gate Criteria
- **PRED(25):** $\ge 30\%$ for baseline gate; $\ge 70\%$ standard target where sample size allows.
- **MMRE:** Mean Magnitude of Relative Error $\le 1.00$.
- **MAE:** Candidate model MUST beat the median baseline calculator on the held-out test split.
- **Sample Size Gate:** Datasets with fewer than 25 valid projects are marked **EXPERIMENTAL** and cannot be approved for automated production sign-off.
