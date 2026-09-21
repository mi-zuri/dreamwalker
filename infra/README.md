# infra

```
Dockerfile              one image: the API, with the built frontend inside it
cloudbuild.yaml         how that image gets built (on Cloud Build, not locally)
scripts/deploy.sh       build, roll out, check it answers
terraform/              the project: registry, identity, secret, service, alerts
```

Deploy:

```bash
brew install opentofu                                    # once per machine
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
$EDITOR terraform/terraform.tfvars
scripts/deploy.sh
```

Everything else — what these resources are, how identity works, the custom
domain, the budget, and what is deliberately not here — is in
[docs/gcp.md](../docs/gcp.md). Creating the project from nothing is
[docs/SETUP.md](../docs/SETUP.md).
