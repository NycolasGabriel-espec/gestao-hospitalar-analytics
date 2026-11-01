"""
Pipeline de Extração de Dados Reais do SIH/SUS (DATASUS) via PySUS
Autor: Nycolas Gabriel / Healthcare Analytics
"""

import os
import sys
import argparse
import asyncio
import re
from ftplib import FTP
from datetime import datetime
from pathlib import Path
import pandas as pd

os.environ.setdefault("PYSUS_CACHEPATH", str(Path(__file__).resolve().parent.parent / "data" / "cache"))
import pysus


def normalize_source_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Uniformiza o esquema entre o catálogo Parquet e os arquivos DBC oficiais."""
    columns = [
        'N_AIH', 'DT_INTER', 'DT_SAIDA', 'DIAS_PERM', 'QT_DIARIAS',
        'DIAG_PRINC', 'PROC_REA', 'VAL_TOT', 'SEXO', 'IDADE', 'COD_IDADE',
        'MORTE', 'UTI_MES_TO', 'ANO_CMPT', 'MES_CMPT', 'IDENT',
        'SEQ_AIH5', 'SEQUENCIA',
    ]
    result = frame[[column for column in columns if column in frame.columns]].astype('string')
    for column in [
        'SEXO', 'IDADE', 'COD_IDADE', 'MORTE', 'ANO_CMPT', 'MES_CMPT',
        'IDENT', 'SEQ_AIH5', 'SEQUENCIA',
    ]:
        if column in result:
            result[column] = result[column].str.replace(r'\.0+$', '', regex=True)
    for column in ['DT_INTER', 'DT_SAIDA']:
        if column in result:
            result[column] = result[column].str.replace(
                r'^(\d{4})-(\d{2})-(\d{2})(?:[ T].*)?$', r'\1\2\3', regex=True,
            )
    return result


def fetch_official_sih(state: str, year: int, month: int, cache_path: Path) -> pd.DataFrame:
    """Fallback para arquivos RD que ainda não aparecem no catálogo PySUS."""
    from pysus.api.extensions import ExtensionFactory

    filename = f"RD{state}{year % 100:02d}{month:02d}.dbc"
    destination = cache_path / filename
    if not destination.exists():
        partial = destination.with_suffix('.dbc.part')
        try:
            with FTP('ftp.datasus.gov.br', timeout=30) as ftp:
                ftp.login()
                ftp.cwd('/dissemin/publicos/SIHSUS/200801_/Dados')
                available = {name.rsplit('/', 1)[-1].upper() for name in ftp.nlst(filename)}
                if filename.upper() not in available:
                    raise FileNotFoundError(f"Competência oficial não encontrada: {year}-{month:02d}")
                # Reuse only the locally generated filename, never server text.
                with partial.open('wb') as target:
                    ftp.retrbinary(f'RETR {filename}', target.write)
            partial.replace(destination)
            destination.chmod(0o600)
        finally:
            partial.unlink(missing_ok=True)

    async def read_dbc():
        file = await ExtensionFactory.instantiate(destination)
        return await file.load()

    return asyncio.run(read_dbc())

def parse_competence(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})-(\d{2})", str(value).strip())
    if not match:
        raise ValueError(f"Competência inválida: {value!r}. Use YYYY-MM.")
    year, month = map(int, match.groups())
    if year < 1992 or year > datetime.now().year or month < 1 or month > 12:
        raise ValueError(f"Competência fora do intervalo válido: {value!r}.")
    return year, month


def extract_sih_data(
    state: str = "AC",
    year: int = 2023,
    months: list[int] = None,
    output_dir: str = "data/raw",
    source: str = "origin",
    competences: list[str] = None,
) -> Path:
    """
    Realiza o download dos dados de Autorização de Internação Hospitalar (AIH - SIH/SUS)
    utilizando a biblioteca PySUS e salva em formato Parquet local.
    
    Parâmetros:
    -----------
    state : str (UF com 2 letras, ex: 'AC', 'RJ', 'SP')
    year : int (Ano das competências, ex: 2023; compatibilidade com --months)
    months : list[int] (Lista de meses, ex: [1, 2])
    competences : list[str] (Competências YYYY-MM, inclusive anos diferentes)
    output_dir : str (Diretório para salvar os arquivos)
    """
    valid_states = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
    state = str(state).strip().upper()
    if state not in valid_states:
        raise ValueError("Informe uma UF brasileira válida com duas letras.")
    if source not in {"origin", "catalog"}:
        raise ValueError("A fonte precisa ser origin ou catalog.")

    if competences:
        requested_competences = sorted(set(parse_competence(item) for item in competences))
    else:
        if not isinstance(year, int) or year < 1992 or year > datetime.now().year:
            raise ValueError("Informe um ano válido entre 1992 e o ano atual.")
        months = [1] if months is None else months
        if not months or any(not isinstance(month, int) or month < 1 or month > 12 for month in months):
            raise ValueError("Informe ao menos um mês inteiro entre 1 e 12.")
        requested_competences = [(year, month) for month in sorted(set(months))]
        
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        out_path.chmod(0o700)
    cache_path = Path(os.environ["PYSUS_CACHEPATH"])
    cache_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        cache_path.chmod(0o700)
    
    competence_labels = [f"{item_year}-{month:02d}" for item_year, month in requested_competences]
    print(f"🏥 Iniciando extração SIH/SUS para UF: {state} | Competências: {', '.join(competence_labels)}")
    
    dfs = []
    missing_months = []
    for item_year, month in requested_competences:
        print(f"⬇️  Baixando dados de {state}/{item_year}-{month:02d}...")
        try:
            # RD contém o resumo das AIHs; outros grupos não têm o mesmo esquema.
            try:
                df_month = pysus.ftp.sih(state=state, year=item_year, month=month, group="RD", source=source, as_dataframe=True)
            except Exception:
                df_month = None
            if df_month is None or df_month.empty:
                print(f"   Consultando o arquivo RD diretamente no FTP DATASUS para {item_year}-{month:02d}...")
                df_month = fetch_official_sih(state, item_year, month, cache_path)
            if df_month is not None and not df_month.empty:
                print(f"✅ Sucesso: {len(df_month):,} registros carregados para o mês {month:02d}.")
                dfs.append(normalize_source_frame(df_month))
            else:
                print(f"⚠️ Aviso: Nenhum dado retornado para a competência {item_year}-{month:02d}.")
                missing_months.append((item_year, month))
        except Exception:
            print(f"❌ Não foi possível baixar a competência {item_year}-{month:02d}.")
            missing_months.append((item_year, month))

    if missing_months:
        raise RuntimeError(f"Extração incompleta; faltam as competências: {', '.join(f'{item_year}-{month:02d}' for item_year, month in missing_months)}")
            
    if not dfs:
        raise RuntimeError("Nenhum dado do SIH/SUS pôde ser obtido.")
        
    df_combined = pd.concat(dfs, ignore_index=True)
    
    # Salva arquivo consolidado em data/raw/
    if len({item_year for item_year, _ in requested_competences}) == 1:
        selected_year = requested_competences[0][0]
        first_month, last_month = requested_competences[0][1], requested_competences[-1][1]
        filename = f"sih_{state.lower()}_{selected_year}_{first_month:02d}-{last_month:02d}_raw.parquet"
    else:
        first = f"{requested_competences[0][0]}-{requested_competences[0][1]:02d}"
        last = f"{requested_competences[-1][0]}-{requested_competences[-1][1]:02d}"
        filename = f"sih_{state.lower()}_{first}_{last}_raw.parquet"
    dest_file = out_path / filename
    df_combined.to_parquet(dest_file, index=False)
    print(f"💾 Base bruta salva com sucesso em: {dest_file} ({df_combined.shape[0]:,} linhas, {df_combined.shape[1]} colunas).")
    
    return dest_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extração SIH/SUS DATASUS via PySUS")
    parser.add_argument("--state", type=str, default="AC", help="UF com 2 letras (padrão: AC)")
    parser.add_argument("--year", type=int, default=2023, help="Ano da competência (padrão: 2023)")
    parser.add_argument("--month", type=int, help="Mês da competência; alternativa a --months")
    parser.add_argument("--months", type=int, nargs="+", help="Lista de meses para extrair em um único conjunto")
    parser.add_argument("--competence", action="append", help="Competência YYYY-MM; pode ser repetida para cruzar anos")
    parser.add_argument("--source", choices=["origin", "catalog"], default="origin", help="Origem DATASUS ou espelho do catálogo PySUS")
    
    args = parser.parse_args()
    if args.competence and (args.month is not None or args.months is not None):
        parser.error("Use --competence ou --month/--months, não ambos.")
    months = args.months if args.months is not None else ([args.month] if args.month is not None else None)
    extract_sih_data(
        state=args.state, year=args.year, months=months,
        competences=args.competence, source=args.source,
    )
