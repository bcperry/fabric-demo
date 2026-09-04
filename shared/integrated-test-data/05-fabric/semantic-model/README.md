# Semantic Model Guidance

The semantic model should expose one governed story across planning, setup,
running, analysis, and post-test reporting.

Recommended conformed dimensions:

- `dim_site`
- `dim_system_instance`
- `dim_system_family`
- `dim_scenario`
- `dim_test_event`
- `dim_track`
- `dim_time`

Recommended measures:

- `Observed Event Count`
- `Delayed Integration Event Count`
- `Predicted vs Observed Delay Delta`
- `Ready Assets`
- `Assets With Limitation`
- `Advisory Safety Events`
- `Authoritative Operator Holds`
- `Open Corrective Actions`

The measure boundary must preserve that safety-status evidence is advisory only;
authoritative stop/resume decisions come from operator and report-review facts.