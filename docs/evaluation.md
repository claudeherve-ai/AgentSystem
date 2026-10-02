# Evaluation strategy

The repository has an offline evaluation suite (`python -m evals.run`) and
tests. Online LLM-judged metrics are optional and must not require credentials
in CI. The deployment target adds versioned datasets and sampled production
trace evaluation.

## Release gates

For each agent/routing change, evaluate routing choice, tool selection, task
completion, groundedness/citation quality where applicable, safety, latency,
and cost against a versioned representative dataset. Compare against the
previous approved baseline. Define a metric threshold and a no-regression rule
before changing prompts, models, tools, or routing policies.

CI runs deterministic tests and offline evaluations only. Production samples
must be consented, privacy-filtered, access-controlled, retained for a defined
period, and never copied into source control or public issues.

## Operational monitoring

Track success/abandonment, approval outcomes, tool failures, safety denials,
groundedness defects, p50/p95 latency, token use, and estimated cost by agent
and release. Slice signals by tenant only in access-controlled systems and
avoid sensitive prompt content in telemetry. Alert on a statistically
meaningful regression, then pause promotion, reproduce with the versioned
dataset, and roll back the model/prompt/route or deployment revision.
