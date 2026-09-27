#!/usr/bin/env python3
"""Gera o provisionamento Grafana (datasources + dashboard) do padrão LGTM.

O JSON e o provider saem de references/grafana-template/, com tokens no
lugar do nome do serviço.
Os UIDs prometheus, loki e tempo não mudam: os painéis e a correlação
log↔trace dependem deles.

Uso:
  python scripts/render_grafana.py \\
    --service-name billing-api \\
    --title "Billing API" \\
    --out docker/observability/grafana/provisioning

Opções:
  --uid              uid do dashboard (padrão: service-name, máx. 40)
  --folder           pasta no Grafana (padrão: --title)
  --db-datname-regex regex PromQL de datname (padrão: .+)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOKEN_SERVICE = "__SERVICE_NAME__"
TOKEN_TITLE = "__DASHBOARD_TITLE__"
TOKEN_UID = "__DASHBOARD_UID__"
TOKEN_FOLDER = "__FOLDER_NAME__"
TOKEN_DB = "__DB_DATNAME_REGEX__"

SERVICE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,62}$")
UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Renderiza o template Grafana LGTM.")
    p.add_argument("--service-name", required=True, help="OTEL_SERVICE_NAME / service_name no Loki")
    p.add_argument("--title", required=True, help="Título do dashboard")
    p.add_argument("--out", required=True, type=Path, help="Diretório provisioning de destino")
    p.add_argument("--uid", help="uid do dashboard (padrão: service-name)")
    p.add_argument("--folder", help="Pasta no Grafana (padrão: title)")
    p.add_argument(
        "--db-datname-regex",
        default=".+",
        help='Regex de datname no painel Postgres (ex.: "billing|app")',
    )
    return p.parse_args()


def reject(label: str, value: str) -> str:
    if any(ch in value for ch in '"\\\n\r'):
        raise SystemExit(f"{label} não pode conter aspas, barra invertida ou quebra de linha")
    return value


def main() -> None:
    args = parse_args()
    service = reject("--service-name", args.service_name)
    title = reject("--title", args.title)
    folder = reject("--folder", args.folder or title)
    db_re = reject("--db-datname-regex", args.db_datname_regex)
    uid = args.uid or service.lower().replace("_", "-").replace(".", "-").replace(":", "-")
    uid = reject("--uid", uid)

    if not SERVICE_RE.match(service):
        raise SystemExit("--service-name deve ser um label seguro (letras, números, _ . : -)")
    if not UID_RE.match(uid):
        raise SystemExit("--uid deve ter 1–40 caracteres [A-Za-z0-9_-]")
    if not db_re:
        raise SystemExit("--db-datname-regex não pode ser vazio")

    template = skill_root() / "references" / "grafana-template"
    dashboard = (template / "dashboard.json").read_text()
    provider = (template / "dashboards.yaml").read_text()
    datasources = (template / "datasources.yaml").read_text()

    dashboard = (
        dashboard.replace(TOKEN_SERVICE, service)
        .replace(TOKEN_TITLE, title)
        .replace(TOKEN_UID, uid)
        .replace(TOKEN_DB, db_re)
    )
    provider = provider.replace(TOKEN_UID, uid).replace(TOKEN_FOLDER, folder)

    leftover = [
        token
        for token in (TOKEN_SERVICE, TOKEN_TITLE, TOKEN_UID, TOKEN_FOLDER, TOKEN_DB)
        if token in dashboard or token in provider
    ]
    if leftover:
        raise SystemExit(f"tokens não substituídos: {', '.join(leftover)}")

    out: Path = args.out
    json_dir = out / "dashboards" / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    (out / "datasources").mkdir(parents=True, exist_ok=True)
    (out / "datasources" / "datasources.yaml").write_text(datasources)
    (out / "dashboards" / "dashboards.yaml").write_text(provider)
    (json_dir / f"{uid}.json").write_text(dashboard)
    print(f"grafana provisioning em {out}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
