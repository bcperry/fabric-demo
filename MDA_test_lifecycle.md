# MDA Test Lifecycle Overview
 
A Missile Defense System test is a tightly controlled, safety-governed event used to evaluate whether sensors, command-and-control systems, communications, interceptors, operators, and analysis systems perform as expected against a defined threat scenario. The details vary by program, classification level, and whether the event is developmental, operational, live-fire, simulation-based, or an integrated flight test.
 
## 1. Planning Phase
 
The planning phase defines what capability is being tested, under what conditions, and how success will be measured.
 
| Area | What Happens |
| --- | --- |
| Test objectives | Define success criteria for sensor detection, tracking accuracy, fire-control quality, engagement timing, interceptor performance, command-and-control response, operator workflow, or end-to-end kill-chain performance. |
| Scenario design | Build a representative threat scenario, including launch location, trajectory class, target characteristics, timing, environmental assumptions, and defended asset geometry. |
| Test type selection | Decide whether the event is a simulation, hardware-in-the-loop test, ground test, flight test, live intercept, cyber/electromagnetic resilience test, or operational exercise. |
| Safety and range planning | Establish launch windows, exclusion zones, debris hazard areas, abort criteria, telemetry coverage, aviation and maritime notices, and emergency procedures. |
| Data requirements | Define instrumentation, time synchronization, telemetry feeds, radar tracks, command logs, operator actions, environmental data, and ground truth measurements needed for evaluation. |
| Governance | Review legal, treaty, environmental, safety, classification, and interagency requirements. |
 
### Participants
 
- Program office and test director
- System engineers and missile-defense architects
- Operational commanders and warfighters
- Range safety officers
- Sensor, interceptor, and command-and-control teams
- Modeling and simulation teams
- Cybersecurity and communications teams
- Data collection and instrumentation teams
- Independent evaluators or operational test agencies
- Contractors and government laboratories
- Public affairs and reporting authorities, where applicable
 
## 2. Setup Phase
 
The setup phase converts the plan into a controlled, instrumented test environment.
 
| Area | Description |
| --- | --- |
| Test range preparation | Instrumented test ranges, launch areas, radar sites, optical tracking systems, telemetry receivers, communications links, and safety zones are configured. |
| Target preparation | A target vehicle or simulated threat is configured to follow the planned trajectory and behave according to the expected test profile. |
| Interceptor and system preparation | Interceptor rounds, launchers, fire-control systems, command systems, and engagement control stations are checked and configured. |
| Sensor alignment | Radars, infrared sensors, space-based sensors, ship-based sensors, airborne sensors, or ground sensors are calibrated and synchronized. |
| Network integration | Tactical data links, command networks, test-control networks, voice circuits, and telemetry networks are validated. |
| Dry runs | Teams rehearse countdowns, decision points, abort procedures, communications, and data capture. |
| Data architecture | Collection systems are checked to ensure logs, telemetry, radar tracks, operator actions, and timing references are captured consistently. |
 
### Data Needed and Typical Locations
 
| Data Type | Typical Source or Location |
| --- | --- |
| Target telemetry | Target vehicle instrumentation and range receivers |
| Interceptor telemetry | Interceptor instrumentation, launch platform, and telemetry ground stations |
| Radar and sensor tracks | Ground radars, ship sensors, airborne sensors, and space-based sensor feeds |
| Command-and-control logs | Fire-control systems, battle management systems, and operator consoles |
| Communications data | Tactical links, voice circuits, and network monitoring systems |
| Ground truth data | Range instrumentation, GPS/INS packages, optical trackers, and independent radars |
| Environmental data | Weather systems, atmospheric models, sea state observations, and ionospheric or space weather sources |
| Safety data | Range safety systems, flight termination systems, and hazard-zone monitoring |
 
## 3. Running the Test
 
Execution is controlled through a formal countdown, readiness process, and decision sequence.
 
