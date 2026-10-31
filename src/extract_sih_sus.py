"""
Pipeline de Extração de Dados Reais do SIH/SUS (DATASUS) via PySUS
Autor: Nycolas Gabriel / Healthcare Analytics
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd
import pysus

def extract_sih_data(state: str = "AC", year: int = 2023, months: list[int] = None, output_dir: str = "data/raw") -> Path:
    """
    Realiza o download dos dados de Autorização de Internação Hospitalar (AIH - SIH/SUS)
    utilizando a biblioteca PySUS e salva em formato Parquet local.
    
    Parâmetros:
    -----------
    state : str (UF com 2 letras, ex: 'AC', 'RJ', 'SP')
    year : int (Ano da competência, ex: 2023)
    months : list[int] (Lista de meses, ex: [1, 2])
    output_dir : str (Diretório para salvar os arquivos)
    """
    if months is None:
        months = [1]

    valid_states = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
    state = str(state).strip().upper()
    if state not in valid_states:
        raise ValueError("Informe uma UF brasileira válida com duas letras.")
    if not isinstance(year, int) or year < 1992 or year > datetime.now().year:
        raise ValueError("Informe um ano válido entre 1992 e o ano atual.")
    if not months or any(not isinstance(month, int) or month < 1 or month > 12 for month in months):
        raise ValueError("Informe ao menos um mês inteiro entre 1 e 12.")
        
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        out_path.chmod(0o700)
    
    print(f"🏥 Iniciando extração SIH/SUS para UF: {state} | Ano: {year} | Meses: {months}")
    
    dfs = []
    for month in months:
        print(f"⬇️  Baixando dados de {state}/{year}-{month:02d}...")
        try:
            # pysus.sih busca as AIHs do DATASUS (RD, RJ, SP, ER)
            df_month = pysus.sih(state, year, month, as_dataframe=True)
            if df_month is not None and not df_month.empty:
                print(f"✅ Sucesso: {len(df_month):,} registros carregados para o mês {month:02d}.")
                dfs.append(df_month)
            else:
                print(f"⚠️ Aviso: Nenhum dado retornado para o mês {month:02d}.")
        except Exception:
            print(f"❌ Não foi possível baixar a competência {year}-{month:02d}.")
            
    if not dfs:
        raise RuntimeError("Nenhum dado do SIH/SUS pôde ser obtido.")
        
    df_combined = pd.concat(dfs, ignore_index=True)
    
    # Salva arquivo consolidado em data/raw/
    dest_file = out_path / f"sih_{state.lower()}_{year}_raw.parquet"
    df_combined.to_parquet(dest_file, index=False)
    print(f"💾 Base bruta salva com sucesso em: {dest_file} ({df_combined.shape[0]:,} linhas, {df_combined.shape[1]} colunas).")
    
    return dest_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extração SIH/SUS DATASUS via PySUS")
    parser.add_argument("--state", type=str, default="AC", help="UF com 2 letras (padrão: AC)")
    parser.add_argument("--year", type=int, default=2023, help="Ano da competência (padrão: 2023)")
    parser.add_argument("--month", type=int, default=1, help="Mês da competência (padrão: 1)")
    
    args = parser.parse_args()
    extract_sih_data(state=args.state, year=args.year, months=[args.month])
