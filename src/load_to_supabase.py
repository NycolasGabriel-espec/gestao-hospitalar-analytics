"""
Script de Carga Automatizada para o Supabase (PostgreSQL)
Projeto: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial

Carrega as 5 tabelas dimensionais e a tabela fato diretamente no Supabase.
Suporta dois métodos de ingestão:
  1. API REST do Supabase (PostgREST via requests) - Não requer driver PostgreSQL instalado!
  2. Conexão Direta PostgreSQL (SQLAlchemy / psycopg2) - Máxima velocidade para grandes volumes.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, List
import pandas as pd
import requests

# Tentar carregar variáveis de ambiente do .env
try:
    from dotenv import load_dotenv
    # Carregar da raiz do projeto
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Ordem de carga respeitando as chaves estrangeiras (FKs)
TABLE_CONFIG = [
    {
        "table": "dim_tempo",
        "file": "dim_tempo.csv",
        "pk": "id_data",
        "dtypes": {
            "id_data": "int64",
            "data_completa": "string",
            "ano": "int64",
            "mes": "int64",
            "dia": "int64",
            "nome_mes": "string",
            "trimestre": "int64",
            "ano_mes": "string",
            "dia_semana": "string",
            "eh_fim_semana": "bool"
        }
    },
    {
        "table": "dim_paciente",
        "file": "dim_paciente.csv",
        "pk": "id_paciente",
        "dtypes": {
            "id_paciente": "string",
            "sexo": "string",
            "faixa_etaria": "string"
        }
    },
    {
        "table": "dim_procedimento",
        "file": "dim_procedimento.csv",
        "pk": "id_procedimento",
        "dtypes": {
            "id_procedimento": "string",
            "descricao_procedimento": "string",
            "especialidade": "string",
            "complexidade": "string",
            "porte_cirurgico": "string",
            "tmp_protocolo_previsto": "float64"
        }
    },
    {
        "table": "dim_diagnostico",
        "file": "dim_diagnostico.csv",
        "pk": "cid_10",
        "dtypes": {
            "cid_10": "string",
            "descricao_cid": "string",
            "capitulo_cid": "string",
            "grau_severidade": "string"
        }
    },
    {
        "table": "dim_setor_leito",
        "file": "dim_setor_leito.csv",
        "pk": "id_leito",
        "dtypes": {
            "id_leito": "string",
            "tipo_acomodacao": "string",
            "setor_hospitalar": "string",
            "leitos_operacionais": "Int64"
        }
    },
    {
        "table": "fato_internacoes",
        "file": "fato_internacoes.csv",
        "pk": "id_atendimento",
        "dtypes": {
            "id_atendimento": "string",
            "id_paciente": "string",
            "id_procedimento": "string",
            "cid_10": "string",
            "id_leito": "string",
            "id_data_admissao": "int64",
            "id_data_alta": "Int64",
            "dias_permanencia": "Int64",
            "dias_uti": "Int64",
            "qtd_diarias": "Int64",
            "custo_hospitalar": "float64",
            "custo_servicos_profissionais": "float64",
            "custo_opme": "float64",
            "custo_sadt": "float64",
            "custo_total": "float64",
            "receita_faturada": "float64",
            "margem_contribuicao": "float64",
            "status_desfecho": "string",
            "indicador_obito": "Int64",
            "readmissao_30d": "boolean"
        }
    }
]


def load_dataframe(csv_path: Path, dtypes: dict) -> pd.DataFrame:
    """Lê CSV pré-processado com separador ponto-e-vírgula e tipos definidos."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {csv_path}")
    
    header = pd.read_csv(csv_path, sep=";", nrows=0).columns
    missing = set(dtypes) - set(header)
    unexpected = set(header) - set(dtypes)
    if missing or unexpected:
        raise ValueError(
            f"Esquema inesperado em {csv_path.name}; "
            f"faltam {sorted(missing)} e campos extras {sorted(unexpected)}."
        )
    df = pd.read_csv(csv_path, sep=";", dtype=dtypes, usecols=list(dtypes))
    return df


def validate_supabase_url(value: str) -> bool:
    """Do not send privileged API credentials over plaintext or to an invalid URL."""
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
    except ValueError:
        return False
    if (
        not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or hostname in {"seu-projeto.supabase.co", "xyzcompanyproject.supabase.co"}
    ):
        return False
    local_http = parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1"}
    return bool(hostname and (parsed.scheme == "https" or local_http))


def validate_database_url(value: str) -> bool:
    """Require TLS and refuse the Supabase postgres master login for ETL."""
    try:
        parsed = urlparse(value)
        username = parsed.username or ""
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme not in {"postgresql", "postgres"} or not hostname or not username:
        return False
    if username.lower() == "postgres" or username.lower().startswith("postgres."):
        return False
    return port is None or 1 <= port <= 65535


