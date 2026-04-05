# langchain_service

Minimal deployable project for the LangChain sample app.

Build from the repository root:

```bash
docker build -f projects/langchain_service/Dockerfile -t xagent-langchain-service .
```

Install locally with Helm:

```bash
helm upgrade --install langchain-service deploy/langchain-service \
  --namespace xagent \
  --create-namespace \
  -f deploy/langchain-service/values-kind.yaml \
  --set image.repository=xagent-langchain-service \
  --set image.tag=latest \
  --set secret.name=openai-api \
  --set secret.openaiApiKey="$OPENAI_API_KEY"
```

The chart renders a single `config.yaml` from `.Values.appConfig`, mounts it into the
container, and starts the service with:

```text
--config /app/config/config.yaml
```

This matches the application entrypoint behavior exactly. Secrets such as
`OPENAI_API_KEY` should still come from Kubernetes secrets or External Secrets Operator,
because runtime environment variables have higher precedence than the config file.

Environment-specific values files:

- `deploy/langchain-service/values-kind.yaml`: local `kind` testing, chart-managed secret creation.
- `deploy/langchain-service/values-dev.yaml`: shared development cluster defaults with `ExternalSecret` integration.
- `deploy/langchain-service/values-prod.yaml`: production-oriented defaults with `ExternalSecret` integration and higher replica count.

Secret management best practice:

- Use a secret manager such as AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault.
- Sync only the specific app secret into Kubernetes through External Secrets Operator.
- Prefer workload identity or IAM role based auth for ESO itself instead of long-lived cloud credentials in Kubernetes secrets.
- Keep application configuration in the `ConfigMap`, and keep credentials in a single Kubernetes secret consumed through `envFrom`.
- Avoid storing production API keys directly in Helm values or committing sealed secret payloads into this repo.
- Prefer keeping `.Values.appConfig` for non-secret hierarchical application settings only.

The chart supports three secret modes:

- Local: `secret.create=true` for disposable `kind` testing only.
- Existing secret: `secret.create=false` and `externalSecret.enabled=false` when another system creates the Kubernetes secret.
- Recommended cluster mode: `externalSecret.enabled=true` and point the chart at a `SecretStore` or `ClusterSecretStore`.

Examples:

```bash
helm upgrade --install langchain-service deploy/langchain-service \
  --namespace xagent-dev \
  --create-namespace \
  -f deploy/langchain-service/values-dev.yaml \
  --set image.repository=xagent-langchain-service \
  --set image.tag=latest
```

```bash
helm upgrade --install langchain-service deploy/langchain-service \
  --namespace xagent-prod \
  --create-namespace \
  -f deploy/langchain-service/values-prod.yaml \
  --set image.repository=registry.example.com/xagent-langchain-service \
  --set image.tag=2026-04-05
```

Example External Secrets Operator override:

```bash
helm upgrade --install langchain-service deploy/langchain-service \
  --namespace xagent-prod \
  --create-namespace \
  -f deploy/langchain-service/values-prod.yaml \
  --set image.repository=registry.example.com/xagent-langchain-service \
  --set image.tag=2026-04-05 \
  --set externalSecret.secretStoreRef.name=team-secrets \
  --set externalSecret.data.openaiApiKey.key=xagent/prod/langchain-service \
  --set externalSecret.data.openaiApiKey.property=OPENAI_API_KEY
```

Provider examples:

- AWS Secrets Manager `ClusterSecretStore`: [aws-clustersecretstore-secretsmanager.yaml](/home/xuelin/work/xagent-p/deploy/langchain-service/examples/aws-clustersecretstore-secretsmanager.yaml)
- AWS Secrets Manager `SecretStore`: [aws-secretstore-secretsmanager.yaml](/home/xuelin/work/xagent-p/deploy/langchain-service/examples/aws-secretstore-secretsmanager.yaml)
- GCP Secret Manager `ClusterSecretStore`: [gcp-clustersecretstore-secretmanager.yaml](/home/xuelin/work/xagent-p/deploy/langchain-service/examples/gcp-clustersecretstore-secretmanager.yaml)
- GCP Secret Manager `SecretStore`: [gcp-secretstore-secretmanager.yaml](/home/xuelin/work/xagent-p/deploy/langchain-service/examples/gcp-secretstore-secretmanager.yaml)
- Nested secret mapping example values: [nested-secret-values-example.yaml](/home/xuelin/work/xagent-p/deploy/langchain-service/examples/nested-secret-values-example.yaml)

AWS example flow:

1. Create an IAM role with access only to the relevant Secrets Manager paths or ARNs.
2. Bind ESO to that role using IRSA, EKS Pod Identity, or another AWS workload identity mechanism.
3. Apply one of the AWS store manifests.
4. Deploy the chart with:

```bash
helm upgrade --install langchain-service deploy/langchain-service \
  --namespace xagent-prod \
  --create-namespace \
  -f deploy/langchain-service/values-prod.yaml \
  --set image.repository=registry.example.com/xagent-langchain-service \
  --set image.tag=2026-04-05 \
  --set externalSecret.secretStoreRef.kind=ClusterSecretStore \
  --set externalSecret.secretStoreRef.name=aws-secretsmanager \
  --set externalSecret.data.openaiApiKey.key=xagent/prod/langchain-service \
  --set externalSecret.data.openaiApiKey.property=OPENAI_API_KEY
```

GCP example flow:

1. Grant ESO access to Secret Manager using GKE Workload Identity or Workload Identity Federation.
2. Apply one of the GCP store manifests.
3. Deploy the chart with:

```bash
helm upgrade --install langchain-service deploy/langchain-service \
  --namespace xagent-prod \
  --create-namespace \
  -f deploy/langchain-service/values-prod.yaml \
  --set image.repository=registry.example.com/xagent-langchain-service \
  --set image.tag=2026-04-05 \
  --set externalSecret.secretStoreRef.kind=ClusterSecretStore \
  --set externalSecret.secretStoreRef.name=gcp-secretmanager \
  --set externalSecret.data.openaiApiKey.key=xagent/prod/langchain-service \
  --set externalSecret.data.openaiApiKey.property=OPENAI_API_KEY
```

Nested secret field example:

If an application uses a nested config model such as:

```python
class OpenAIConfig(StrictConfigModel):
    api_key: str | None = None

class AppConfig(StrictConfigModel):
    openai: OpenAIConfig = OpenAIConfig()
```

then the Kubernetes secret key must use the env-to-path mapping form:

```text
OPENAI__API_KEY
```

because the runtime loader maps:

```text
OPENAI__API_KEY -> openai.api_key
```

For Helm and External Secrets Operator, this means:

1. Configure the chart to emit the env-style secret key:

```yaml
secret:
  keys:
    openaiApiKey: OPENAI__API_KEY
```

2. Keep the remote secret lookup as usual:

```yaml
externalSecret:
  data:
    openaiApiKey:
      key: xagent/prod/langchain-service
      property: OPENAI_API_KEY
```

3. ESO will create a Kubernetes `Secret` whose key is `OPENAI__API_KEY`.
4. `envFrom.secretRef` injects that into the container environment.
5. The app loader maps it into the nested config field `openai.api_key`.

An end-to-end override example is included in
[nested-secret-values-example.yaml](/home/xuelin/work/xagent-p/deploy/langchain-service/examples/nested-secret-values-example.yaml).
