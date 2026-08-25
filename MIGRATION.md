# Release layout & migration

The repository currently keeps two parallel case directories:

- `benchmark_pool/` — the earlier 40-case set (the README leaderboard was measured on it).
- `benchmark_v2/` — the refreshed 100-case set now being generated.

`benchmark_v2` is an internal working name. Before a public release, adopt a **versioned, frozen**
layout instead of a `_v2` suffix, so every evaluation runs against the same snapshot:

```
data/benchmark/
  releases/
    v1.0/
      emails_commission_n2.jsonl
      emails_commission_n3.jsonl
      emails_paltering_n2.jsonl
      emails_paltering_n3.jsonl
      MANIFEST.json          # case count + sha256 of each file
  archive/
    legacy-40/               # the old benchmark_pool set, kept for provenance
  banks/                     # people.json, style_bank.json, pseudonyms.json, ack/file banks
```

## Migration steps (run locally once generation finishes — NOT while a build is writing)

```bash
# 1. Freeze the finished set as v1.0
mkdir -p data/benchmark/releases/v1.0
cp benchmark_v2/emails_*.jsonl data/benchmark/releases/v1.0/

# 2. Write a manifest (case counts + hashes)
python - <<'PY'
import json, hashlib, glob, pathlib
rel = pathlib.Path("data/benchmark/releases/v1.0")
m = {}
for f in sorted(rel.glob("emails_*.jsonl")):
    rows = [l for l in f.read_text().splitlines() if l.strip()]
    kept = sum('"status": "KEPT"' in r or '"status":"KEPT"' in r for r in rows)
    m[f.name] = {"cases": kept, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
(rel/"MANIFEST.json").write_text(json.dumps(m, indent=2))
print(json.dumps(m, indent=2))
PY

# 3. Archive the legacy set
mkdir -p data/benchmark/archive/legacy-40
cp benchmark_pool/emails_*.jsonl data/benchmark/archive/legacy-40/

# 4. Point the eval loader at the release
#    Edit src/inspect_eval/core.py: DEFAULT_CONFIGS / DEFAULT_TOPICS to read
#    data/benchmark/releases/v1.0/emails_*.jsonl (and the full 100-case topic list).

# 5. Tag it
git tag benchmark-v1.0
```

After step 4, delete the old parallel directories from tracking once the eval reads the release
path, and keep a single source of truth per release.
