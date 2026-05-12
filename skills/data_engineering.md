# Data Engineering Skill

## Medallion Architecture
- **Bronze**: Raw, immutable, append-only. Never transform in place.
- **Silver**: Cleansed, deduplicated, conformed. Must be joinable across domains.
- **Gold**: Business-ready, aggregated, SLA-backed. Optimized for query patterns.
- Never allow gold consumers to read from Bronze/Silver directly.

## Pipeline Reliability Standards
- All pipelines must be idempotent
- Explicit schema contracts — drift must alert, never silently corrupt
- Null handling must be deliberate
- Soft deletes + audit columns (created_at, updated_at, deleted_at)

## Tools & Platforms
- Apache Spark / PySpark for large-scale processing
- dbt for transformation and testing
- Delta Lake / Iceberg for open table formats
- Great Expectations for data quality
- Azure Fabric / Synapse / ADLS for cloud lakehouse / Databricks / Snowflake
- Kafka
- Apache Iceberg
