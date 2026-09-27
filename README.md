# go-clean-api

Agent skills for a Go HTTP API whose dependencies point inward: `cmd`, `config`, `domain`, `application`, `infrastructure`, `delivery`.

- `go-clean-api` validates and reproduces that layout. Module paths and the OpenTelemetry library set live in `references/`. A small script checks import direction.
- `go-clean-observability` is the accessory skill for the telemetry stack: one OpenTelemetry Collector fans out to Prometheus, Loki, and Tempo, and Grafana is generated from the template in that skill. It does not decide which package owns the code.

## Install

The [Skills CLI](https://github.com/vercel-labs/skills) discovers every `skills/<name>/SKILL.md` in this repository:

```bash
npx skills add fonsecach/go-clean-api
```

Global install, available in every project:

```bash
npx skills add fonsecach/go-clean-api -g
```

This is the same `npx` install path used for skills published on GitHub. The Tech Leads Club wizard (`npx @tech-leads-club/agent-skills`) only lists skills in that catalog. This repository is the source you install directly.

## Layout

```text
skills/go-clean-api/
├── SKILL.md
├── references/libraries.md
└── scripts/check_layers.py

skills/go-clean-observability/
├── SKILL.md
├── LICENSE
├── references/grafana-lgtm.md
├── references/grafana-template/
└── scripts/render_grafana.py
```

Generate Grafana provisioning for a service:

```bash
python3 skills/go-clean-observability/scripts/render_grafana.py \
  --service-name my-api \
  --title "My API" \
  --out docker/observability/grafana/provisioning
```

## Check a module

```bash
python3 skills/go-clean-api/scripts/check_layers.py /path/to/module
```

Exit 0 when layer imports hold. Exit 1 lists the files that import a package their layer must not see.

## License

MIT. `skills/go-clean-observability/LICENSE` keeps both copyright notices: the original observability text and the Grafana template added here.
