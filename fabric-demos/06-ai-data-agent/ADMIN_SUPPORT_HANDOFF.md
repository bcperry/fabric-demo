# Fabric Administrator and Support Handoff

Checked 2026-09-09. This is a prepared handoff, not a submitted support case.
After activating Global Administrator through PIM and signing in again, the user
approved enabling ontology creation on the `mdademo` capacity only. That delegated
override is saved. The tenant-wide default remains disabled; no AI safety or
cross-geography settings were changed.

## Environment

- Tenant: `a9077aab-55ce-4dac-8343-89d30aeaa786`.
- Workspace: `mda-fabric-demo`, `10327698-2b0d-446f-9b1b-beabe18a4bda`.
- Capacity: `mdademo`, paid F2, Central US, Active.
- Browser identity: `admin@mngenvmcap005042.onmicrosoft.com`.
- Deployment identity: `admin@mngenvmcap005042.onmicrosoft.com`.
- Browser admin portal now exposes Tenant settings following PIM activation and
  sign-out/sign-in. Graph confirmed active Global Administrator membership.
- Earlier `GET /v1/admin/tenantsettings` using the Fabric CLI token returned HTTP 403
  `InsufficientScopes`, request `f778898d-4da3-421f-a279-d57677664573`.

The earlier CLI scope failure is not evidence that the current browser lacks
administrator access.

## Ontology Creation

**Confirmed configuration:** **Users can create Ontology (preview) items** was
disabled for the entire organization and for `mdademo`. With explicit approval,
Admin portal > Capacity settings > Fabric Capacity > mdademo > Delegated tenant
settings now has **Override tenant admin selection** checked and ontology
**Enabled for all users in capacity**. The tenant-wide default was separately
verified unchanged as disabled. Capacity ID:
`31216fbb-0e7c-40f1-bbb7-2ff4c00643f9`.

Fabric displayed a propagation notice of up to 15 minutes. One immediate
provisioning attempt still returned HTTP 403 `FeatureNotAvailable`,
`isRetriable: false`, request `90b2342d-c7ca-44dc-b070-fcfa83a16162`.
Creation subsequently succeeded at `2026-09-09T14:03:10Z`, operation
`3e1ea25f-1047-4cb7-aee3-7db14b088a05`, item
`0b149572-2340-4e6d-b36b-14330d12c132`. No additional tenant setting was changed.
Do not enable unrelated settings or broaden tenant-wide access.

Official prerequisite:
[Ontology required tenant settings](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview-tenant-settings).
The documented tutorial requires Fabric-enabled capacity; the current capacity
is active. There is no evidence here that an F64 upgrade is required.

The approved setting has taken effect. Repeatable ontology provisioning:

```bash
shared/setup-scripts/fabric_demo_cli.sh provision-demo-06-ontology
```

**Existing failure for support:** `POST /v1/workspaces/{workspaceId}/ontologies`
returned HTTP 403 `FeatureNotAvailable`, `isRetriable: false`, request ID
`c038da05-fa04-401f-a03a-ec5ab7ef2756` on 2026-09-08. Local generation succeeded
with eight entity types, eight relationships, ten bindings, and eight
contextualizations. This historical eligibility failure is now resolved.

If tenant eligibility is confirmed and creation still fails, provide the above
request/workspace/capacity information to Fabric support and request the specific
eligibility gate. Do not repeatedly retry the unchanged non-retriable failure.

**Completion gate:** creation operation succeeds; all bindings resolve; instance
counts, keys, and relationship joins are queried successfully. Creation alone
does not prove ontology binding correctness.

The binding gate is now verified: eight populated entity views; exact history
validation notebook `95aea5da-2bf2-4b79-9e24-596c32410bd5` completed; graph refresh
`f94fca3d-1653-46ba-9247-6a4a0b7e0d03` completed at `14:28:52Z`.
The command-to-system graph and 104,000 ms command chart render in the browser.
Graph storage reads required omitting `dbo` for the schema-less Lakehouse.
Static observation/command identities and relationships now use Lakehouse facts;
isolated Eventhouse history preserves their exact source IDs and timestamps.
The creation notebook also completed (job `0ee7118f-8d1b-4dec-b871-ed77680cfd0d`).
An earlier run failed with `ModuleNotFoundError: rdflib`; the dedicated
`MDA Ontology Dependencies` Environment now supplies that declared dependency.

## Data Agent Validation

On 2026-09-09, a fresh admin session showed no selected tables despite the
initial source definition marking two flat elements as selected. Selecting
`EvidenceReviewPackages` and `RawIntegratedTestEvents` in the UI persisted after
reload, and the unchanged reconciliation question returned a grounded answer.
The previous content rejection did not recur; its original cause is not proven.

