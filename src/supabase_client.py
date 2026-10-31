"""
Supabase Client & Query Helper
Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial

Fornece funções para conexão, teste de conectividade e consumo de dados analíticos
direto do Supabase via API REST (PostgREST).
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
import pandas as pd
import requests

# Carregar variáveis de ambiente do .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass


def get_config() -> Dict[str, str]:
    """Obtém credenciais locais; a chave privilegiada nunca deve sair deste processo."""
    configured_url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    try:
        parsed = urlparse(configured_url) if configured_url else None
        hostname = parsed.hostname if parsed else None
        port = parsed.port if parsed else None
    except ValueError:
        parsed, hostname, port = None, None, None
    local_http = bool(parsed and parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1"})
    valid_origin = bool(
        parsed
        and hostname
        and (parsed.scheme == "https" or local_http)
        and not parsed.username
        and not parsed.password
        and parsed.path in ("", "/")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
        and (port is None or 1 <= port <= 65535)
    )
    url = parsed._replace(path="", params="", query="", fragment="").geturl().rstrip("/") if valid_origin else ""
    return {"url": url, "key": key}


def test_supabase_connection() -> Dict[str, Any]:
    """
    Testa a conectividade com o Supabase e verifica a existência das tabelas analíticas.
    Retorna um dicionário com o status de cada componente.
    """
    cfg = get_config()
    if not cfg["url"] or not cfg["key"]:
        return {
            "success": False,
            "message": "SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não configurados no arquivo .env"
        }

    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}"
    }

    results = {"success": True, "tables": {}}
    tables = [
        "vw_painel_executivo_mensal", "vw_eficiencia_leitos_setor", "vw_detalhe_clinico_risco",
        "vw_dim_procedimento", "vw_dim_diagnostico", "vw_dim_setor_leito", "vw_dim_tempo"
    ]

    for tbl in tables:
        url = f"{cfg['url']}/rest/v1/{tbl}?select=*"
        headers_count = {**headers, "Prefer": "count=exact", "Range": "0-0"}
        try:
            res = requests.get(url, headers=headers_count, timeout=10, allow_redirects=False)
            if res.status_code == 200 or res.status_code == 206:
                content_range = res.headers.get("content-range", "")
                total = content_range.split("/")[-1] if "/" in content_range else "OK"
                results["tables"][tbl] = {"status": "disponível", "total_linhas": total}
            else:
                results["tables"][tbl] = {"status": f"erro HTTP {res.status_code}"}
                results["success"] = False
        except Exception:
            results["tables"][tbl] = {"status": "falha na requisição"}
            results["success"] = False

    return results


def query_table(
    table_or_view: str,
    select: str = "*",
    filters: Optional[Dict[str, str]] = None,
    limit: Optional[int] = 1000
) -> pd.DataFrame:
    """
    Consulta uma tabela ou view do Supabase e retorna os dados em um DataFrame Pandas.
    
    Exemplo:
        df = query_table("vw_painel_executivo_mensal", select="ano_mes,especialidade,margem_contribuicao")
    """
    cfg = get_config()
    if not cfg["url"] or not cfg["key"]:
        raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar configurados no .env")

    allowed_views = {
        "vw_painel_executivo_mensal", "vw_eficiencia_leitos_setor", "vw_detalhe_clinico_risco",
        "vw_dim_procedimento", "vw_dim_diagnostico", "vw_dim_setor_leito", "vw_dim_tempo"
    }
    allowed_filters = {
        "vw_painel_executivo_mensal": {"ano_mes", "especialidade"},
        "vw_eficiencia_leitos_setor": {"ano_mes", "id_leito"},
        "vw_detalhe_clinico_risco": {"ano_mes", "cid_10", "especialidade", "grau_severidade"},
        "vw_dim_procedimento": {"id_procedimento", "especialidade"},
        "vw_dim_diagnostico": {"cid_10", "grau_severidade"},
        "vw_dim_setor_leito": {"id_leito"},
        "vw_dim_tempo": {"ano_mes", "ano", "mes"},
    }
    if table_or_view not in allowed_views:
        raise ValueError("A consulta local só pode acessar as views analíticas aprovadas.")
    if not isinstance(limit, int) or limit < 1 or limit > 1000:
        raise ValueError("limit deve ser um inteiro entre 1 e 1000")
    if not (select == "*" or all(part.replace("_", "").isalnum() for part in select.split(","))):
        raise ValueError("select contém uma coluna inválida")

    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Range": f"0-{limit - 1}" if limit else "0-9999"
    }

    params = {"select": select}
    if filters:
        for column, value in filters.items():
            if column not in allowed_filters[table_or_view] or not isinstance(value, str) or not value or len(value) > 80:
                raise ValueError("filters contém um filtro inválido")
            if not all(char.isalnum() or char in " _./&+-" for char in value):
                raise ValueError("filters contém um valor inválido")
            params[column] = f"eq.{value}"

    url = f"{cfg['url']}/rest/v1/{table_or_view}"
    res = requests.get(url, headers=headers, params=params, timeout=30, allow_redirects=False)

    if res.status_code not in (200, 206):
        raise RuntimeError(f"Erro ao consultar Supabase ({table_or_view}): HTTP {res.status_code}")

    return pd.DataFrame(res.json())


if __name__ == "__main__":
    print("Testando conexão com o Supabase...")
    status = test_supabase_connection()
    if status["success"]:
        print("✅ Conexão bem-sucedida! Status das tabelas e views:")
        for t, info in status["tables"].items():
            print(f"   • {t}: {info}")
    else:
        print("ℹ️ Status da conexão:")
        print(status)

