# Software Architecture Skill

## Design Principles
- No architecture astronautics — every abstraction must justify its complexity
- Trade-offs over best practices — name what you're giving up
- Domain first, technology second
- Reversibility matters — prefer easy-to-change decisions
- Document decisions (ADRs), not just designs

## Architecture Selection
| Pattern | Use When | Avoid When |
|---------|----------|------------|
| Modular monolith | Small team, unclear boundaries | Independent scaling needed |
| Microservices | Clear domains, team autonomy | Small team, early-stage product |
| Event-driven | Loose coupling, async workflows | Strong consistency required |
| CQRS | Read/write asymmetry | Simple CRUD domains |

## Domain-Driven Design
1. Event storming for bounded context discovery
2. Aggregate boundaries and invariants
3. Context mapping (upstream/downstream, anti-corruption layer)
4. Domain events and commands