def upload_via_api(supabase_url: str, supabase_key: str, batch_size: int = 500, truncate: bool = False):
    """Carrega dados no Supabase usando a API PostgREST (requisições HTTP em lote com upsert)."""
    base_url = supabase_url.rstrip("/")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal"
    }
    
    # Testar conectividade inicial
    print(f"📡 Conectando à API Supabase: {base_url}...")
    try:
        test_res = requests.get(f"{base_url}/rest/v1/", headers=headers, timeout=10, allow_redirects=False)
        if test_res.status_code not in (200, 404):
            print(f"⚠️ Alerta de status na conexão: HTTP {test_res.status_code}")
    except Exception:
        print("❌ Erro ao conectar na API Supabase.")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "processed"

    if truncate:
        for cfg in reversed(TABLE_CONFIG):
            table_name = cfg["table"]
            print(f"   🧹 Limpando dados pré-existentes de [{table_name}]...")
            del_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Prefer": "return=minimal"
            }
            del_url = f"{base_url}/rest/v1/{table_name}?{cfg['pk']}=not.is.null"
            delete_res = requests.delete(del_url, headers=del_headers, timeout=30, allow_redirects=False)
            if delete_res.status_code not in (200, 204):
                print(f"   ❌ Não foi possível limpar [{table_name}]: HTTP {delete_res.status_code}.")
                sys.exit(1)
    
    total_records_inserted = 0
    start_time = time.time()
    
    for cfg in TABLE_CONFIG:
        table_name = cfg["table"]
        file_path = data_dir / cfg["file"]
        
        print(f"\n📂 Preparando tabela [{table_name}] a partir de {cfg['file']}...")
        df = load_dataframe(file_path, cfg["dtypes"])
        total_rows = len(df)
        print(f"   Total de registros a enviar: {total_rows:,}")
        
        # Converter dataframe para lista de dicionários com tipos nativos do Python
        # Para booleanos e datas, garantir conformidade JSON
        records = df.astype(object).where(pd.notna(df), None).to_dict(orient="records")
        
        endpoint = f"{base_url}/rest/v1/{table_name}"
        inserted_table = 0
        
        # Enviar em lotes
        for i in range(0, total_rows, batch_size):
            chunk = records[i:i + batch_size]
            res = requests.post(endpoint, headers=headers, json=chunk, timeout=60, allow_redirects=False)
            
            if res.status_code not in (200, 201, 204):
                print(f"   ❌ Erro ao enviar lote {i}-{i+len(chunk)} em [{table_name}]: HTTP {res.status_code}")
                print("\n💡 DICA: Certifique-se de que o script 'sql/supabase_setup.sql' foi executado no Supabase SQL Editor.")
                sys.exit(1)
                
            inserted_table += len(chunk)
            pct = (inserted_table / total_rows) * 100
            print(f"   ➡️ Progresso [{table_name}]: {inserted_table:,}/{total_rows:,} ({pct:.1f}%)", end="\r")
            
        print(f"\n   ✅ [{table_name}] concluído com sucesso ({inserted_table:,} registros inseridos/atualizados).")
        total_records_inserted += inserted_table
        
    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"🎉 CARGA VIA API SUPABASE CONCLUÍDA COM SUCESSO!")
    print(f"   Total geral: {total_records_inserted:,} registros processados em {elapsed:.1f} segundos.")
    print("=" * 65)


def upload_via_direct_db(database_url: str, batch_size: int = 1000, truncate: bool = False):
    """Carrega dados no Supabase via conexão direta PostgreSQL (SQLAlchemy)."""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.dialects.postgresql import insert
    except ImportError:
        print("❌ SQLAlchemy não está instalado. Instale com: pip install sqlalchemy psycopg2-binary")
        sys.exit(1)
        
    print(f"🔌 Conectando diretamente ao banco PostgreSQL...")
    engine = create_engine(database_url, connect_args={"sslmode": "require"})
    
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "processed"
    
    total_records = 0
    start_time = time.time()
    
    with engine.begin() as conn:
        if truncate:
            print("🧹 Limpando as tabelas do projeto em um único comando...")
            table_names = ", ".join(f"{cfg['table']}" for cfg in TABLE_CONFIG)
            conn.execute(text(f"TRUNCATE TABLE {table_names};"))
                
        for cfg in TABLE_CONFIG:
            table_name = cfg["table"]
            file_path = data_dir / cfg["file"]
            
            print(f"\n📂 Carregando [{table_name}] via SQLAlchemy...")
            df = load_dataframe(file_path, cfg["dtypes"])
            
            def upsert_method(table, connection, keys, data_iter, primary_key=cfg["pk"]):
                rows = [
                    {key: (None if pd.isna(value) else value) for key, value in zip(keys, row)}
                    for row in data_iter
                ]
                if not rows:
                    return 0
                statement = insert(table.table).values(rows)
                updates = {
                    column.name: getattr(statement.excluded, column.name)
                    for column in table.table.columns
                    if column.name != primary_key
                }
                result = connection.execute(
                    statement.on_conflict_do_update(index_elements=[primary_key], set_=updates)
                )
                return result.rowcount

            df.to_sql(
                name=table_name,
                con=conn,
                if_exists="append",
                index=False,
                chunksize=batch_size,
                method=upsert_method
            )
            print(f"   ✅ [{table_name}]: {len(df):,} linhas inseridas/atualizadas.")
            total_records += len(df)
            
    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"🎉 CARGA DIRETA POSTGRESQL CONCLUÍDA COM SUCESSO!")
    print(f"   Total geral: {total_records:,} registros inseridos em {elapsed:.1f} segundos.")
    print("=" * 65)