1. Readiness polls confirm that range safety, launch teams, sensors, networks, data systems, operators, and command authorities are ready.
2. Target launch or scenario start begins the test event.
3. Sensor detection and tracking occur as radars and other sensors acquire the target and generate tracks.
4. Track correlation and discrimination occur inside command-and-control systems, which combine sensor data and classify objects.
5. Engagement decisions are made either automatically within defined rules or by authorized operators, depending on the test design.
6. Interceptor launch or simulated engagement occurs.
7. Midcourse and terminal updates may be sent to the interceptor or fire-control system.
8. Intercept assessment is performed using telemetry, sensors, and ground-truth instrumentation.
9. Safety termination or normal completion occurs based on preplanned criteria.
10. Data preservation begins immediately so raw data is secured before detailed analysis.
 
For non-live tests, the target and interceptor may be simulated while real command systems, sensors, or operator consoles participate. These events may be conducted as simulation, digital, hardware-in-the-loop, or distributed mission operations tests.
 
## 4. Analysis Phase
 
After the event, analysts compare what happened against the test objectives, requirements, and pre-test predictions.
 
| Analysis Area | What Is Evaluated |
| --- | --- |
| Detection | Whether sensors detected the target at the expected time and range. |
| Tracking | Whether tracks were accurate, stable, and continuous. |
| Discrimination | Whether the system correctly classified relevant objects. |
| Fire control | Whether engagement-quality tracks were generated in time. |
| Command and control | Whether decisions, messages, and operator actions were correct and timely. |
| Interceptor performance | Whether the interceptor launched, flew, received updates, and performed as expected. |
| System timing | Whether latency across sensors, networks, and command systems stayed within requirements. |
| Communications | Whether links were available, accurate, and resilient. |
| Operator performance | Whether crews followed procedures and responded appropriately. |
| Model validation | Whether real-world results matched pre-test simulations and predictions. |
| Failure or anomaly review | Whether unexpected behavior can be reconstructed using logs, telemetry, and instrumentation. |
 
### Tools Used
 
- Modeling and simulation environments
- Mission planning tools
- Range safety and flight analysis tools
- Telemetry processing systems
- Radar track analysis tools
- Time-synchronized data repositories
- Command-and-control log parsers
- Statistical analysis tools
- Visualization tools for trajectories, timelines, and engagement geometry
- Configuration management systems
- Requirements verification databases
- Cyber and network monitoring tools
- Secure collaboration and reporting systems
 
## 5. Post-Test Reporting
 
The post-test reporting phase turns raw results, analysis products, and lessons learned into official findings.
 
| Report or Output | Purpose |
| --- | --- |
| Quick-look report | Provides initial results shortly after the test, including what occurred, whether major objectives were met, and any immediate anomalies. |
| Data review package | Curates telemetry, logs, sensor data, configuration records, and timing references. |
| Anomaly reports | Documents unexpected behavior, suspected causes, and corrective actions. |
| Requirement verification report | Maps observed performance against system requirements and test objectives. |
| Operational assessment | Evaluates suitability, effectiveness, reliability, maintainability, and operator usability. |
| Lessons learned | Captures planning, execution, technical, safety, and coordination improvements. |
| Final test report | Provides the official record of methodology, conditions, results, limitations, conclusions, and recommendations. |
 
The final report is usually provided to the program office, operational stakeholders, acquisition authorities, test agencies, engineering teams, and, when appropriate, oversight or public reporting authorities.
 
## Summary
 
A Missile Defense System test is not just a missile launch. It is an end-to-end evaluation of a complex system of systems: sensors, networks, command-and-control, operators, interceptors, safety infrastructure, and analytical models. The most important outcomes are not only whether an intercept occurred, but whether the system behaved predictably, produced trustworthy data, met requirements, and revealed what should be improved before operational use.
 
## 6. Mapping the Test Lifecycle to Microsoft Fabric
 
Microsoft Fabric can support the test lifecycle as an integrated data, analytics, reporting, and governance platform. In this context, Fabric is best suited for test data management, engineering analytics, operational dashboards, anomaly analysis, model validation, and reporting workflows. It should be used within the appropriate accredited environment, security boundary, and data classification controls for the program.
 
