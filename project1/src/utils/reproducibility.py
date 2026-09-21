"""
Reproducibility System Module (Phase R1, Section 30)
记录实验运行环境、Git 提交、配置哈希、数据校验和与软硬件依赖版本，确保 100% 实验可复现。
"""
import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional

class ReproducibilityLogger:
    """
    实验复现性日志追踪器
    """
    
    @staticmethod
    def get_git_commit() -> str:
        try:
            cmd = ["git", "rev-parse", "HEAD"]
            commit = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('ascii').strip()
            return commit
        except Exception:
            return "UNKNOWN_OR_UNTRACKED"

    @staticmethod
    def calculate_file_hash(filepath: str) -> str:
        if not os.path.exists(filepath):
            return "FILE_NOT_FOUND"
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_dict_hash(d: dict) -> str:
        encoded = json.dumps(d, sort_keys=True).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def record_experiment_run(
        cls,
        run_name: str,
        config: dict,
        data_filepath: str,
        start_time: datetime,
        end_time: datetime,
        metrics_summary: dict,
        random_seed: Optional[int] = 42
    ) -> Dict[str, Any]:
        """
        生成并持久化完整的复现性元数据。
        """
        run_id = f"{run_name}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # 依赖版本
        import pandas as pd
        import numpy as np
        import yaml
        
        metadata = {
            "run_id": run_id,
            "git_commit": cls.get_git_commit(),
            "config_hash": cls.calculate_dict_hash(config),
            "data_version": "v1_25_etfs",
            "data_checksum": cls.calculate_file_hash(data_filepath),
            "python_version": sys.version.split()[0],
            "dependency_versions": {
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "yaml": yaml.__version__
            },
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "random_seed": random_seed,
            "config": config,
            "metrics": metrics_summary
        }
        
        os.makedirs("outputs/manifests", exist_ok=True)
        log_path = f"outputs/manifests/reproducibility_{run_id}.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            
        return metadata

