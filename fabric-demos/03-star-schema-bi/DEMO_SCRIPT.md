# Demo 03 Script

1. Show the Stage 01 Lakehouse baseline and Stage 02 mirrored tables.
2. Run Silver canonicalization and inspect rejected/quality records.
3. Build the conformed dimensions and facts; call out each fact's grain.
4. Open **Readiness Detail** and filter `integrated-defense-001`, one site, and
	one system; confirm the participant table updates with readiness and
	blocking reasons.
5. Open **PostgreSQL Mirror** and call out the live source banner, 40 mirrored
	real-world Indo-Pacific locations, 18 synthetic hardware components assigned
	to six lead-event sites, and the Azure
	Maps footprint from Guam and the Philippines through Korea and Japan.
6. Trace one mirrored finding through its PostgreSQL, Eventhouse, and Lakehouse
	evidence sources to the corrective action, status, and owner.
7. Clarify that site names and coordinates are public real-world geography;
	operational systems, readiness, findings, and site associations are demo data.
8. Explain that Direct Lake reads compact governed Delta products built from
	the Fabric mirrored database without copying the 8.2 million-row source
	into the semantic model.

Expected time: 20 minutes.
