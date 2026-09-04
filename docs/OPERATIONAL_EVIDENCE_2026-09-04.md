# ALMA Monitor 2 — publication-safe operational evidence

Verification date: **4 September 2026**.

This record documents an operator-verified production check of the private
ALMA Monitor 2 controlled pilot. It provides a dated and version-bound account
of operation for grant and public-interest review. It is not an independent
certification and does not publish the private successor source.

## Verified production state

| Control | Verified result |
| --- | --- |
| Exact private runtime identifier | `95bea4a6dabffd7377538714e0ff8dcea987d3ce` |
| Runtime health | configured and enabled |
| Controlled preflight | passed |
| Observation source | private Mergin Maps project, version `v49`, read-only access |
| Evidence storage | private; public access prevention enabled |
| Legal Core | active 20-card runtime release |
| Kazakh presentation | 20/20 required cards verified |
| Visual evidence boundary | up to three photographs for one observation; neutral description only |
| Bounded delivery | at most one complete dossier per scheduled run |
| Queue after the first post-deployment cycle | `0` bounded items remaining |
| Durable pilot delivery state | `5` successful deliveries; `0` recorded delivery failures |
| Backup | fresh database backup verified and copied off-host |
| Reliability inspection | healthy; no active issue code |
| Scheduler watchdog | healthy; no repair action required |
| Current production timers | delivery, delivery status, backup, reliability and bounded watchdog active |
| Legacy worker | disabled |
| Automatic state-authority submission | disabled |

The first normal delivery cycle after the checked deployment completed at
`2026-09-04T07:41:59Z`. It found no bounded backlog and did not increase the
durable delivery count. The reliability inspection and watchdog completed
without calling the delivery worker or email channel directly. The preflight
transferred no field photograph; its visual-provider check used synthetic
readiness data only.

## Evidence and privacy boundary

This public record contains no observation text, photograph, precise field
coordinate, personal data, recipient address, credential, private GIS package,
database, log export or infrastructure secret. Aggregate counts do not identify
a participant or an observation.

The exact private runtime identifier binds this statement to one deployed
revision. Because that revision is not public, the identifier proves record
continuity but does not make Monitor 2 independently reproducible. The public
[`alma-monitor`](https://github.com/plvsovltre-ops/alma-monitor) repository
provides the inspectable v1 source and deployment lineage. Its
[`v1.3.0`](https://github.com/plvsovltre-ops/alma-monitor/releases/tag/v1.3.0)
release records an exact source commit and immutable Cloud Run image digest.

## Interpretation

The verified status is **running closed operational pilot**. It means the
system can receive an authorised field observation, preserve its evidence and
geographic context, apply human-approved Legal Core references, and return a
controlled dossier to an allowed participant. It does not mean unrestricted
public enrolment, automatic legal qualification, proof of guilt, or automatic
submission to a state authority.
