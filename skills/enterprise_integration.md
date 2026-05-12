# Enterprise Integration Skill

## Integration Patterns

### Event-Driven (Preferred)
- Use webhooks for real-time sync
- Implement idempotent handlers
- Dead letter queue for failed events
- Schema versioning for payload evolution

### API-Based (Request/Response)
- RESTful for CRUD operations
- GraphQL for complex queries
- gRPC for high-performance internal services
- Rate limiting and backoff strategies

### Batch/ETL
- Scheduled jobs for large data volumes
- Change Data Capture (CDC) for incremental sync
- Data validation at ingestion point
- Reconciliation reports

## Common Enterprise Systems

### Salesforce
- REST API v58+ / Bulk API 2.0
- OAuth 2.0 with refresh tokens
- Trigger-based outbound messages
- Key objects: Account, Contact, Opportunity, Lead, Case

### Microsoft 365
- Microsoft Graph API
- OAuth 2.0 with admin consent
- Webhooks for change notifications
- Key APIs: Mail, Calendar, Files, Teams

### HubSpot
- REST API v3
- OAuth 2.0 or API keys
- Webhook subscriptions
- Key objects: Contacts, Companies, Deals, Tickets

## Security Requirements
- OAuth 2.0 / OpenID Connect
- API key rotation policy
- Data encryption in transit (TLS 1.3)
- PII handling per GDPR/CCPA
- Audit logging of all data access
- IP allowlisting where possible

## Data Mapping Best Practices
- Define canonical data model
- Map field-by-field with transformations
- Handle nulls and defaults explicitly
- Version your mappings
- Test with production-like data
