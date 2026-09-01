# Data-retention policy for deployments

> **Scope:** this is the v1 reference policy. Current Monitor 2 archive and
> verified rollover controls are operational controls outside this public v1
> source tree. They do not replace the need for an approved retention schedule
> before unrestricted public collection.

The repository has no production field data. In a deployed ALMA Monitor:

- the downloaded Mergin project is temporary working data for one job;
- incident state and delivery evidence are kept in private Cloud Storage;
- completed summaries may be kept in a restricted Google Sheet;
- service logs are kept according to the cloud project's logging policy;
- the authoritative field record remains subject to the Mergin project policy.

## Verified archive rollover

> **Monitor 2 operational control — not implemented by the v1 reference worker.**

Archiving does not discard the evidence dossier. Before any Mergin media is
removed, the original photographs and other evidence are copied to the private
EvidenceStorage with their observation ID, MIME type, size and SHA-256 manifest.
A restore test must successfully reconstruct the originals before deletion is
allowed. Email is a delivery channel, not an archive.

After a verified rollover, the active Mergin project keeps a lightweight,
read-only point layer containing the observation ID, time, topics and archive
status. This preserves the map and the link to the archived dossier without
keeping every photograph in the active project. A partial archive, missing
object or unknown path blocks deletion and requires operator review.

The reference code does not yet erase durable incident state or registry rows
automatically. Before allowing public data collection, the operator must approve
and enforce concrete retention periods, access roles, backup rules, and a tested
deletion process. Until that control exists, do not promise automatic deletion.

Deletion must preserve only the minimum audit information required by applicable
law and an approved operational policy. A deletion request must also be checked
against copies held by configured processors and against any legal preservation
obligation.