The complete service-generated source metadata was imported into the repository
after a simplified hierarchy failed a deployment/reload check. The complete
export preserved the two selections after deployment. Citation instructions now
require unabbreviated package identity, source path, and applicable limitations.
The revised response correctly reconciled 15 raw records into 13 canonical,
one duplicate (lines 7/8), and one rejection (line 15), and distinguished envelope
admission from full payload-schema or engineering validation. Query details
exposed the source row, raw records, full package ID, and source path.

Full answer acceptance and human review remain separate gates. Historical
rejection details below are retained for support only if the issue recurs.

**Historical query failure:** after successful Agent deployment
`21d65b7e-d583-4750-b9d5-a494e4644348` at `14:43:44Z`, a cleared, fully reset
chat received the unchanged cross-event acceptance question. Its 45-second
response reported invalid KQL join attributes, followed by unresolved
`Package.limitations`. No package or reference rows were retrieved. Source
instructions were verified in the UI; all three selected tables persist after
reload, and all four stored example queries execute successfully. Those facts
isolate an answer-generation failure, not a missing reference table or an
ontology eligibility problem. See [ANSWER_ACCEPTANCE.json](ANSWER_ACCEPTANCE.json)
for the exact question, case results and citation limitations. No support case
has been submitted and the Agent remains unpublished.

**Retrieval repair:** deployment `06395e9a-feee-43cb-bad1-f6477aabd403`
succeeded at `15:07:27Z`. The selected `EvidenceReviewContext` table contains
the verified package and independently identified SQL reference side by side,
with explicit non-linkage limitations. It does not assert an event relationship.
Six example queries execute directly; the timing query returns a 20-second gap.
The service definition export confirms only this table is selected and that
source instructions match the repository. Fabric's schema-generated table ID
`2019c2fc-4b33-4058-9e94-652db266e4ac` is required to persist selection.
The unchanged standalone cross-event question now returns both source identities,
paths and limitations in a fresh chat. See the acceptance record for the full
five-question run and the separate human-evaluation gate.

- Agent: `MDA Evidence Review Agent`, `6cf57c76-efc5-4f60-bdd2-8c353483b0c4`.
- Data source: `kqldb_mda_test`, `210c14b4-028c-4db9-91f2-e617cd21a2dc`, in the
  same workspace/capacity as the agent.
- Selected source: `EvidenceReviewContext`. Original package, raw and reference
  tables remain available in Eventhouse but are not selected by the Agent.
  The reference remains a checked-in SQL seed, not current deployed status.
- Runtime displayed on 2026-09-09: Standard; UI announces GPT 5.1.
- Publication subsequently authorized by the user and confirmed by Fabric at
  `2026-09-09T15:26:11Z`. Microsoft 365 Agent Store remains off. Historical draft
  descriptions above refer to the earlier diagnostics; human evaluation and
  evidence approval remain unperformed.

Previously rejected question (now answered unchanged):

> For test-streaming-findings-001, why are there 15 raw records but only 13 canonical events? Cite the records and explain whether anything was deleted.

Historical response:

> There's content here I can't work with. Try asking a new question. If that doesn't work, there might be an issue with the content in your source data.

The saved response shows two seconds. On 2026-09-09, expanding that response did
not expose generated query steps or a diagnostic error code. This inspection
did not rerun the question, change the runtime, rewrite source context, or weaken
safeguards. The UI message alone does not identify whether the prompt, agent
instructions, source content, or a governance policy triggered rejection.

The underlying package/raw data are queryable directly. The package verifies
15 raw records = 13 canonical + one duplicate + one rejected envelope. Replay
payload verification and the exact saved dashboard queries pass. These facts
prove the direct data path, not the agent's authorization or answer quality.

**If rejection recurs:** inspect the failed interaction using supported
Fabric diagnostics and tenant/Purview auditing. Identify the rejection stage and
policy/error code. **Users can use Copilot, AI Agents and other AI experiences
powered by Azure OpenAI** is confirmed enabled for the entire organization and
all users in this capacity. Check any applicable DLP/access restriction policy.
Request review of a possible false positive for this
synthetic data-quality accounting question; do not disable policy enforcement.

The [documented Data Agent prerequisites](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)
allow paid F2 and higher. The source and agent share a capacity region.
[Current tenant-setting guidance](https://learn.microsoft.com/en-us/fabric/data-science/data-agent-tenant-settings)
requires cross-geography processing/storage switches for capacities outside the
US/EU boundaries; do not enable those switches indiscriminately for Central US.

**Completion gate:** run every case in [ANSWER_ACCEPTANCE.json](ANSWER_ACCEPTANCE.json);
verify query results and resolve every citation.
Keep the agent unpublished until every assertion passes. No human evidence
acceptance or execution authorization should be invented.