### Lifecycle-to-Fabric Mapping
 
| Test Lifecycle Section | Test Workflow or Event | Microsoft Fabric Products, Features, and Capabilities | Example Use |
| --- | --- | --- | --- |
| Planning | Test objectives, requirements, and success criteria | Fabric workspaces, Domains, Lakehouse, Warehouse, semantic models, Power BI reports, Git integration, deployment pipelines | Organize test artifacts by program, event, and classification boundary; map requirements to measures and planned data products. |
| Planning | Scenario design and pre-test modeling assumptions | Data Science, notebooks, Lakehouse, ML experiments, Power BI, OneLake shortcuts | Store scenario parameters, simulation outputs, assumptions, and model versions for comparison against post-test results. |
| Planning | Data requirements and instrumentation planning | Data Factory pipelines, Dataflows Gen2, Lakehouse tables, Warehouse schemas, OneLake data hub, Microsoft Purview integration | Define required telemetry, radar tracks, command logs, environmental data, and ground truth feeds before the event. |
| Planning | Governance, access, and classification control | Fabric workspaces, item permissions, sensitivity labels, endorsement, lineage, Microsoft Purview hub, tenant settings | Control who can access test data, document lineage, apply labels, and separate working, validated, and releasable datasets. |
| Setup | Range, sensor, telemetry, and network data onboarding | Data Factory pipelines, Eventstream, Real-Time Intelligence, Eventhouse, KQL databases, Lakehouse, OneLake shortcuts | Connect batch and streaming sources from range systems, telemetry collectors, network monitors, and sensor exports. |
| Setup | Data validation before execution | Data pipelines, notebooks, Data Wrangler, Lakehouse validation tables, Power BI readiness dashboards | Check schema completeness, missing fields, time synchronization, source availability, and expected event identifiers. |
| Setup | Dry runs and rehearsals | Eventstream, Eventhouse, KQL querysets, Power BI dashboards, Activator | Monitor rehearsal data in near real time, detect missing feeds, and alert teams when required data sources are not publishing. |
| Running | Live or near-real-time telemetry ingestion | Eventstream, Real-Time Intelligence, Eventhouse, KQL databases, Activator | Ingest high-volume event streams, telemetry messages, system status updates, and timing events for live situational monitoring. |
| Running | Sensor track and command-event monitoring | Eventhouse, KQL querysets, Real-Time dashboards, Power BI Direct Lake reports | Visualize track continuity, event timelines, system states, message latency, and data feed health during the test. |
| Running | Countdown, readiness, and event logging | Lakehouse, Warehouse, Data Factory, Eventhouse, semantic models | Preserve structured countdown events, readiness polls, operator actions, decision points, and system state changes. |
| Running | Immediate anomaly detection | Activator, KQL queries, notebooks, Data Science models | Trigger alerts when feeds stop, timing thresholds are exceeded, required events are missing, or telemetry values fall outside expected bounds. |
| Analysis | Raw data preservation and curation | OneLake, Lakehouse bronze/silver/gold zones, Data Factory pipelines, shortcuts, lineage | Preserve immutable raw files, curate cleaned datasets, and publish validated analysis-ready tables. |
| Analysis | Time synchronization and event reconstruction | Notebooks, Spark, Eventhouse, KQL querysets, Lakehouse, Warehouse | Align telemetry, radar tracks, command logs, voice/network events, and ground truth into a common event timeline. |
| Analysis | Detection, tracking, discrimination, and timing analysis | KQL databases, notebooks, Data Science, Power BI, semantic models | Evaluate detection time, track stability, classification outcomes, engagement timing, message latency, and system response. |
| Analysis | Model validation and simulation comparison | Data Science, ML experiments, notebooks, Lakehouse, Power BI | Compare pre-test predictions against observed performance and retain model inputs, outputs, metrics, and versions. |
| Analysis | Anomaly investigation | Eventhouse, KQL querysets, notebooks, Power BI drill-through reports, lineage | Trace anomalies across telemetry, system logs, network events, configuration records, and operator actions. |
| Post-test reporting | Quick-look reporting | Power BI dashboards, Real-Time dashboards, semantic models, Data Activator alerts | Produce early summaries of event status, objective completion, data quality, major anomalies, and known limitations. |
| Post-test reporting | Formal reporting and evidence packages | Power BI paginated reports, semantic models, Warehouse, Lakehouse, deployment pipelines | Generate standardized reports with approved metrics, source traceability, and repeatable calculations. |
| Post-test reporting | Requirements verification | Warehouse, semantic models, Power BI scorecards or metrics, Lakehouse | Map measured results to requirements, thresholds, test objectives, and pass/fail or confidence statements. |
| Post-test reporting | Lessons learned and historical trend analysis | Lakehouse, Warehouse, Power BI, notebooks, Data Science | Compare results across test events, identify recurring anomalies, and track corrective-action effectiveness over time. |
 
