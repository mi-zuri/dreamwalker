# infra

Populated in Phase 8.

- `Dockerfile.backend` / `Dockerfile.ingest` - Cloud Run service and ingest job images
- `cloudrun/` - service + job YAML, Cloud Scheduler bindings
- `terraform/` - project, Firestore, Cloud Storage, Secret Manager, IAM
- `scripts/` - deploy, and the authenticated manual trigger for the news ingest job
