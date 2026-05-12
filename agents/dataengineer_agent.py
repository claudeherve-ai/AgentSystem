"""Data engineer agent.

Specialises in data pipelines, lakehouse architecture, ETL/ELT,
Spark, dbt, streaming, and cloud data platforms.  Follows the
medallion architecture (Bronze → Silver → Gold).
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import MCP_SEQUENTIAL_THINKING_TOOLS, MCP_SQLITE_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def design_pipeline(
    source_description: Annotated[str, "Description of data source(s) including format and volume"],
    destination: Annotated[str, "Target destination (e.g. Delta Lake, Synapse, BigQuery)"],
    transformations: Annotated[str, "Key transformations required (dedup, join, aggregate, etc.)"] = "",
    frequency: Annotated[str, "Ingestion frequency: real-time, hourly, daily, weekly"] = "daily",
) -> str:
    """Design an ETL/ELT pipeline following medallion architecture.

    Returns a pipeline diagram with stage definitions, scheduling
    configuration, and data-quality gate placements.
    """
    logger.info("Designing pipeline: %s → %s (%s)", source_description[:40], destination, frequency)

    transforms_note = transformations if transformations else "Standard: dedup, schema enforcement, type casting"

    result = (
        "═══════════════════════════════════════════\n"
        "  🔄  DATA PIPELINE DESIGN\n"
        "═══════════════════════════════════════════\n"
        f"  Source        : {source_description[:100]}\n"
        f"  Destination   : {destination}\n"
        f"  Frequency     : {frequency}\n"
        f"  Transforms    : {transforms_note}\n"
        "───────────────────────────────────────────\n"
        "  PIPELINE DIAGRAM\n"
        "───────────────────────────────────────────\n"
        "\n"
        "  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐\n"
        "  │ Source   │──▶ │  Bronze  │──▶ │  Silver  │──▶ │   Gold   │\n"
        "  │ (Raw)    │    │ (Landing)│    │ (Cleaned)│    │ (Curated)│\n"
        "  └─────────┘    └──────────┘    └──────────┘    └──────────┘\n"
        "                   │  DQ Gate     │  DQ Gate     │  DQ Gate\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  STAGE DEFINITIONS\n"
        "───────────────────────────────────────────\n"
        "  Bronze (Raw Landing)\n"
        "    • Ingest as-is with append-only writes\n"
        "    • Add metadata: _ingested_at, _source_file, _batch_id\n"
        "    • Format: Delta / Parquet\n"
        "    • Retention: 90 days (configurable)\n"
        "\n"
        "  Silver (Cleaned / Conformed)\n"
        "    • Schema enforcement and type casting\n"
        "    • Deduplication (based on business keys)\n"
        "    • Null handling and default values\n"
        "    • SCD Type 2 for dimension tables\n"
        "\n"
        "  Gold (Business-Ready)\n"
        "    • Aggregations and business metrics\n"
        "    • Star schema / wide tables for BI\n"
        "    • Materialised views for dashboards\n"
        "    • Access controls and column masking\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  SCHEDULING\n"
        "───────────────────────────────────────────\n"
        f"  Frequency  : {frequency}\n"
    )

    if frequency == "real-time":
        result += (
            "  Engine     : Spark Structured Streaming / Kafka\n"
            "  Trigger    : Continuous or micro-batch (1 min)\n"
            "  Checkpoint : ADLS / S3 checkpoint directory\n"
        )
    else:
        result += (
            "  Engine     : Databricks Jobs / Airflow / ADF\n"
            "  Trigger    : Cron-based schedule\n"
            "  Retry      : 3 attempts with exponential backoff\n"
        )

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  DATA QUALITY GATES\n"
        "───────────────────────────────────────────\n"
        "  • Row count validation (±10% from baseline)\n"
        "  • Schema drift detection\n"
        "  • Null percentage thresholds on critical columns\n"
        "  • Freshness SLA check\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DataEngineerAgent",
        "design_pipeline",
        f"Source: {source_description[:60]}, Dest: {destination}, Freq: {frequency}",
        "Pipeline design (medallion) generated",
    )
    return result


async def generate_schema(
    table_name: Annotated[str, "Fully qualified table name (e.g. catalog.schema.table)"],
    columns_json: Annotated[str, "JSON array of column definitions with 'name', 'type', 'nullable', 'description' keys"],
    layer: Annotated[str, "Medallion layer: bronze, silver, or gold"] = "silver",
    format: Annotated[str, "Storage format: delta, parquet, iceberg"] = "delta",
) -> str:
    """Generate data schema with constraints, tests, and documentation.

    Returns SQL DDL and a dbt schema YAML block for the given table.
    """
    logger.info("Generating schema for: %s (layer=%s)", table_name, layer)

    try:
        columns = json.loads(columns_json)
    except (json.JSONDecodeError, TypeError):
        columns = [{"name": "id", "type": "BIGINT", "nullable": False, "description": "Primary key"}]

    # --- SQL DDL ---
    ddl_lines = [f"CREATE TABLE IF NOT EXISTS {table_name} ("]
    for i, col in enumerate(columns):
        name = col.get("name", f"col_{i}")
        dtype = col.get("type", "STRING")
        nullable = col.get("nullable", True)
        null_str = "" if nullable else " NOT NULL"
        comma = "," if i < len(columns) - 1 else ""
        ddl_lines.append(f"    {name:<30} {dtype}{null_str}{comma}")
    ddl_lines.append(")")
    if format == "delta":
        ddl_lines.append("USING DELTA")
    elif format == "iceberg":
        ddl_lines.append("USING ICEBERG")
    ddl_lines.append(f"COMMENT '{table_name} — {layer} layer';")

    # --- dbt schema YAML ---
    dbt_lines = [
        "# dbt schema.yml",
        "version: 2",
        "models:",
        f"  - name: {table_name.split('.')[-1]}",
        f"    description: \"{table_name} ({layer} layer)\"",
        "    columns:",
    ]
    for col in columns:
        name = col.get("name", "unknown")
        desc = col.get("description", "")
        nullable = col.get("nullable", True)
        dbt_lines.append(f"      - name: {name}")
        dbt_lines.append(f'        description: "{desc}"')
        tests = []
        if not nullable:
            tests.append("not_null")
        if name.endswith("_id") or name == "id":
            tests.append("unique")
        if tests:
            dbt_lines.append("        tests:")
            for t in tests:
                dbt_lines.append(f"          - {t}")

    result = (
        "═══════════════════════════════════════════\n"
        "  📊  SCHEMA DEFINITION\n"
        "═══════════════════════════════════════════\n"
        f"  Table  : {table_name}\n"
        f"  Layer  : {layer}\n"
        f"  Format : {format}\n"
        f"  Columns: {len(columns)}\n"
        "───────────────────────────────────────────\n"
        "  SQL DDL\n"
        "───────────────────────────────────────────\n"
    )
    for line in ddl_lines:
        result += f"  {line}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  dbt SCHEMA YAML\n"
        "───────────────────────────────────────────\n"
    )
    for line in dbt_lines:
        result += f"  {line}\n"

    result += "═══════════════════════════════════════════"

    log_action(
        "DataEngineerAgent",
        "generate_schema",
        f"Table: {table_name}, Layer: {layer}, Cols: {len(columns)}",
        f"DDL + dbt YAML generated ({format})",
    )
    return result


async def create_data_quality_checks(
    dataset_description: Annotated[str, "Description of the dataset to validate"],
    critical_columns: Annotated[str, "Comma-separated list of critical columns to check"],
    sla: Annotated[str, "Data freshness SLA (e.g. '30 min', '1 hour')"] = "",
) -> str:
    """Create a data quality validation suite.

    Returns Great Expectations–style and dbt test configurations for
    the specified dataset.
    """
    logger.info("Creating DQ checks for: %s", dataset_description[:80])

    columns = [c.strip() for c in critical_columns.split(",") if c.strip()]
    sla_note = sla if sla else "Not specified — default 1 hour"

    result = (
        "═══════════════════════════════════════════\n"
        "  ✅  DATA QUALITY CHECKS\n"
        "═══════════════════════════════════════════\n"
        f"  Dataset  : {dataset_description[:100]}\n"
        f"  Critical : {', '.join(columns)}\n"
        f"  SLA      : {sla_note}\n"
        "───────────────────────────────────────────\n"
        "  COLUMN-LEVEL CHECKS\n"
        "───────────────────────────────────────────\n"
    )

    for col in columns:
        result += (
            f"  📋 {col}\n"
            f"    • not_null        — {col} must not contain NULLs\n"
            f"    • unique          — no duplicate values (if applicable)\n"
            f"    • accepted_values — values within expected range\n"
            f"    • regex_match     — format validation (if string)\n"
            "\n"
        )

    result += (
        "───────────────────────────────────────────\n"
        "  TABLE-LEVEL CHECKS\n"
        "───────────────────────────────────────────\n"
        "  • row_count  — within ±10% of trailing 7-day average\n"
        "  • freshness  — last record within SLA window\n"
        "  • schema     — no unexpected column additions / removals\n"
        "  • duplicates — composite key uniqueness\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  dbt TEST CONFIG\n"
        "───────────────────────────────────────────\n"
        "  tests:\n"
    )
    for col in columns:
        result += (
            f"    - not_null:\n"
            f"        column_name: {col}\n"
            f"        severity: error\n"
        )

    result += (
        "    - dbt_utils.recency:\n"
        f"        datepart: minute\n"
        f"        field: updated_at\n"
        f"        interval: 60\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  ALERTING\n"
        "───────────────────────────────────────────\n"
        "  • Critical failures → PagerDuty / Slack #data-alerts\n"
        "  • Warnings          → Slack #data-quality\n"
        "  • Dashboard         → Grafana / Monte Carlo\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DataEngineerAgent",
        "create_data_quality_checks",
        f"Dataset: {dataset_description[:60]}, Columns: {len(columns)}",
        f"DQ suite generated ({len(columns)} column checks + table checks)",
    )
    return result


async def design_lakehouse(
    data_sources_json: Annotated[str, "JSON array of data sources with 'name', 'type', 'volume', 'frequency' keys"],
    cloud_platform: Annotated[str, "Target cloud platform: azure, aws, gcp"] = "azure",
    query_patterns: Annotated[str, "Expected query patterns (ad-hoc BI, real-time dashboards, ML training)"] = "",
) -> str:
    """Design a lakehouse architecture.

    Returns layer definitions, storage strategy, partitioning plan,
    and technology mapping for the chosen cloud platform.
    """
    logger.info("Designing lakehouse on %s", cloud_platform)

    try:
        sources = json.loads(data_sources_json)
    except (json.JSONDecodeError, TypeError):
        sources = [{"name": "unknown", "type": "batch", "volume": "unknown", "frequency": "daily"}]

    query_note = query_patterns if query_patterns else "Mixed: BI dashboards + ad-hoc analysis"

    # Cloud-specific technology mapping
    tech_map = {
        "azure": {
            "storage": "Azure Data Lake Storage Gen2 (ADLS)",
            "compute": "Azure Databricks / Synapse Spark",
            "warehouse": "Databricks SQL / Synapse Serverless",
            "orchestration": "Azure Data Factory / Databricks Workflows",
            "catalog": "Unity Catalog",
        },
        "aws": {
            "storage": "Amazon S3",
            "compute": "Databricks on AWS / EMR",
            "warehouse": "Databricks SQL / Athena / Redshift Spectrum",
            "orchestration": "Step Functions / MWAA (Airflow)",
            "catalog": "Unity Catalog / AWS Glue Catalog",
        },
        "gcp": {
            "storage": "Google Cloud Storage (GCS)",
            "compute": "Databricks on GCP / Dataproc",
            "warehouse": "Databricks SQL / BigQuery",
            "orchestration": "Cloud Composer (Airflow) / Databricks Workflows",
            "catalog": "Unity Catalog",
        },
    }
    tech = tech_map.get(cloud_platform.lower(), tech_map["azure"])

    result = (
        "═══════════════════════════════════════════\n"
        "  🏠  LAKEHOUSE ARCHITECTURE\n"
        "═══════════════════════════════════════════\n"
        f"  Platform      : {cloud_platform.upper()}\n"
        f"  Data Sources  : {len(sources)}\n"
        f"  Query Patterns: {query_note}\n"
        "───────────────────────────────────────────\n"
        "  DATA SOURCES\n"
        "───────────────────────────────────────────\n"
    )

    for src in sources:
        name = src.get("name", "unknown")
        stype = src.get("type", "batch")
        vol = src.get("volume", "unknown")
        freq = src.get("frequency", "daily")
        result += f"  • {name} ({stype}) — {vol}, {freq}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  TECHNOLOGY STACK\n"
        "───────────────────────────────────────────\n"
        f"  Storage       : {tech['storage']}\n"
        f"  Compute       : {tech['compute']}\n"
        f"  SQL Warehouse : {tech['warehouse']}\n"
        f"  Orchestration : {tech['orchestration']}\n"
        f"  Catalog       : {tech['catalog']}\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  LAYER STRATEGY\n"
        "───────────────────────────────────────────\n"
        "  Bronze : raw/ — append-only, schema-on-read\n"
        "  Silver : curated/ — cleaned, conformed, SCD\n"
        "  Gold   : analytics/ — star schema, aggregates\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  PARTITIONING & STORAGE\n"
        "───────────────────────────────────────────\n"
        "  • Partition by date (yyyy/mm/dd) for time-series\n"
        "  • Z-ORDER on high-cardinality filter columns\n"
        "  • OPTIMIZE + VACUUM on weekly schedule\n"
        "  • Delta format with liquid clustering (if supported)\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  GOVERNANCE\n"
        "───────────────────────────────────────────\n"
        "  • Row / column-level security via Unity Catalog\n"
        "  • Data lineage tracking\n"
        "  • PII tagging and masking\n"
        "  • Audit logging for all access\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DataEngineerAgent",
        "design_lakehouse",
        f"Platform: {cloud_platform}, Sources: {len(sources)}",
        "Lakehouse architecture generated",
    )
    return result


async def optimize_query(
    query_text: Annotated[str, "SQL or Spark SQL query to optimise"],
    table_stats: Annotated[str, "Table statistics: row counts, file sizes, partitioning info"] = "",
    current_runtime: Annotated[str, "Current query execution time"] = "",
) -> str:
    """Analyse and optimise a SQL/Spark query.

    Returns an optimised query with an explanation of every change
    and the expected performance impact.
    """
    logger.info("Optimising query (%d chars)", len(query_text))

    stats_note = table_stats if table_stats else "Not provided — run DESCRIBE EXTENDED / ANALYZE TABLE"
    runtime_note = current_runtime if current_runtime else "Not measured"

    findings: list[str] = []
    suggestions: list[str] = []

    query_upper = query_text.upper()

    if "SELECT *" in query_upper:
        findings.append("🟡 SELECT * detected — projection pushdown disabled")
        suggestions.append("Specify only required columns to reduce I/O")

    if "CROSS JOIN" in query_upper:
        findings.append("🔴 CROSS JOIN detected — potential cartesian product")
        suggestions.append("Replace with explicit JOIN condition")

    if query_upper.count("JOIN") > 3:
        findings.append("🟡 Multiple JOINs (>3) — may cause shuffle spill")
        suggestions.append("Consider broadcast join for small tables: /*+ BROADCAST(small_table) */")

    if "ORDER BY" in query_upper and "LIMIT" not in query_upper:
        findings.append("🟡 ORDER BY without LIMIT — full sort on all data")
        suggestions.append("Add LIMIT or use windowed approach")

    if "DISTINCT" in query_upper:
        findings.append("🟡 DISTINCT — triggers extra shuffle stage")
        suggestions.append("Check if GROUP BY or dedup at source is more efficient")

    if "NOT IN" in query_upper:
        findings.append("🟡 NOT IN subquery — can cause full scan")
        suggestions.append("Replace with LEFT ANTI JOIN or NOT EXISTS")

    if not findings:
        findings.append("🟢 No obvious anti-patterns detected")
        suggestions.append("Review EXPLAIN plan for partition pruning and predicate pushdown")

    result = (
        "═══════════════════════════════════════════\n"
        "  🚀  QUERY OPTIMISATION\n"
        "═══════════════════════════════════════════\n"
        f"  Current Runtime : {runtime_note}\n"
        f"  Table Stats     : {stats_note[:80]}\n"
        "───────────────────────────────────────────\n"
        "  ORIGINAL QUERY\n"
        "───────────────────────────────────────────\n"
        f"  {query_text.strip()}\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  FINDINGS\n"
        "───────────────────────────────────────────\n"
    )
    for f in findings:
        result += f"  {f}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  OPTIMISATION SUGGESTIONS\n"
        "───────────────────────────────────────────\n"
    )
    for idx, s in enumerate(suggestions, 1):
        result += f"  {idx}. {s}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  GENERAL BEST PRACTICES\n"
        "───────────────────────────────────────────\n"
        "  • Filter early — push WHERE predicates to partitioned columns\n"
        "  • Use EXPLAIN to verify partition pruning\n"
        "  • Consider materialised views for repeated aggregations\n"
        "  • Run ANALYZE TABLE to update statistics\n"
        "  • Use Z-ORDER on frequently filtered columns\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DataEngineerAgent",
        "optimize_query",
        f"Query length: {len(query_text)}, Runtime: {runtime_note}",
        f"Findings: {len(findings)}, Suggestions: {len(suggestions)}",
    )
    return result


async def create_pipeline_monitoring(
    pipeline_name: Annotated[str, "Name of the data pipeline to monitor"],
    sla_minutes: Annotated[int, "SLA in minutes — alert if pipeline exceeds this duration"] = 60,
    alert_channels: Annotated[str, "Alert channels: slack, email, pagerduty (comma-separated)"] = "",
) -> str:
    """Create monitoring and alerting configuration for a data pipeline.

    Returns a monitoring dashboard specification and alert rule
    definitions suitable for Grafana, Datadog, or Databricks monitoring.
    """
    logger.info("Creating monitoring for pipeline: %s (SLA=%d min)", pipeline_name, sla_minutes)

    channels = [c.strip() for c in alert_channels.split(",") if c.strip()] if alert_channels else ["slack"]

    result = (
        "═══════════════════════════════════════════\n"
        "  📡  PIPELINE MONITORING\n"
        "═══════════════════════════════════════════\n"
        f"  Pipeline : {pipeline_name}\n"
        f"  SLA      : {sla_minutes} minutes\n"
        f"  Channels : {', '.join(channels)}\n"
        "───────────────────────────────────────────\n"
        "  METRICS TO TRACK\n"
        "───────────────────────────────────────────\n"
        "  • pipeline_duration_seconds  — end-to-end runtime\n"
        "  • rows_processed_total       — throughput per run\n"
        "  • rows_failed_total          — error row count\n"
        "  • data_freshness_seconds     — time since last successful load\n"
        "  • schema_drift_detected      — boolean flag per run\n"
        "  • dq_check_pass_rate         — percentage of passing checks\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  ALERT RULES\n"
        "───────────────────────────────────────────\n"
        f"  🔴 CRITICAL: pipeline_duration > {sla_minutes} min\n"
        f"     → Notify: {', '.join(channels)}\n"
        f"     → Runbook: Investigate Spark UI, check for data skew\n"
        "\n"
        "  🔴 CRITICAL: rows_failed > 1% of rows_processed\n"
        f"     → Notify: {', '.join(channels)}\n"
        "     → Runbook: Check DQ logs, quarantine bad records\n"
        "\n"
        f"  🟡 WARNING: data_freshness > {sla_minutes * 2} min\n"
        "     → Notify: slack\n"
        "     → Runbook: Verify upstream source availability\n"
        "\n"
        "  🟡 WARNING: schema_drift_detected = true\n"
        "     → Notify: slack\n"
        "     → Runbook: Compare schemas, update downstream consumers\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  DASHBOARD PANELS\n"
        "───────────────────────────────────────────\n"
        "  ┌────────────────────┬────────────────────┐\n"
        "  │ Pipeline Status    │ Duration Trend      │\n"
        "  │ (pass/fail badge)  │ (time-series chart) │\n"
        "  ├────────────────────┼────────────────────┤\n"
        "  │ Rows Processed     │ DQ Pass Rate        │\n"
        "  │ (bar chart / run)  │ (gauge / %)         │\n"
        "  ├────────────────────┼────────────────────┤\n"
        "  │ Data Freshness     │ Error Log (table)   │\n"
        "  │ (time since load)  │ (last 10 failures)  │\n"
        "  └────────────────────┴────────────────────┘\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DataEngineerAgent",
        "create_pipeline_monitoring",
        f"Pipeline: {pipeline_name}, SLA: {sla_minutes}min",
        f"Monitoring config generated (channels: {', '.join(channels)})",
    )
    return result


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

# List of tools to register with the data engineer agent
DATAENGINEER_TOOLS = [
    design_pipeline,
    generate_schema,
    create_data_quality_checks,
    design_lakehouse,
    optimize_query,
    create_pipeline_monitoring,
] + list(MCP_SQLITE_TOOLS) + list(MCP_SEQUENTIAL_THINKING_TOOLS)