### Data Architecture Alignment
 
| Data Layer | Fabric Capability | Test Lifecycle Role |
| --- | --- | --- |
| Source landing | OneLake, Lakehouse files, OneLake shortcuts, Data Factory pipelines | Land raw telemetry, sensor exports, logs, environmental data, configuration files, and range products without prematurely altering them. |
| Streaming ingestion | Eventstream, Eventhouse, KQL databases, Real-Time Intelligence | Capture event streams, telemetry status, system health, timing events, and live operational logs. |
| Raw preservation | Lakehouse bronze tables or file zones | Maintain original test data, source metadata, receipt timestamps, checksums, and provenance. |
| Curated data | Lakehouse silver/gold tables, Warehouse | Produce normalized, joined, quality-checked datasets for analysts, engineers, and reporting teams. |
| Analytical modeling | Notebooks, Spark, Data Science, ML experiments | Run reconstruction, statistical analysis, feature engineering, model validation, and anomaly detection. |
| Serving and reporting | Semantic models, Direct Lake, Power BI reports, paginated reports | Deliver validated metrics, dashboards, quick-look products, and formal reporting outputs. |
| Governance | Microsoft Purview integration, sensitivity labels, lineage, workspace roles, endorsement | Protect sensitive data, document lineage, identify authoritative products, and support auditability. |
 
### Fabric Product and Feature Usage by Role
 
| Role | Fabric Capabilities Used | How the Role Uses Fabric |
| --- | --- | --- |
| Test director and program leadership | Power BI dashboards, semantic models, scorecards or metrics, deployment pipelines | Track readiness, objective completion, event status, quick-look outcomes, and formal reporting products. |
| Range and instrumentation teams | Eventstream, Eventhouse, KQL querysets, Real-Time dashboards, Activator | Monitor telemetry feeds, instrumentation health, source availability, and timing integrity. |
| System engineers | Lakehouse, Warehouse, notebooks, Power BI, lineage | Analyze system performance, reconstruct timelines, evaluate requirements, and review anomalies. |
| Data engineers | Data Factory, Dataflows Gen2, Lakehouse, Warehouse, OneLake shortcuts | Build ingestion pipelines, transform data, manage schemas, and publish curated datasets. |
| Data scientists and modelers | Data Science, notebooks, ML experiments, Lakehouse | Compare models to observed results, run statistical analysis, and build anomaly detection approaches. |
| Cybersecurity and network analysts | Eventhouse, KQL querysets, Real-Time Intelligence, Power BI | Analyze network logs, link availability, latency, data movement, and cyber-relevant telemetry. |
| Independent evaluators | Warehouse, semantic models, Power BI reports, paginated reports, lineage | Review approved data products, trace findings to source data, and produce independent assessments. |
| Governance and security teams | Purview integration, sensitivity labels, workspace roles, tenant settings, lineage | Enforce data access controls, classification handling, auditability, and release boundaries. |
 
### Example Fabric Workflow
 
