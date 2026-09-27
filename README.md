# go-clean-api

Agent skill that validates and reproduces a Go HTTP API in inward-pointing layers: `cmd`, `config`, `domain`, `application`, `infrastructure`, `delivery`. Includes the documentation and OpenTelemetry library set used by that layout.

`SKILL.md` stays under 500 lines. Module paths and wiring notes live in `references/`. A small script checks import direction.

## Install

The [Skills CLI](https://github.com/vercel-labs/skills) discovers `skills/<name>/SKILL.md`:

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
```

## Check a module

```bash
python3 skills/go-clean-api/scripts/check_layers.py /path/to/module
```

Exit 0 when layer imports hold. Exit 1 lists the files that import a package their layer must not see.

## License

MIT
