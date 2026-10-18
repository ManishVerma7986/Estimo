"""Training Jobs Service.

Runs asynchronous training jobs with status tracking, progress logging, and cancellation.
"""

from __future__ import annotations
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.schemas.training import StartTrainingJobRequest, TrainingJobStatusResponse
from ml.train import train_models_for_dataset


class TrainingJobManager:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.base_dir
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.cancel_flags: Dict[str, bool] = {}

    def start_training_job(self, request: StartTrainingJobRequest) -> str:
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        now_str = datetime.now(timezone.utc).isoformat()

        job_state = {
            "job_id": job_id,
            "dataset_id": request.dataset_id,
            "target_column": request.target_column,
            "status": "PENDING",
            "progress_percentage": 0,
            "started_at": now_str,
            "completed_at": None,
            "logs": [f"[{now_str}] Job submitted for target '{request.target_column}'."],
            "result": None,
            "error": None
        }

        self.jobs[job_id] = job_state
        self.cancel_flags[job_id] = False

        # Run in worker thread
        thread = threading.Thread(
            target=self._run_training_worker,
            args=(job_id, request),
            daemon=True
        )
        thread.start()
        return job_id

    def _run_training_worker(self, job_id: str, request: StartTrainingJobRequest) -> None:
        state = self.jobs[job_id]
        state["status"] = "RUNNING"
        state["progress_percentage"] = 15
        state["logs"].append("Loading dataset and validating schema...")

        if self.cancel_flags.get(job_id, False):
            state["status"] = "CANCELLED"
            state["logs"].append("Job cancelled by user before execution.")
            return

        try:
            state["progress_percentage"] = 35
            state["logs"].append("Running data leakage checks and holdout splitting...")

            schema_path = None
            if request.schema_template_name:
                p = self.base_dir / "configs" / "schemas" / f"{request.schema_template_name}.json"
                if p.exists():
                    schema_path = str(p)

            state["progress_percentage"] = 55
            state["logs"].append("Training candidate models (Ridge, Huber, Random Forest, Gradient Boosting)...")

            res = train_models_for_dataset(
                dataset_id=request.dataset_id,
                target_column=request.target_column,
                schema_template_path=schema_path,
                split_strategy=request.split_strategy,
                time_column=request.time_column,
                group_column=request.group_column,
                random_seed=request.random_seed,
                base_dir=self.base_dir
            )

            state["progress_percentage"] = 85
            state["logs"].append("Evaluating candidate models against approval gates...")

            state["result"] = res
            state["status"] = "COMPLETED"
            state["progress_percentage"] = 100
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
            state["logs"].append("Training run completed successfully.")

        except Exception as exc:
            state["status"] = "FAILED"
            state["error"] = str(exc)
            state["logs"].append(f"ERROR: {exc}")
            state["completed_at"] = datetime.now(timezone.utc).isoformat()

    def get_job_status(self, job_id: str) -> Optional[TrainingJobStatusResponse]:
        state = self.jobs.get(job_id)
        if not state:
            return None
        return TrainingJobStatusResponse(**state)

    def cancel_job(self, job_id: str) -> bool:
        if job_id in self.jobs and self.jobs[job_id]["status"] in ["PENDING", "RUNNING"]:
            self.cancel_flags[job_id] = True
            self.jobs[job_id]["status"] = "CANCELLED"
            self.jobs[job_id]["logs"].append("Job cancelled by user request.")
            return True
        return False

    def list_jobs(self) -> List[TrainingJobStatusResponse]:
        return [TrainingJobStatusResponse(**st) for st in self.jobs.values()]


training_manager = TrainingJobManager()
