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
