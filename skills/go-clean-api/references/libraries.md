# Recommended libraries

Read this before choosing modules for a new service, before changing the HTTP contract, or before wiring telemetry. Versions move; the module paths and the rules below are the stable part. Confirm current versions against the module proxy when adding a requirement. Do not invent an API.

## HTTP, data, security

| Concern | Module |
| --- | --- |
| Router | `github.com/go-chi/chi/v5` |
| Postgres | `github.com/jackc/pgx/v5` (`pgxpool`) |
| JWT | `github.com/golang-jwt/jwt/v5` |
| Password hashing | `golang.org/x/crypto/argon2` (Argon2id) |
| Per-IP rate limit | `golang.org/x/time/rate` |
| Env files in development | `github.com/joho/godotenv` |
| Identifiers | `github.com/google/uuid` |

JWT signing secret is at least 32 bytes, checked in `config.Load`. Argon2 parameters live next to the hasher, not in the handler.

## API docs

The YAML file is the contract. Generated comments are not.

| Piece | Where |
| --- | --- |
| Spec | `docs/openapi.yaml` |
| Embed | `docs/docs.go` |
| UI | `GET /docs` |
| Raw spec | `GET /docs/openapi.yaml` |

```go
package docs

import _ "embed"

//go:embed openapi.yaml
var Spec []byte
```

Serve the spec as `application/yaml`. Serve the UI as HTML that loads Scalar and points it at the raw spec:

```html
<script
  id="api-reference"
  data-url="/docs/openapi.yaml"
  data-configuration='{"theme":"purple"}'
></script>
<script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
```

Scalar is a UI dependency loaded in the browser from the jsDelivr CDN (`@scalar/api-reference`). It is not a Go module. Any change to a path, a body, a status, or auth updates `docs/openapi.yaml` in the same change. The embed ships that file inside the binary, so the running process and the spec cannot drift apart across deploys.

## Telemetry

The process speaks OTLP/gRPC only. Prometheus, Loki, Tempo, and Grafana sit behind an OpenTelemetry Collector. Do not add a Prometheus client as the source of HTTP metrics; `otelchi` already records them.

| Concern | Module |
| --- | --- |
| API | `go.opentelemetry.io/otel` |
| Traces | `go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc` |
| Metrics | `go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc` |
| Logs | `go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc` |
| slog bridge | `go.opentelemetry.io/contrib/bridges/otelslog` |
| Runtime metrics | `go.opentelemetry.io/contrib/instrumentation/runtime` |
| chi middleware | `github.com/riandyrn/otelchi` |

Rules that keep telemetry from becoming a hard dependency:

- `OTEL_ENABLED=false` installs no providers and returns a no-op shutdown. The default for a new service is off until the collector exists.
- Dial the collector in a way that does not block startup. On setup error, log a warning and keep serving. Shutdown joins the tracer, meter, and logger providers and is safe to call when setup was skipped.
- Resource attributes: `service.name`, `service.version`, `deployment.environment`.
- Sample traces with a ratio (parent-based). Production does not keep every span.
- HTTP middleware is `otelchi` with the chi route set (`WithChiRoutes`) plus request duration and active requests. The label is the template (`/api/v1/orders/{id}`), never the raw path. A raw path explodes cardinality.
- Propagate W3C trace context and baggage.
- `slog` JSON on stdout. Wrap the handler so a record inside a span gains `trace_id` and `span_id`. When the log provider is up, also hand records to the `otelslog` bridge (`NewCombinedLogger`). stdout stays even if the collector does not.
- Start runtime instrumentation on the same meter provider (heap, GC, goroutines). A failure there is a warning, not a crash.
- Register pgx pool stats (acquired, idle, max) under a pool name such as `app`.
- Business counters (`quota_exceeded`, lockout, cache hit, fallback) are created lazily on the global meter. With no provider they are no-ops, so call sites do not care whether telemetry started.

Suggested environment:

```bash
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317
OTEL_SERVICE_NAME=my-api
DEPLOYMENT_ENVIRONMENT=production
OTEL_TRACES_SAMPLER_ARG=0.10
```

Outside the process, the collector fans out: metrics to Prometheus, logs to Loki, traces to Tempo, dashboards in Grafana. Generate that provisioning with the sibling skill `go-clean-observability` (`scripts/render_grafana.py`). Host and database exporters (node exporter, postgres exporter) are deploy concerns. They do not belong in `go.mod`.