def validate_local_data():
    """Valida se todos os arquivos locais estão íntegros e com colunas corretas."""
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "processed"
    print("🔍 Validando arquivos locais em:", data_dir)
    
    all_ok = True
    total_rows = 0
    for cfg in TABLE_CONFIG:
        path = data_dir / cfg["file"]
        if not path.exists():
            print(f"   ❌ Arquivo faltando: {path}")
            all_ok = False
            continue
            
        df = pd.read_csv(path, sep=";", dtype=str)
        missing_cols = set(cfg["dtypes"].keys()) - set(df.columns)
        unexpected_cols = set(df.columns) - set(cfg["dtypes"].keys())
        if missing_cols or unexpected_cols:
            print(
                f"   ❌ Esquema inválido em {cfg['file']}: "
                f"ausentes={sorted(missing_cols)}, extras={sorted(unexpected_cols)}"
            )
            all_ok = False
        else:
            print(f"   ✔️ {cfg['table']:<20} -> {len(df):>6,} linhas | {len(df.columns)} colunas")
            total_rows += len(df)
            
    if all_ok:
        print(f"\n✨ Todos os datasets estão válidos! Total de {total_rows:,} registros prontos para envio.")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Carga de Dados no Supabase (Star Schema Hospitalar)")
    parser.add_argument("--method", choices=["auto", "api", "direct"], default="auto",
                        help="Método de carga: 'api' (REST PostgREST), 'direct' (PostgreSQL URI) ou 'auto'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas valida os dados locais sem conectar ou enviar ao Supabase")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Tamanho do lote por envio (padrão: 500)")
    parser.add_argument("--truncate", action="store_true",
                        help="Apaga os dados existentes antes de carregar (exige --confirm-truncate)")
    parser.add_argument("--confirm-truncate", action="store_true",
                        help="Confirma a remoção dos dados existentes quando usado com --truncate")
    args = parser.parse_args()

    if not 1 <= args.batch_size <= 1000:
        parser.error("--batch-size deve estar entre 1 e 1000")
    if args.truncate != args.confirm_truncate:
        parser.error("Use --truncate e --confirm-truncate juntos para confirmar a remoção de dados")

    print("=" * 65)
    print("🏥 HEALTHCARE ANALYTICS - CARGA DE DADOS PARA O SUPABASE")
    print("=" * 65)

    if args.dry_run:
        if not validate_local_data():
            sys.exit(1)
        return

    # Validar dados locais primeiro
    if not validate_local_data():
        print("❌ Validação de dados falhou. Abortando.")
        sys.exit(1)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    database_url = os.getenv("DATABASE_URL")

    # Decisão do método de envio
    chosen_method = args.method
    if chosen_method == "auto":
        database_is_configured = bool(database_url) and not any(
            marker in database_url.lower()
            for marker in ("[sua-senha]", "[seu-project-ref]", "sua-senh", "xyzcompanyproject")
        )
        api_is_configured = bool(supabase_url and supabase_key) and "seu-projeto" not in supabase_url.lower()
        if database_is_configured:
            chosen_method = "direct"
        elif api_is_configured:
            chosen_method = "api"
        else:
            print("\n⚠️ NENHUMA CREDENCIAL CONFIGURADA!")
            print("Configure suas credenciais no arquivo .env a partir de .env.example:")
            print("   1. Copie o arquivo: cp .env.example .env")
            print("   2. Configure DATABASE_URL ou SUPABASE_SERVICE_ROLE_KEY")
            print("   3. Execute o script novamente: python src/load_to_supabase.py\n")
            print("Para testar apenas a validação dos arquivos locais, use:")
            print("   python src/load_to_supabase.py --dry-run")
            sys.exit(1)

    print(f"\n🚀 Método de ingestão selecionado: {chosen_method.upper()}")

    if chosen_method == "api":
        if not supabase_url or not supabase_key:
            print("❌ Erro: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórios para carga via API.")
            sys.exit(1)
        if not validate_supabase_url(supabase_url):
            print("❌ Erro: SUPABASE_URL precisa usar HTTPS (HTTP só é aceito para localhost).")
            sys.exit(1)
        upload_via_api(supabase_url, supabase_key, batch_size=args.batch_size, truncate=args.truncate)
    elif chosen_method == "direct":
        if not database_url:
            print("❌ Erro: DATABASE_URL é obrigatório para carga direta via PostgreSQL.")
            sys.exit(1)
        if not validate_database_url(database_url):
            print("❌ DATABASE_URL inválida: use PostgreSQL com TLS e uma role de carga dedicada, não postgres.")
            sys.exit(1)
        upload_via_direct_db(database_url, batch_size=args.batch_size, truncate=args.truncate)


if __name__ == "__main__":
    main()
