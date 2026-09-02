# Platform independence and replaceable adapters

ALMA uses external services in its current controlled deployment. These
services are adapters around a portable processing boundary; they are not the
source of the Legal Core decisions.

| Component | Current adapter | Open or standard alternative | Evidence status |
| --- | --- | --- | --- |
| Legal Core | ALMA deterministic catalogs and mappings | No replacement required | Confirmed: references come only from reviewed cards |
| Observation source | Mergin Maps API and project package | GeoPackage/JSON fixture, QField, PostGIS | Alternative input contract documented; production adapter not yet claimed |
| Evidence storage | Google Cloud Storage | S3-compatible storage, including MinIO | Blob and manifest boundary is portable; alternative deployment requires verification |
| Visual description | Gemini API | Open-weight model or local inference with the same neutral-description contract | Contract is defined; an alternative model is not represented as production-tested |
| Delivery | SMTP2GO | Any standards-compliant SMTP relay | Portable through SMTP configuration |

The portable core is the sequence that validates evidence, resolves spatial
context, applies human-reviewed Legal Core mappings, and builds a request for
official fact-checking. A model does not select legal provisions, an authority,
or a legal conclusion. Replacing a service adapter must not change that core
boundary.

This document distinguishes three claims:

1. an interface is narrow enough to permit replacement;
2. an offline alternative has passed a contract test;
3. an alternative is deployed in production.

ALMA currently makes the first claim for the observation, storage, visual
description and delivery boundaries. The closed Monitor 2 pilot is the
operational reference; it does not claim that every listed alternative is
production-ready. A future portable release must publish its adapter,
dependency licenses, reproducible test result and exact deployment boundary.

The current Mergin Maps and Gemini integrations remain intentional pilot
choices. Their use does not make the Legal Core proprietary or transferable to
another provider; it does mean that a complete independent deployment requires
the corresponding open adapter and an evidence-preserving contract test.
