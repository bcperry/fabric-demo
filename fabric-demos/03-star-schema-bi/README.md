# 03 - Star Schema and BI

Combine the Stage 01 Lakehouse baseline and Stage 02 mirrored operational data
into analysis-ready dimensions, facts, Gold products, a Direct Lake semantic
model, and a Power BI report.

## Outcome

- **Leadership:** readiness, objective status, data trust, open findings, and
	corrective actions in one report with drill-through to evidence.
- **Data professionals:** Bronze/Silver curation, natural fact grain, 13
	conformed dimensions, 11 facts, 11 Gold products, relationships, governed
	measures, and Direct Lake.
- **Operations:** a dedicated PostgreSQL mirror page exposes source provenance,
	real public Indo-Pacific geography, system counts, and finding-to-evidence-to-action
	lineage from compact mirror-backed Gold products.

```bash
shared/setup-scripts/fabric_demo_cli.sh push-demo-03
shared/setup-scripts/fabric_demo_cli.sh run-demo-03
```

The mirrored database is the preferred administrative source. The canonical
CSV batches remain a deterministic fallback and must be labeled as fallback,
not mirroring. `gold_mirror_site_locations` and `gold_mirror_casework` read the
live Stage 02 mirror directly through OneLake; their report banner identifies
the source as `Azure PostgreSQL -> Fabric mirrored database`. Site names and
coordinates are public real-world geography. Operational systems, readiness,
findings, and their site associations remain synthetic demo data.
