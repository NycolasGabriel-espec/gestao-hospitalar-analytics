"""
Supabase Client & Query Helper
Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial

Fornece funções para conexão, teste de conectividade e consumo de dados analíticos
direto do Supabase via API REST (PostgREST) ou SDK oficial.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
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
    """Obtém credenciais do Supabase a partir das variáveis de ambiente."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
    db_url = os.getenv("DATABASE_URL", "")
    return {"url": url, "key": key, "db_url": db_url}


def test_supabase_connection() -> Dict[str, Any]:
    """
    Testa a conectividade com o Supabase e verifica a existência das tabelas analíticas.
    Retorna um dicionário com o status de cada componente.
    """
    cfg = get_config()
    if not cfg["url"] or not cfg["key"]:
        return {
            "success": False,
            "message": "SUPABASE_URL ou SUPABASE_KEY não configurados no arquivo .env"
        }

    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}"
    }

    results = {"success": True, "tables": {}}
    tables = [
        "dim_tempo", "dim_paciente", "dim_procedimento",
        "dim_diagnostico", "dim_setor_leito", "fato_internacoes",
        "vw_painel_executivo_mensal", "vw_eficiencia_leitos_setor", "vw_detalhe_clinico_risco"
    ]

    for tbl in tables:
        url = f"{cfg['url']}/rest/v1/{tbl}?select=count"
        headers_count = {**headers, "Prefer": "count=exact", "Range": "0-0"}
        try:
            res = requests.get(url, headers=headers_count, timeout=10)
            if res.status_code == 200 or res.status_code == 206:
                content_range = res.headers.get("content-range", "")
                total = content_range.split("/")[-1] if "/" in content_range else "OK"
                results["tables"][tbl] = {"status": "disponível", "total_linhas": total}
            else:
                results["tables"][tbl] = {"status": f"erro HTTP {res.status_code}", "detalhe": res.text[:100]}
                results["success"] = False
        except Exception as e:
            results["tables"][tbl] = {"status": "falha na requisição", "erro": str(e)}
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
        raise ValueError("SUPABASE_URL e SUPABASE_KEY precisam estar configurados no .env")

    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Range": f"0-{limit - 1}" if limit else "0-9999"
    }

    params = {"select": select}
    if filters:
        params.update(filters)

    url = f"{cfg['url']}/rest/v1/{table_or_view}"
    res = requests.get(url, headers=headers, params=params, timeout=30)

    if res.status_code not in (200, 206):
        raise RuntimeError(f"Erro ao consultar Supabase ({table_or_view}): HTTP {res.status_code} - {res.text}")

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

