# Operational status and release lineage

Status checked: **4 September 2026**.

ALMA is a launched controlled field system. It is not currently represented as
an unrestricted mass public service. These statements describe different
boundaries and must not be collapsed into a single "launched/not launched"
label.

## Status by system boundary

| Boundary | Status | Public evidence |
| --- | --- | --- |
| `alma.eco` map and archive | Publicly available information surface | [Public website](https://alma.eco/), [map](https://alma.eco/#map), and [archive](https://alma.eco/#archive) |
| Early `alma_bot` automation | Launched closed-pilot lineage | [Scheduled workflow introduced on 21 December 2025](https://github.com/plvsovltre-ops/alma-monitor/commit/0bb23be12d8402f807cb195d54cbab0af2bb967a) |
| ALMA Monitor v1 cloud worker | Deployed closed operational pilot | [Cloud Run deployment commit of 10 August 2026](https://github.com/plvsovltre-ops/alma-monitor/commit/859a125862a7a0ba32e3d57571c4035fc716b626) |
| ALMA Monitor 1.3.0 | Released human-response and controlled legal-reference path | [Release v1.3.0](https://github.com/plvsovltre-ops/alma-monitor/releases/tag/v1.3.0), including an immutable image digest |
| ALMA Monitor 1.3.1 | Released deterministic field-quality notices | [Release v1.3.1](https://github.com/plvsovltre-ops/alma-monitor/releases/tag/v1.3.1) |
| Public Legal Core v1 overlay | Approved as an exact hash-bound package | [`decision.json`](../governance/public/kz/0.1.0-rc1/decision.json) and the confidentially attributable [`independent_review.json`](../governance/public/kz/0.1.0-rc1/independent_review.json) |
| ALMA Monitor 2 | Running closed successor pilot with scheduled delivery and active reliability controls | [Publication-safe operational evidence, 4 September 2026](OPERATIONAL_EVIDENCE_2026-09-04.md); its current server configuration and working data remain private and are not reproduced by this v1 repository |
| Unrestricted mass public service | Not claimed | The public-service gates remain in the [public release checklist](PUBLIC_RELEASE_CHECKLIST.md) |

## What “launched” means

The closed operational pilot receives observations from a private Mergin Maps
project, checks evidence and spatial context, applies deterministic Legal Core
rules, and returns a result to an allowed participant. A closed pilot is a real
deployment. Restricted access is an intentional safety boundary for personal
data, sensitive locations, legal references, and delivery controls.

It does **not** mean that anyone can enrol without approval, that ALMA determines
a violation or guilt, or that it submits a request to a state authority.

## Current successor boundary

As of the status date, the operator has verified the ALMA Monitor 2 controlled
pilot with the following boundary:

- a private Mergin Maps source and a scheduled server worker;
- bounded processing and delivery to an allowlisted participant;
- deterministic GIS context and an active 20-card Legal Core release;
- Russian or Kazakh presentation selected from the observation;
- a complete evidence dossier, including controlled photo attachments;
- neutral model-assisted description of visible circumstances only;
- a bounded queue that retains additional observations and processes at most
  one dossier in each scheduled run;
- verified off-host backup, delivery-status monitoring, reliability inspection,
  and a bounded watchdog for the scheduler;
- no model selection of law, article, topic, competent authority, or guilt;
- no automatic submission to a state authority.

The latest production verification found the bounded backlog empty, recorded
five successful pilot deliveries in the durable delivery state, and confirmed
that all current production timers were scheduled. These are aggregate
operational facts, not publication of any observation or recipient. The exact
scope, timestamp and limits of this check are recorded in
[`OPERATIONAL_EVIDENCE_2026-09-04.md`](OPERATIONAL_EVIDENCE_2026-09-04.md).

This is an operator status statement: Monitor 2 is running in a controlled
private pilot. The statement does not claim that its private runtime can be
rebuilt from this v1 repository. A future public Monitor 2 source release must
identify its own exact source commit, image digest, governed data packages, and
deployment boundary.

## Repository scope

This repository is public evidence of the ALMA Monitor v1 development and
deployment lineage and contains public governance artifacts. Its current
[`Dockerfile`](../Dockerfile) runs `main.py` and includes reviewed catalogs,
Legal Core, and governance files. It does not include `app.py` or `laws/` in the
runtime image.

`app.py` and `laws/` are retained only as historical pre-Legal-Core research
materials. They must not be deployed or cited as the current legal-reference
mechanism. Current legal references come only from exact, human-reviewed Legal
Core cards and deterministic mappings.

## Canonical status statement

> ALMA is a launched controlled field infrastructure initiated and originally
> designed by Yernar Sailybayev in Almaty, Kazakhstan. ALMA Monitor 2 is its
> next-generation hardening, not evidence that the earlier system did not work.
> An unrestricted mass public service is not currently claimed.
