"""apps — deployable process entrypoints (api, worker).

These reuse the shared :mod:`api` and :mod:`agentsystem` packages rather than
duplicating logic. Dockerfiles are intentionally NOT included here; the
infrastructure workstream adds them.
"""
