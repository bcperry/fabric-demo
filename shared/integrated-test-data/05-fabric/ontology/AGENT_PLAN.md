# Agent Plan - Fabric IQ Ontology

## Mission

Create an optional MDA ontology package after Silver/Gold schemas are stable.

## Candidate entities

Site, Sensor, Track, TestEvent, Scenario, SystemFamily, SystemInstance, Component,
ReadinessState, MaintenanceAction, TestObjective, Observation, CommandEvent,
Anomaly, CorrectiveAction, SimulationRun, and DataProduct.

## Deliverables

- Versioned ontology source/package separate from the retail ontology.
- Lakehouse bindings for master/history data.
- Eventhouse bindings for current time-series data.
- Identifier, display-name, temporal, and relationship definitions.
- Creation notebook and validation queries.
- Agent-safe example questions grounded in the ontology.

## Acceptance

- Package creates a new ontology without modifying Demo 08.
- Every relationship maps to an actual stable key.
- Cross-engine navigation covers Track → Observation → TestObjective → Anomaly →
  CorrectiveAction and System → Site → Readiness → Maintenance.
- Preview unavailability does not block any core demo path.

