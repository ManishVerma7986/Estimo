"""Local Versioned Model Registry Module.

Manages versioned models, enforces cryptographic SHA-256 verification (Rule R6),
and powers CLI actions: list, activate, rollback, verify.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def compute_file_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class ModelRegistry:
    def __init__(self, base_dir: Path | str = "."):
        self.base_dir = Path(base_dir).resolve()
        self.models_dir = self.base_dir / "models"
        self.registry_file = self.models_dir / "registry.json"
        self._ensure_registry()

    def _ensure_registry(self) -> None:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            initial_data = {
                "registry_version": "1.0",
                "active_models": {},
                "history": {},
                "models": {}
            }
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

    def load_registry(self) -> Dict[str, Any]:
        with open(self.registry_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_registry(self, data: Dict[str, Any]) -> None:
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def register_model(
        self,
        target: str,
        version: str,
        model_file_rel_path: str,
        metadata_file_rel_path: str,
        evaluation_file_rel_path: str,
        feature_schema_file_rel_path: str,
        dataset_manifest_rel_path: str,
        dataset_id: str,
        algorithm: str,
        status: str,
        metrics: Dict[str, Any]
    ) -> str:
        """Registers a newly trained model artifact with its cryptographic signature."""
        full_model_path = self.base_dir / model_file_rel_path
        if not full_model_path.exists():
            raise FileNotFoundError(f"Model artifact not found at {full_model_path}")

        sha256_hash = compute_file_sha256(full_model_path)
        model_key = f"{target}@{version}"

        reg = self.load_registry()
        reg["models"][model_key] = {
            "target": target,
            "version": version,
            "algorithm": algorithm,
            "dataset_id": dataset_id,
            "status": status,
            "model_file_path": model_file_rel_path,
            "metadata_file_path": metadata_file_rel_path,
            "evaluation_file_path": evaluation_file_rel_path,
            "feature_schema_file_path": feature_schema_file_rel_path,
            "dataset_manifest_path": dataset_manifest_rel_path,
            "sha256": sha256_hash,
            "metrics": metrics,
            "registered_at": datetime.now(timezone.utc).isoformat()
        }

        # Auto-activate if approved and no active model exists for this target
        if status == "APPROVED":
            current_active = reg["active_models"].get(target)
            if not current_active:
                reg["active_models"][target] = version
                if target not in reg.get("history", {}):
                    reg.setdefault("history", {})[target] = []
                reg["history"][target].append(version)

        self.save_registry(reg)
        return model_key

    def activate_model(self, target: str, version: str) -> bool:
        """Activates a specific model version for a target."""
        reg = self.load_registry()
        model_key = f"{target}@{version}"
        if model_key not in reg["models"]:
            raise ValueError(f"Model version '{version}' for target '{target}' does not exist.")

        # Verify integrity before activation
        model_info = reg["models"][model_key]
        model_path = self.base_dir / model_info["model_file_path"]
        actual_hash = compute_file_sha256(model_path)
        if actual_hash != model_info["sha256"]:
            raise ValueError(f"Integrity check failed: Checksum mismatch for {model_key}!")

        # Record history for rollback
        current = reg["active_models"].get(target)
        if "history" not in reg:
            reg["history"] = {}
        if target not in reg["history"]:
            reg["history"][target] = []

        if current and current not in reg["history"][target]:
            reg["history"][target].append(current)

        reg["active_models"][target] = version
        reg["history"][target].append(version)
        self.save_registry(reg)
        return True

    def rollback_model(self, target: str) -> Optional[str]:
        """Rolls back the active model to the previously active version."""
        reg = self.load_registry()
        history = reg.get("history", {}).get(target, [])
        if len(history) < 2:
            return None  # No previous version to roll back to

        history.pop()  # Remove current version
        prev_version = history[-1]
        reg["active_models"][target] = prev_version
        self.save_registry(reg)
        return prev_version

    def verify_all_models(self) -> Dict[str, bool]:
        """Checks SHA-256 for all registered models on disk."""
        reg = self.load_registry()
        results: Dict[str, bool] = {}
        for model_key, info in reg.get("models", {}).items():
            path = self.base_dir / info["model_file_path"]
            if not path.exists():
                results[model_key] = False
                continue
            actual_hash = compute_file_sha256(path)
            results[model_key] = (actual_hash == info["sha256"])
        return results

    def list_models(self) -> List[Dict[str, Any]]:
        reg = self.load_registry()
        items = []
        for key, info in reg.get("models", {}).items():
            target = info["target"]
            active_ver = reg.get("active_models", {}).get(target)
            is_active = (info["version"] == active_ver)
            items.append({
                "model_key": key,
                "is_active": is_active,
                **info
            })
        return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Model Registry Management CLI")
    subparsers = parser.add_subparsers(dest="action", help="Action to execute")

    # list
    subparsers.add_parser("list", help="List all registered models and active versions")

    # activate
    act_parser = subparsers.add_parser("activate", help="Activate a model version")
    act_parser.add_argument("target", help="Prediction target (e.g., Effort, cost)")
    act_parser.add_argument("version", help="Model version (e.g., v1.0.0 or timestamp)")

    # rollback
    rb_parser = subparsers.add_parser("rollback", help="Roll back active model for a target")
    rb_parser.add_argument("target", help="Prediction target")

    # verify
    subparsers.add_parser("verify", help="Verify SHA-256 integrity of all registered models")

    args = parser.parse_args()
    registry = ModelRegistry()

    if args.action == "list":
        models = registry.list_models()
        if not models:
            print("No models currently registered in models/registry.json.")
            return
        print("\nRegistered Models:")
        print(f"{'ACTIVE':<8} {'TARGET':<15} {'VERSION':<15} {'ALGORITHM':<15} {'STATUS':<12} {'MAE':<10} {'PRED(25)':<10}")
        print("-" * 85)
        for m in models:
            active_flag = "[*]" if m["is_active"] else "   "
            mae = m.get("metrics", {}).get("MAE", "-")
            p25 = m.get("metrics", {}).get("PRED25", "-")
            print(f"{active_flag:<8} {m['target']:<15} {m['version']:<15} {m['algorithm']:<15} {m['status']:<12} {str(mae):<10} {str(p25):<10}")
        print()

    elif args.action == "activate":
        try:
            registry.activate_model(args.target, args.version)
            print(f"SUCCESS: Activated version '{args.version}' for target '{args.target}'.")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.action == "rollback":
        prev = registry.rollback_model(args.target)
        if prev:
            print(f"SUCCESS: Rolled back target '{args.target}' to version '{prev}'.")
        else:
            print(f"No previous version available to roll back for '{args.target}'.")

    elif args.action == "verify":
        res = registry.verify_all_models()
        print("\nModel Integrity Verification:")
        all_ok = True
        for k, ok in res.items():
            status = "VALID" if ok else "FAILED/CORRUPT"
            if not ok:
                all_ok = False
            print(f"  {k:30s} : {status}")
        if not res:
            print("  No models registered yet.")
        if not all_ok:
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
