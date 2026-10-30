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
            "idade": "int64",
            "faixa_etaria": "string",
            "municipio_residencia": "string",
            "uf_residencia": "string"
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
            "leitos_operacionais": "int64"
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
            "id_data_alta": "int64",
            "dias_permanencia": "int64",
            "dias_uti": "int64",
            "qtd_diarias": "int64",
            "custo_hospitalar": "float64",
            "custo_servicos_profissionais": "float64",
            "custo_opme": "float64",
            "custo_sadt": "float64",
            "custo_total": "float64",
            "receita_faturada": "float64",
            "margem_contribuicao": "float64",
            "status_desfecho": "string",
            "indicador_obito": "int64",
            "readmissao_30d": "bool"
        }
    }
]


def load_dataframe(csv_path: Path, dtypes: dict) -> pd.DataFrame:
    """Lê CSV pré-processado com separador ponto-e-vírgula e tipos definidos."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {csv_path}")
    
    df = pd.read_csv(csv_path, sep=";", dtype=dtypes)
    return df


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
        test_res = requests.get(f"{base_url}/rest/v1/", headers=headers, timeout=10)
        if test_res.status_code not in (200, 404):
            print(f"⚠️ Alerta de status na conexão: HTTP {test_res.status_code} - {test_res.text[:150]}")
    except Exception as e:
        print(f"❌ Erro ao conectar na API Supabase: {e}")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "processed"
    
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
        records = df.to_dict(orient="records")
        
        # Opcional: Truncar/Limpar tabela antes de carregar (se solicitado e for service role)
        if truncate:
            print(f"   🧹 Limpando dados pré-existentes de [{table_name}]...")
            del_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Prefer": "return=minimal"
            }
            # PostgREST DELETE com filtro que pega tudo (ex: id_data > 0 ou pk not null)
            del_url = f"{base_url}/rest/v1/{table_name}?{cfg['pk']}=not.is.null"
            requests.delete(del_url, headers=del_headers, timeout=30)
            
        endpoint = f"{base_url}/rest/v1/{table_name}"
        inserted_table = 0
        
        # Enviar em lotes
        for i in range(0, total_rows, batch_size):
            chunk = records[i:i + batch_size]
            res = requests.post(endpoint, headers=headers, json=chunk, timeout=60)
            
            if res.status_code not in (200, 201, 204):
                print(f"   ❌ Erro ao enviar lote {i}-{i+len(chunk)} em [{table_name}]: HTTP {res.status_code}")
                print(f"      Resposta do Supabase: {res.text[:300]}")
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
    except ImportError:
        print("❌ SQLAlchemy não está instalado. Instale com: pip install sqlalchemy psycopg2-binary")
        sys.exit(1)
        
    print(f"🔌 Conectando diretamente ao banco PostgreSQL...")
    engine = create_engine(database_url)
    
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "processed"
    
    total_records = 0
    start_time = time.time()
    
    with engine.begin() as conn:
        if truncate:
            print("🧹 Limpando tabelas existentes em cascata...")
            for cfg in reversed(TABLE_CONFIG):
                conn.execute(text(f"TRUNCATE TABLE {cfg['table']} CASCADE;"))
                
        for cfg in TABLE_CONFIG:
            table_name = cfg["table"]
            file_path = data_dir / cfg["file"]
            
            print(f"\n📂 Carregando [{table_name}] via SQLAlchemy...")
            df = load_dataframe(file_path, cfg["dtypes"])
            
            # Se não estiver truncando, evitar erro de duplicate key usando upsert ou if_exists
            df.to_sql(
                name=table_name,
                con=conn,
                if_exists="append",
                index=False,
                chunksize=batch_size,
                method="multi"
            )
            print(f"   ✅ [{table_name}]: {len(df):,} linhas inseridas.")
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
        if missing_cols:
            print(f"   ❌ Colunas ausentes em {cfg['file']}: {missing_cols}")
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
                        help="Limpa os dados das tabelas antes de carregar")
    args = parser.parse_args()

    print("=" * 65)
    print("🏥 HEALTHCARE ANALYTICS - CARGA DE DADOS PARA O SUPABASE")
    print("=" * 65)

    if args.dry_run:
        validate_local_data()
        return

    # Validar dados locais primeiro
    if not validate_local_data():
        print("❌ Validação de dados falhou. Abortando.")
        sys.exit(1)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    database_url = os.getenv("DATABASE_URL")

    # Decisão do método de envio
    chosen_method = args.method
    if chosen_method == "auto":
        if database_url and not database_url.startswith("postgresql://postgres:[SUA-SENHA]"):
            chosen_method = "direct"
        elif supabase_url and supabase_key and not supabase_url.startswith("https://seu-projeto"):
            chosen_method = "api"
        else:
            print("\n⚠️ NENHUMA CREDENCIAL CONFIGURADA!")
            print("Configure suas credenciais no arquivo .env a partir de .env.example:")
            print("   1. Copie o arquivo: cp .env.example .env")
            print("   2. Preencha SUPABASE_URL e SUPABASE_KEY ou DATABASE_URL")
            print("   3. Execute o script novamente: python src/load_to_supabase.py\n")
            print("Para testar apenas a validação dos arquivos locais, use:")
            print("   python src/load_to_supabase.py --dry-run")
            sys.exit(1)

    print(f"\n🚀 Método de ingestão selecionado: {chosen_method.upper()}")

    if chosen_method == "api":
        if not supabase_url or not supabase_key:
            print("❌ Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórios para carga via API.")
            sys.exit(1)
        upload_via_api(supabase_url, supabase_key, batch_size=args.batch_size, truncate=args.truncate)
    elif chosen_method == "direct":
        if not database_url:
            print("❌ Erro: DATABASE_URL é obrigatório para carga direta via PostgreSQL.")
            sys.exit(1)
        upload_via_direct_db(database_url, batch_size=args.batch_size, truncate=args.truncate)


if __name__ == "__main__":
    main()
