# Problem Solving Skill

## Methodology: Systematic Debugging Framework

### Phase 1 — Observe
- Read the FULL error message, not just the first line
- Identify: error type, stack trace origin, trigger conditions
- Note: when did it start? What changed recently?
- Collect: logs, metrics, reproduction steps

### Phase 2 — Hypothesize
- Rank hypotheses by likelihood (most common cause first)
- Consider: configuration, dependency, permission, network, data, code
- Check: has this been seen before? (GitHub Issues, Stack Overflow)
- Eliminate: what HASN'T changed?

### Phase 3 — Test
- One variable at a time
- Use bisection for large changesets
- Verify with minimal reproduction case
- Document each test and result

### Phase 4 — Resolve
- Apply the minimal fix
- Verify the fix doesn't break other things
- Document root cause and resolution
- Add prevention (tests, validation, monitoring)

## Research Sources Priority
1. Official documentation
2. GitHub Issues (exact error message search)
3. Stack Overflow (with version-specific filtering)
4. Community forums and blogs
5. Source code inspection

## Anti-Patterns to Avoid
- Guessing without evidence
- Changing multiple things at once
- Ignoring the stack trace
- Assuming the obvious cause
- Not testing the fix in isolation
