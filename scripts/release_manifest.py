from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    archive = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    manifest = {
        "app_version": "0.1.0",
        "build_time": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ),
        "git_commit": os.environ.get("GIT_COMMIT", ""),
        "milvus_version": "2.5.6",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "vector_dimension": 512,
        "sha256": {
            archive.name: sha256(archive),
        },
    }
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(manifest["sha256"][archive.name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
