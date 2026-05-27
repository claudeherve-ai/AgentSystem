#!/usr/bin/env bash
# =============================================================================
# build-claude-skills-slim.sh — Build a deterministic, verified slim skill tree
# =============================================================================
# Produces a lean copy of claude-skills for Docker build context.
# ALWAYS produces real skills. NEVER a placeholder. Fails loudly on error.
#
# Usage:
#   ./scripts/build-claude-skills-slim.sh                    # default output: /tmp/acr-build/claude-skills-slim
#   ./scripts/build-claude-skills-slim.sh /path/to/output    # custom output path
#   SOURCE=/path/to/claude-skills ./scripts/build-claude-skills-slim.sh  # custom source
#
# Exit codes:
#   0 — success, verified
#   1 — source not found
#   2 — rsync failed
#   3 — verification failed (no SKILL.md files in output)
# =============================================================================
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
OUTPUT_DIR="${1:-/tmp/acr-build/claude-skills-slim}"
SOURCE="${SOURCE:-/home/tedch/claude-skills}"
MIN_SKILLS="${MIN_SKILLS:-300}"  # minimum SKILL.md files expected (slim subset of full 729)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  build-claude-skills-slim"
echo "  Source:  $SOURCE"
echo "  Output:  $OUTPUT_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Validate source ────────────────────────────────────────────────────────
if [ ! -d "$SOURCE" ]; then
    echo "❌ FATAL: Source not found: $SOURCE"
    exit 1
fi

SOURCE_COUNT=$(find "$SOURCE" -name "SKILL.md" 2>/dev/null | wc -l)
echo "  Source SKILL.md count: $SOURCE_COUNT"

if [ "$SOURCE_COUNT" -lt "$MIN_SKILLS" ]; then
    echo "❌ FATAL: Source has only $SOURCE_COUNT SKILL.md files (minimum: $MIN_SKILLS)"
    exit 1
fi

# ── Prepare output directory ──────────────────────────────────────────────
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# ── Domain directories to include (based on AGENT_SKILL_MAP) ───────────────
# These are the domain directories containing SKILL.md files used by agents.
# We explicitly list them to avoid accidentally including heavy dev-only dirs.
DOMAINS=(
    "engineering"
    "engineering-team"
    "c-level-advisor"
    "marketing-skill"
    "marketing"
    "finance"
    "business-growth"
    "business-operations"
    "commercial"
    "ra-qm-team"
    "product-team"
    "project-management"
    "productivity"
    "research"
    "compliance-os"
    "orchestration"
)

# ── Additional files to copy ──────────────────────────────────────────────
EXTRA_FILES=(
    "CLAUDE.md"
    "README.md"
    "LICENSE"
    "standards"
    ".claude-plugin"
)

# ── Copy domain directories ────────────────────────────────────────────────
echo ""
echo "  Copying domains..."
COPIED=0
SKIPPED=0

for domain in "${DOMAINS[@]}"; do
    if [ -d "$SOURCE/$domain" ]; then
        rsync -a --delete \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.git' \
            --exclude='node_modules' \
            --exclude='.DS_Store' \
            "$SOURCE/$domain/" "$OUTPUT_DIR/$domain/" 2>/dev/null
        echo "    ✅ $domain"
        ((COPIED++)) || true
    else
        echo "    ⚠️  $domain (not found at source, skipping)"
        ((SKIPPED++)) || true
    fi
done

# ── Copy extra files ──────────────────────────────────────────────────────
echo ""
echo "  Copying extra files..."
for extra in "${EXTRA_FILES[@]}"; do
    if [ -e "$SOURCE/$extra" ]; then
        if [ -d "$SOURCE/$extra" ]; then
            rsync -a --delete \
                --exclude='__pycache__' \
                --exclude='*.pyc' \
                "$SOURCE/$extra/" "$OUTPUT_DIR/$extra/" 2>/dev/null
        else
            cp "$SOURCE/$extra" "$OUTPUT_DIR/$extra" 2>/dev/null
        fi
        echo "    ✅ $extra"
    else
        echo "    ⚠️  $extra (not found, skipping)"
    fi
done

# ── Verify output ──────────────────────────────────────────────────────────
echo ""
echo "  Verifying output..."

OUTPUT_COUNT=$(find "$OUTPUT_DIR" -name "SKILL.md" 2>/dev/null | wc -l)
OUTPUT_SIZE=$(du -sh "$OUTPUT_DIR" 2>/dev/null | cut -f1)

echo "    Output SKILL.md count: $OUTPUT_COUNT"
echo "    Output size:           $OUTPUT_SIZE"

if [ "$OUTPUT_COUNT" -lt "$MIN_SKILLS" ]; then
    echo ""
    echo "❌❌❌ VERIFICATION FAILED ❌❌❌"
    echo "  Expected at least $MIN_SKILLS SKILL.md files"
    echo "  Got: $OUTPUT_COUNT"
    echo "  The slim tree is INCOMPLETE. Build aborted."
    exit 3
fi

# ── Create a version manifest ──────────────────────────────────────────────
cat > "$OUTPUT_DIR/.slim-manifest.json" <<EOF
{
    "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "source": "$SOURCE",
    "source_skill_count": $SOURCE_COUNT,
    "slim_skill_count": $OUTPUT_COUNT,
    "slim_size": "$OUTPUT_SIZE",
    "domains_copied": $COPIED,
    "domains_skipped": $SKIPPED
}
EOF

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ SUCCESS — Slim skill tree built"
echo "  $OUTPUT_COUNT SKILL.md files  |  $OUTPUT_SIZE"
echo "  Manifest: $OUTPUT_DIR/.slim-manifest.json"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0