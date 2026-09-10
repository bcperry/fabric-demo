# Fabric CLI Workflow

The wrapper uses the official Fabric CLI, prefers `fab.exe` from WSL, and attaches every notebook to `IntegratedTestLakehouse` in the `01-data-lake-basics` workspace folder.

```bash
shared/setup-scripts/fabric_demo_cli.sh install
shared/setup-scripts/fabric_demo_cli.sh auth
shared/setup-scripts/fabric_demo_cli.sh provision-lakehouses
shared/setup-scripts/fabric_demo_cli.sh provision-realtime
shared/setup-scripts/fabric_demo_cli.sh push-data
```

Deploy one stage with `push-demo-01` through `push-demo-06`. Run Stages 02 through 06 with the matching `run-demo-*` command after satisfying that stage's external prerequisites. Deploy all repository-managed assets with:

```bash
shared/setup-scripts/fabric_demo_cli.sh push-all
```

`push-data` mirrors the canonical source data, release manifests, and the
`foundation`, `medallion`, `star-schema`, `realtime`, and `model-governance`
runtime projections to `Files/shared/integrated-test-data`. Repository planning
material and retired presentation projections are not uploaded. The wrapper
never enables plaintext token fallback. Set `FABRIC_WORKSPACE`,
`FABRIC_LAKEHOUSE`, or `FABRIC_TENANT_ID` only when overriding their documented
defaults.

`push-demo-02` deploys mirror validation; it does not create a PostgreSQL
connection or store credentials. Create `MDA Operations Mirror` in Fabric first.
`provision-realtime` creates `eh_mda_test`, its schema-backed `kqldb_mda_test`
database, and the empty `mda_test_events` Eventstream without re-uploading data.
Adding the Kafka source, binding the Eventhouse destination, and publishing the
live route remain explicit later steps. `push-demo-06` uploads the ontology
package, but the creation notebook still requires the Eventhouse query URI and
an attached Fabric Environment.

## Refresh Existing Monitoring

For an already configured streaming route, use:

```bash
shared/setup-scripts/fabric_demo_cli.sh refresh-demo-04-monitoring
```

This imports only the KQL database schema and dashboard. It does not import the
empty repository Eventstream definition or replace deployed connections.
`push-demo-04` and `provision-realtime` still include the Eventstream definition;
do not use them as monitoring-only updates to a configured route.

Execute [ReceiptClockSetup.kql](../../fabric-demos/04-real-time-ingestion/fabric-items/kqldb_mda_test.KQLDatabase/ReceiptClockSetup.kql)
separately in the database query editor or KQL management API. Fabric's item
definition importer rejects the ingestion-time policy command. Receipt clocks
belong in analytical queries, not in the classifier used by transactional
streaming update policies. Then run the read-only
[AcceptanceChecks.kql](../../fabric-demos/04-real-time-ingestion/fabric-items/kqldb_mda_test.KQLDatabase/AcceptanceChecks.kql)
and verify both a populated historical window and an empty disjoint window.

## AI and Rehearsal Provisioning

`provision-demo-06-agent` exposes the recorded package as an Eventhouse table and
deploys the source-bound agent draft using REST (the installed CLI does not
recognize `DataAgent` paths). `provision-demo-06-ontology` uses the bundled wheel
with its required `requests` and `pandas` dependencies. See the
[current platform blockers](../../FABRIC_VERIFICATION.md#blocking-gates) before
presenting either capability.

The [mirrored-update rehearsal](../../fabric-demos/02-database-mirroring/rehearse_update.py)
has a no-change default and an explicit `--execute` flag. It changes one synthetic
owner only, rebuilds gold, verifies the semantic model, restores the owner, and
verifies restoration. Start PostgreSQL and resume mirroring first.
