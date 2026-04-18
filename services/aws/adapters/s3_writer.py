from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional

import boto3

from services.core.artifacts.writer import (
    RunContext,
    serialize_manifest,
    serialize_manifest_from_context,
    serialize_simulation_result,
)
from services.core.simulator import SimulationResult


@dataclass
class S3ArtifactWriter:
    bucket_name: str

    def __post_init__(self) -> None:
        self._client = boto3.client("s3")

    def write(
        self,
        result: SimulationResult,
        mode: Optional[str] = None,
        correlation_id: Optional[str] = None,
        strategy_path: Optional[str] = None,
        budgets: Optional[Dict[str, object]] = None,
        symbols: Optional[list[str]] = None,
    ) -> Dict[str, str]:
        prefix = f"artifacts/{result.run_id}"
        trajectory_key = f"{prefix}/trajectory.json"
        decision_key = f"{prefix}/decision.json"
        deltas_key = f"{prefix}/deltas.json"
        manifest_key = f"{prefix}/manifest.json"

        # Use shared serialization function
        payloads = serialize_simulation_result(result)

        self._client.put_object(
            Bucket=self.bucket_name,
            Key=trajectory_key,
            Body=json.dumps(payloads["trajectory"], indent=2).encode("utf-8"),
        )
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=decision_key,
            Body=json.dumps(payloads["decision"], indent=2).encode("utf-8"),
        )
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=deltas_key,
            Body=json.dumps(payloads["deltas"], indent=2).encode("utf-8"),
        )

        # Generate and upload manifest with stable key ordering
        # For AWS, default mode is "agentcore-loop" if not specified
        if mode is None:
            mode = "agentcore-loop"

        manifest_payload = serialize_manifest(
            result,
            mode=mode,
            correlation_id=correlation_id,
            strategy_path=strategy_path,
            budgets=budgets,
            symbols=symbols,
            artifact_s3_prefix=f"s3://{self.bucket_name}/{prefix}",
        )
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=manifest_key,
            Body=json.dumps(manifest_payload, indent=2, sort_keys=True).encode("utf-8"),
        )

        return {
            "artifact_prefix": prefix,
            "trajectory_key": trajectory_key,
            "decision_key": decision_key,
            "deltas_key": deltas_key,
            "manifest_key": manifest_key,
        }

    def write_with_context(
        self,
        result: SimulationResult,
        context: RunContext,
    ) -> Dict[str, str]:
        """
        Write artifacts using a RunContext for resolved values.

        This is the preferred method when you have resolved runtime values.
        """
        prefix = f"artifacts/{context.run_id}"
        trajectory_key = f"{prefix}/trajectory.json"
        decision_key = f"{prefix}/decision.json"
        deltas_key = f"{prefix}/deltas.json"
        manifest_key = f"{prefix}/manifest.json"

        # Use shared serialization function
        payloads = serialize_simulation_result(result)

        self._client.put_object(
            Bucket=self.bucket_name,
            Key=trajectory_key,
            Body=json.dumps(payloads["trajectory"], indent=2).encode("utf-8"),
        )
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=decision_key,
            Body=json.dumps(payloads["decision"], indent=2).encode("utf-8"),
        )
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=deltas_key,
            Body=json.dumps(payloads["deltas"], indent=2).encode("utf-8"),
        )

        # Generate manifest from context with resolved values
        # Set the S3 prefix for the context
        context.artifact_s3_prefix = f"s3://{self.bucket_name}/{prefix}"

        manifest_payload = serialize_manifest_from_context(result, context)
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=manifest_key,
            Body=json.dumps(manifest_payload, indent=2, sort_keys=True).encode("utf-8"),
        )

        return {
            "artifact_prefix": prefix,
            "trajectory_key": trajectory_key,
            "decision_key": decision_key,
            "deltas_key": deltas_key,
            "manifest_key": manifest_key,
        }

    def enumerate_artifacts(self, run_id: str) -> list[str]:
        """
        Enumerate all artifact keys for a given run_id.
        Used for testing and verification.
        """
        prefix = f"artifacts/{run_id}"
        return [
            f"{prefix}/trajectory.json",
            f"{prefix}/decision.json",
            f"{prefix}/deltas.json",
            f"{prefix}/manifest.json",
        ]
