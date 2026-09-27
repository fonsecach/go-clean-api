# Padrão de observabilidade — Grafana LGTM

O padrão é esta skill. O dashboard e os datasources saem de `references/grafana-template/`, preenchidos por `scripts/render_grafana.py`. Não há outro repositório para copiar.

Troque o que é do serviço (nome, título, bancos, limites de CPU e memória). Mantenha a topologia.

## Por que esta forma

A aplicação em Go não é o lugar onde se consulta observabilidade. Ela emite os três sinais uma vez, via OTLP, e o Grafana é a única UI. Prometheus, Loki e Tempo ficam atrás do collector. Isso evita um scrape `/metrics` na API como caminho principal, um Promtail ou Alloy no lugar do collector, e um backend de trace diferente por serviço.

```
API (Go) ──OTLP/gRPC──▶ OTel Collector ──┬─▶ Prometheus (métricas)
  slog JSON + spans + meters              ├─▶ Loki (logs)
                                          └─▶ Tempo (traces)
node_exporter + postgres_exporter ──────▶ Prometheus
                                          ▼
                                       Grafana
```

Imagens para fixar ao criar a stack (não suba major sem motivo): collector contrib `0.116.1`, Prometheus `v3.1.0`, Loki `3.3.2`, Tempo `2.7.0`, Grafana `11.4.0`.

O dashboard gerado usa tema escuro, refresh de 5s e janela padrão de 1 hora, no estilo do painel App do Fly.io.

## Contrato da aplicação

O dashboard quebra se a app não cumprir isto. Ao instrumentar código, alinhe com as seções 1–4 e 6 do `SKILL.md` e com estes nomes. O pacote fica em `internal/infrastructure/observability/` (`otel.go`, `slog.go`, `metrics.go`, `pgxstats.go`), montado em `cmd`, como em `go-clean-api`.

- `OTEL_ENABLED` liga a telemetria. Com `false`, o setup é no-op. O padrão de um serviço novo é desligado até o collector existir.
- `OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317` (gRPC). `OTEL_SERVICE_NAME` vira `service_name` nos logs e nos seletores do Grafana.
- Collector fora do ar não impede a API de subir nem de servir tráfego. O exporter não bloqueia no dial (`grpc.WithBlock` fica de fora). Erro de telemetria é logado, não é fatal.
- Logs: `slog` em JSON, com `trace_id` e `span_id` tirados do span do contexto. O derived field do Loki procura `"trace_id":"(\w+)"`.
- HTTP: middleware OTel (`otelchi` com o pattern do chi). Métrica `http.server.request.duration`. Label de rota é o template (`/api/v1/orders/{id}`), nunca o path cru nem um id.
- Concorrência in-flight: `http.server.active_requests`.
- Runtime Go (memória, goroutines, alocação) sai pelo MeterProvider da própria app, não por um sidecar.
- Traces amostrados (ponto de partida: 10% via `OTEL_TRACES_SAMPLER_ARG=0.10`, parent-based). Métricas e logs seguem em 100%.
- No shutdown, dê flush nos providers com timeout curto.

## Collector

Arquivo esperado: `docker/observability/otel-collector-config.yaml`.

- Receiver `otlp` em `:4317` (gRPC) e `:4318` (HTTP).
- Processors `memory_limiter` (limit 150 MiB, ponto de partida) e `batch`.
- Traces → `otlp/tempo` (`tempo:4317`, TLS insecure na rede do compose).
- Métricas → exporter `prometheus` em `:8889`, com `resource_to_telemetry_conversion`. O Prometheus raspa o collector, não a API.
- Logs → `otlphttp/loki` em `http://loki:3100/otlp`.

`docker/observability/prometheus.yml` raspa `otel-collector:8889`, `node-exporter:9100` e o postgres-exporter. cAdvisor é opcional: nenhum painel essencial depende dele.

Retenção de partida: Prometheus 15d e 5GB, Loki 7d, Tempo 48h. Cada serviço do compose leva `mem_limit` e `cpus` para a stack não competir com o banco. Recalcule para o host real.

## Grafana provisionado

Datasources em `grafana/provisioning/datasources/datasources.yaml`. Os UIDs são contrato dos painéis — mantenha `prometheus`, `loki` e `tempo`.

- Prometheus é o datasource default (`http://prometheus:9090`).
- Loki (`http://loki:3100`) tem derived field `TraceID` com regex `"trace_id":"(\w+)"` apontando para o UID `tempo`.
- Tempo (`http://tempo:3200`) tem `tracesToLogsV2` de volta para o UID `loki`, filtro por trace id, tag `service.name` → `service_name`, e node graph ligado.

Não monte o dashboard à mão. Gere o provisionamento a partir do template em `references/grafana-template/` com `scripts/render_grafana.py`. Os tokens são `__SERVICE_NAME__`, `__DASHBOARD_TITLE__`, `__DASHBOARD_UID__` e `__DB_DATNAME_REGEX__`. Os datasources saem iguais em todo serviço.

```bash
python scripts/render_grafana.py \
  --service-name billing-api \
  --title "Billing API" \
  --db-datname-regex "billing" \
  --out docker/observability/grafana/provisioning
```

Isso grava `datasources/datasources.yaml`, `dashboards/dashboards.yaml` e `dashboards/json/<uid>.json`. Monte esse diretório em `/etc/grafana/provisioning` no container do Grafana.

Seções do dashboard:

| Seção | O que mostra |
|---|---|
| Logs | Logs ao vivo (Loki) e volume por nível |
| Overview | Memória, CPU e rede do host (`node_exporter`), concorrência in-flight, load 5m |
| HTTP | Contagem por status, p50/p90/p99, tempo médio, RPS por rota |
| Volumes | Filesystem raiz |
| Database | Pool pgx, conexões/tx do Postgres, top slow queries (`pg_stat_statements`) |
| API (processo Go) | Memória do processo, goroutines, alocação |

Depois do primeiro deploy, confira os nomes reais em `http://otel-collector:8889/metrics`. A conversão OTel → Prometheus troca ponto por underscore e pode acrescentar unidade (`http.server.request.duration` vira `http_server_request_duration_seconds_*`). Se um painel ficar "No data", ajuste a query ao nome exportado. Não invente outra métrica na aplicação.

## O que adaptar em cada deploy

A forma acima vale para qualquer API Go neste padrão. Ajuste só o que muda de ambiente:

- Nome do serviço, título e uid do dashboard — sempre pelo `render_grafana.py`, nunca editando o JSON à mão.
- Regex de `datname` quando houver um ou mais Postgres. Um banco no host (fora do compose) usa o exporter com `host.docker.internal` e uma regra de `pg_hba` para a subnet do Docker. Isso é deploy, não um segundo padrão.
- `mem_limit` e `cpus` para a máquina real. A observabilidade não pode ficar com a RAM que o banco precisa.
- Proxy TLS na frente. API e Grafana escutam em `127.0.0.1`. Prometheus, Loki, Tempo e exporters não são publicados. O proxy pode ser Caddy, outro reverse proxy, ou só localhost em desenvolvimento.

Credenciais do Grafana (`GRAFANA_USER`, `GRAFANA_PASSWORD`) ficam no `.env` local, nunca no compose com senha real commitada.
