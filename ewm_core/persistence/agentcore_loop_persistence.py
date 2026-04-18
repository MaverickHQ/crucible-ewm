from __future__ import annotations

from pathlib import Path

import boto3


def upload_dir_to_s3(local_dir: Path, bucket: str, prefix: str) -> str:
    """Upload local_dir recursively to s3://bucket/prefix preserving relative paths."""
    if not local_dir.exists() or not local_dir.is_dir():
        raise ValueError(f"local_dir must exist and be a directory: {local_dir}")

    normalized_prefix = prefix.strip("/")
    s3 = boto3.client("s3")

    for file_path in sorted(local_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(local_dir).as_posix()
        key = f"{normalized_prefix}/{rel}" if normalized_prefix else rel
        s3.put_object(Bucket=bucket, Key=key, Body=file_path.read_bytes())

    return f"s3://{bucket}/{normalized_prefix}" if normalized_prefix else f"s3://{bucket}"
