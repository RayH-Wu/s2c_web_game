#!/usr/bin/env python3
"""Take the training paths off the published assets. Run after every export.

    python3 tools/export_policy.py && python3 tools/export_filter.py \
        && python3 tools/strip_provenance.py

The exporters stamp each asset with where its weights came from: the run
directory under ``logs/rsl_rl``, the md5 of the ``.pt``, the ``.cache`` copy it
was read from, and a free-text note naming the pool member. That record is how
an export is audited, and it must not be the thing a visitor to the repo reads,
so the full manifest is kept in ``.cache/manifest.provenance.json`` (gitignored)
and the published copies lose those keys.

``filter_nets_md5`` stays in the manifest -- it is the integrity check
tests/node_policy_parity.mjs runs against the shipped bins, not a path -- and is
dropped from the per-net json, which is where it is merely a duplicate.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POLICY_DIR = REPO / "assets" / "policies"
CACHE = REPO / ".cache"

MANIFEST_DROP = {
    "md5",
    "provenance",
    "source_bundle",
    "source_checkpoint",
    "upstream_checkpoint_md5",
    "upstream_md5_verified",
}
ASSET_DROP = {
    # top level
    "filter_nets_md5",
    "local_copy",
    "md5",
    "notes",
    "provenance",
    "source_bundle",
    "source_checkpoint",
    # inside `splice_infos` / `splice_corroboration`, whose remaining fields --
    # the system names and the seat sha256 -- are what makes the export
    # auditable without naming a run.
    "attacker_checkpoint",
    "defender_checkpoint",
    "records",
}


def prune(obj, drop):
    if isinstance(obj, dict):
        return {k: prune(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [prune(v, drop) for v in obj]
    return obj


def main() -> int:
    man_path = POLICY_DIR / "manifest.json"
    full = json.loads(man_path.read_text())

    CACHE.mkdir(exist_ok=True)
    (CACHE / "manifest.provenance.json").write_text(json.dumps(full, indent=1) + "\n", "utf-8")

    man_path.write_text(json.dumps(prune(full, MANIFEST_DROP), indent=1) + "\n", "utf-8")
    print(f"  manifest.json     dropped {sorted(MANIFEST_DROP)}")

    n = 0
    for p in sorted(POLICY_DIR.glob("*.json")):
        if p.name == "manifest.json":
            continue
        js = json.loads(p.read_text())
        out = prune(js, ASSET_DROP)
        if out != js:
            p.write_text(json.dumps(out, indent=2) + "\n", "utf-8")
            n += 1
    print(f"  {n} policy/net json files stripped")

    # A published asset that still names a run directory is the failure this
    # file exists to prevent, so say so loudly rather than exiting 0.
    leaked = [
        p.name
        for p in sorted(POLICY_DIR.glob("*.json"))
        if "logs/rsl_rl" in p.read_text() or ".cache/" in p.read_text()
    ]
    if leaked:
        print(f"STILL LEAKING a training path: {leaked}")
        return 1
    print("  no published asset names a training path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