1. Create a dedicated Fabric workspace for the test event and organize related assets under the appropriate domain.
2. Use Data Factory pipelines and OneLake shortcuts to land planned batch data sources such as scenario files, configuration records, environmental data, and historical test data.
3. Use Eventstream and Eventhouse to ingest near-real-time telemetry, system status, and event logs during rehearsals and execution.
4. Store raw data in Lakehouse bronze zones, then transform and validate it into curated Lakehouse or Warehouse tables.
5. Use notebooks, Spark, KQL, and Data Science capabilities to reconstruct event timelines, calculate metrics, compare against requirements, and investigate anomalies.
6. Publish approved semantic models and Power BI dashboards for quick-look reporting, engineering analysis, and leadership summaries.
7. Use paginated reports, governed semantic models, lineage, sensitivity labels, and deployment pipelines to support final reporting and controlled release.
 
### Important Implementation Considerations
 
- Use separate workspaces, domains, labels, and access controls for different programs, tests, classification levels, and release states.
- Preserve raw data separately from curated and reportable data products.
- Capture source metadata, ingestion time, data owner, event identifiers, schema versions, and transformation lineage.
- Define standard data contracts for telemetry, sensor tracks, command logs, environmental data, and ground truth.
- Use KQL and Real-Time Intelligence for high-volume time-series and event analysis.
- Use Lakehouse and Warehouse patterns for curated engineering datasets and repeatable reporting.
- Use semantic models to standardize metric definitions so quick-look and final reports use consistent calculations.
- Treat Fabric as an analytics and reporting environment, not as a replacement for certified range safety systems, tactical fire-control systems, or mission command systems.
 
## 7. Overlaying Fabric IQ, Work IQ, and Foundry IQ Across the Test Lifecycle
 
Fabric IQ, Work IQ, and Foundry IQ can be viewed as complementary intelligence layers over the Missile Defense System test lifecycle. Fabric IQ helps reason over governed operational and engineering data in Fabric. Work IQ helps reason across Microsoft 365 work artifacts, people, meetings, emails, documents, and collaboration activity. Foundry IQ helps build, ground, evaluate, and govern AI agents and applications that support test planning, execution awareness, analysis, and reporting.
 
The three IQ layers should operate inside the approved security, accreditation, classification, and data-handling boundaries for the mission environment.
 
### IQ Layer Roles
 
| IQ Layer | Primary Scope | Role in the Test Lifecycle |
| --- | --- | --- |
| Fabric IQ | Governed data, metrics, analytics products, semantic models, lineage, and Fabric-hosted analytical context | Makes test data easier to discover, interpret, query, and reuse across planning, execution, analysis, and reporting. |
| Work IQ | Microsoft 365 work context such as meetings, chats, emails, documents, action items, participants, decisions, and collaboration history | Connects the human coordination layer of the test to the technical lifecycle by surfacing decisions, task ownership, status, and supporting documents. |
| Foundry IQ | AI agents, grounded generative AI applications, evaluation, prompt orchestration, model selection, safety controls, and agent workflows | Enables purpose-built copilots and agents for test planning, data triage, anomaly investigation, report drafting, and decision support. |
 
### Lifecycle Overlay
 
