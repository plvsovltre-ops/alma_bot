# Historical legal research notes

The text files in this directory belong to the pre-Legal-Core prototype. They
are retained to preserve the development record. They are not approved Legal
Core cards, not legal advice, and not inputs to the current ALMA Monitor runtime.

Some files contain early categorical commentary about an alleged violation,
remedy, or legal consequence. That commentary is superseded by the current
fail-closed design and must not be treated as an ALMA finding.

Current legal-reference rules are stricter:

1. A language model does not select a law or article.
2. A reference can come only from an exact, human-reviewed Legal Core card and
   deterministic mapping.
3. An unknown circumstance remains unknown.
4. ALMA does not determine a violation, guilt, ownership, or final legal
   qualification.
5. A draft asks the competent authority to verify facts; it is not submitted
   automatically.

The production [`Dockerfile`](../Dockerfile) intentionally excludes this
directory.