| Test Lifecycle Stage | Fabric IQ Overlay | Work IQ Overlay | Foundry IQ Overlay | Combined Value to MDA |
| --- | --- | --- | --- | --- |
| Planning | Discovers prior test datasets, requirements metrics, historical anomalies, data products, semantic models, and lineage relevant to the planned event. | Summarizes planning meetings, decision records, action items, stakeholder inputs, schedule constraints, and source documents. | Supports planning assistants that draft test objectives, identify data gaps, generate checklists, and reason over approved doctrine, requirements, and historical lessons learned. | Accelerates planning by connecting engineering evidence, collaboration history, and AI-assisted planning workflows into one governed preparation process. |
| Setup | Helps validate whether required data sources, schemas, ingestion pipelines, semantic models, and quality checks are ready. | Tracks readiness discussions, open issues, approvals, dry-run notes, participant availability, and handoff status across teams. | Enables setup agents that monitor readiness criteria, flag missing inputs, summarize dry-run discrepancies, and recommend corrective actions. | Reduces setup risk by aligning technical data readiness with team readiness and AI-assisted issue tracking. |
| Running | Provides real-time and historical context for telemetry, event streams, readiness states, data quality, and system health dashboards. | Captures operational coordination context such as status calls, notes, decisions, incident updates, and stakeholder communications. | Supports event-monitoring agents that summarize live status, identify anomalies, explain likely data-quality issues, and guide analysts to relevant dashboards or queries. | Improves situational awareness by combining live data intelligence, human coordination, and AI-assisted monitoring. |
| Analysis | Grounds analysts in curated datasets, event timelines, requirements metrics, model outputs, KQL results, notebooks, and lineage. | Finds relevant post-test discussions, engineering notes, decisions, review comments, meeting transcripts, and unresolved action items. | Powers analysis agents that help reconstruct timelines, compare observed results to predictions, summarize anomalies, and draft evidence-backed findings. | Shortens analysis cycles by connecting validated data, expert collaboration, and repeatable AI analysis workflows. |
| Post-test reporting | Provides trusted metrics, semantic definitions, governed datasets, lineage, and Power BI or paginated reporting context. | Collects approvals, adjudication notes, report review comments, executive summaries, and stakeholder feedback. | Assists with report drafting, consistency checks, evidence traceability, briefing generation, and question-answering over approved report packages. | Produces faster, more consistent, and more traceable reports while preserving governance over source data and findings. |
| Continuous improvement | Identifies trends across test events, recurring anomalies, data-quality patterns, and requirement verification history. | Tracks lessons learned, corrective actions, ownership, due dates, and organizational knowledge from prior events. | Builds agents that recommend process improvements, retrieve prior lessons, and evaluate whether corrective actions reduced recurrence. | Converts each test into reusable institutional knowledge that improves future planning, execution, analysis, and reporting. |
 
### Value Statement for Fabric IQ
 
Fabric IQ provides MDA with an intelligence layer over governed test data, analytical products, metrics, lineage, and reporting assets. For the testing lifecycle, its value is the ability to help teams find the right data, understand what it means, trust where it came from, and reuse it consistently across quick-look reporting, engineering analysis, formal verification, and historical trend assessment.
 
**Value to MDA:** Fabric IQ can reduce time spent searching for data, reconciling metric definitions, rebuilding analysis context, and validating source lineage. It helps create a shared analytical foundation for test directors, system engineers, analysts, evaluators, and leadership.
 
### Value Statement for Work IQ
 
Work IQ provides MDA with an intelligence layer over the human and organizational context of a test: meetings, documents, chats, emails, decisions, task ownership, reviews, and approvals. Missile defense testing is highly coordinated, and important knowledge often lives in planning sessions, review boards, action-item lists, and post-test discussions. Work IQ helps connect that collaboration record to the technical test lifecycle.
 
**Value to MDA:** Work IQ can reduce coordination friction, preserve decision context, improve action-item accountability, and help teams recover the "why" behind test plans, changes, anomalies, and reporting decisions.
 
### Value Statement for Foundry IQ
 
Foundry IQ provides MDA with a platform intelligence layer for building grounded, evaluated, and governed AI agents and applications. In the test lifecycle, Foundry IQ can support specialized agents for planning assistance, readiness checks, data triage, anomaly investigation, report drafting, lessons-learned retrieval, and leadership question-answering over approved knowledge sources.
 
**Value to MDA:** Foundry IQ can help turn governed data and organizational knowledge into mission-specific AI workflows while supporting evaluation, safety controls, model governance, and repeatable agent operations.
 
### Combined Value Across the Lifecycle
 
Together, Fabric IQ, Work IQ, and Foundry IQ create an end-to-end intelligence fabric for MDA testing:
 
| Combined Capability | Lifecycle Benefit |
| --- | --- |
| Data intelligence plus work intelligence | Connects technical evidence with decisions, meetings, approvals, and ownership. |
| Governed AI over approved sources | Supports AI assistance without relying on untracked, unapproved, or disconnected knowledge sources. |
| Faster transition from event data to findings | Helps analysts move from raw data to curated evidence, findings, reports, and briefings more quickly. |
| Traceable recommendations | Allows findings and AI-generated summaries to be linked back to datasets, documents, meeting decisions, and report packages. |
| Reusable institutional knowledge | Converts each test event into searchable, governed knowledge for future planning and improvement. |
| Improved decision velocity | Gives leaders faster access to status, risk, readiness, anomalies, and evidence-backed conclusions. |
 
### Example Integrated Scenario
 
During a post-test analysis cycle, Fabric IQ helps an analyst find the authoritative telemetry dataset, event timeline, requirement metrics, and Power BI quick-look dashboard. Work IQ surfaces the relevant anomaly review meeting, engineering discussion, assigned action items, and approval trail. Foundry IQ powers an analysis agent that summarizes the anomaly, links it to the supporting Fabric datasets and Work IQ collaboration context, drafts a finding, and identifies what evidence still needs evaluator review.
 
The result is a faster and more traceable path from test execution to defensible conclusions.

## 8. Repository Demo Alignment

This repository implements the lifecycle as six independently teachable demos.
All use the canonical identifiers, contracts, scenario, and evidence in the
[shared integrated-test release](shared/integrated-test-data/README.md).

| Demo | Primary lifecycle responsibility | Planned outcome |
| --- | --- | --- |
| [01 - Data Lake Basics](fabric-demos/01-data-lake-basics/README.md) | Planning | Land a simulated CSV baseline, validate its contract, and save it as Delta. |
| [02 - Database Mirroring](fabric-demos/02-database-mirroring/README.md) | Setup and operational readiness | Mirror the external PostgreSQL administrative source and validate freshness and completeness. |
| [03 - Star Schema and BI](fabric-demos/03-star-schema-bi/README.md) | Analysis and reporting | Conform Lakehouse and mirrored records into facts, dimensions, governed measures, and leadership reporting. |
| [04 - Real-Time Ingestion](fabric-demos/04-real-time-ingestion/README.md) | Running the test | Monitor event health, timing, continuity, dropout, and deterministic findings. |
| [05 - ML Models](fabric-demos/05-ml-models/README.md) | Analysis and model validation | Compare readiness models and govern explainability, scoring, and drift. |
| [06 - AI Data Agent](fabric-demos/06-ai-data-agent/README.md) | Cross-lifecycle intelligence | Ask grounded questions over authoritative Lakehouse, mirror, semantic-model, and Eventhouse products. |

### Emulator and Resource Model

The emulator suite is intentionally low fidelity. Its purpose is to create
internally coherent data-engineering and analytics workloads, not to reproduce
real system behavior.

| Workload class | Resources | Scope |
| --- | --- | --- |
| Simulation | Python/Faker Kafka producers running locally, in containers, or as Kubernetes pods/jobs | Generate predicted and simulated TPY-2 radar, Patriot radar, Patriot launcher, and THAAD launcher streams. |
| Observed/"Real" | Separate Kubernetes pods using the same system-family profiles | Generate synthetic observed streams with maintenance context, degraded states, delayed/missing updates, and controlled data dropout. "Real" is a narrative lane name only. |
| Administrative | One PostgreSQL database, local container for development and managed service for cloud demos | Pre-seed test events, objectives, required feeds, systems, configuration, readiness, maintenance, findings, corrective actions, and reporting state. |

When no seed is supplied, each emulator pod generates a startup seed and uses
Faker to create its fictional identity, location, and event profile. A five-pod
deployment therefore produces five distinct data streams. Before emitting
business events, each pod persists a run manifest containing the non-secret seed,
scenario, instance identity, profile, schema version, and fictional location.
Rehearsals supply explicit seeds; exploratory runs can use random startup seeds.
Both modes are replayable from their manifests.

All generated locations, measures, event rates, maintenance conditions, and
dropout patterns are invented and labeled synthetic. Fabric is used for data,
analytics, governance, and reporting, not as a certified safety, tactical
fire-control, or mission-command system.