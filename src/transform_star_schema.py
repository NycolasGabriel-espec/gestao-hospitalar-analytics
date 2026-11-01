"""
Pipeline ETL: Transformação dos Dados Brutos do SUS em Modelo Dimensional Star Schema
Criação das Dimensões (Tempo, Paciente, Procedimento, Diagnóstico, Leito) e Tabela Fato
Autor: Nycolas Gabriel / Healthcare Analytics
"""

import os
import hashlib
import hmac
from pathlib import Path
import pandas as pd
import duckdb
from sih_data import consolidate_aih_versions

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

def get_specialty_and_complexity(proc_code: str) -> tuple[str, str]:
    """
    Gera categorias heurísticas a partir do prefixo SIGTAP; não substitui catálogo oficial.
    """
    raw_code = str(proc_code).strip()
    if raw_code == 'SEM_INFO':
        return ("Não Informado", "Não Informada")
    code_str = raw_code.zfill(10)
    prefix_sub = code_str[:4]
    
    # 04 = Procedimentos Cirúrgicos
    if code_str.startswith("04"):
        if prefix_sub in ["0408", "0409"]:
            return ("Ortopedia & Traumatologia", "Alta Complexidade")
        elif prefix_sub in ["0406", "0407"]:
            return ("Cardiologia Cirúrgica", "Alta Complexidade")
        elif prefix_sub in ["0403", "0404"]:
            return ("Cirurgia Geral & Digestiva", "Média Complexidade")
        elif prefix_sub in ["0411", "0412"]:
            return ("Obstetrícia & Ginecologia", "Média Complexidade")
        elif prefix_sub in ["0401", "0402"]:
            return ("Neurologia & Neurocirurgia", "Alta Complexidade")
        else:
            return ("Cirurgia Geral", "Média Complexidade")
    # 03 = Procedimentos Clínicos
    elif code_str.startswith("03"):
        if prefix_sub in ["0303", "0304"]:
            return ("Clínica Médica / Infectologia", "Média Complexidade")
        elif prefix_sub in ["0301", "0302"]:
            return ("Pediatria Clínica", "Média Complexidade")
        elif prefix_sub in ["0305", "0306"]:
            return ("Oncologia Clínica", "Alta Complexidade")
        else:
            return ("Clínica Médica", "Média Complexidade")
    else:
        return ("Outras Especialidades", "Média Complexidade")

def get_cid_chapter(cid_code: str) -> str:
    """
    Mapeia um capítulo amplo pela letra do CID; não infere severidade clínica.
    """
    cid = str(cid_code).upper().strip()
    if not cid:
        return "Não Informado"
        
    letter = cid[0]
    
    if letter in ['A', 'B']:
        return "Doenças Infecciosas e Parasitárias"
    elif letter == 'C' or (
        letter == 'D' and len(cid) >= 3 and cid[1:3].isdigit() and int(cid[1:3]) <= 48
    ):
        return "Neoplasias (Tumores)"
    elif letter == 'E':
        return "Doenças Endócrinas e Metabólicas"
    elif letter == 'I':
        return "Doenças do Aparelho Circulatório"
    elif letter == 'J':
        return "Doenças do Aparelho Respiratório"
    elif letter == 'K':
        return "Doenças do Aparelho Digestivo"
    elif letter == 'M':
        return "Doenças do Sistema Osteomuscular"
    elif letter == 'O':
        return "Gravidez, Parto e Puerpério"
    elif letter == 'S' or letter == 'T':
        return "Lesões, Envenenamentos e Traumas"
    else:
        return "Outros Capítulos CID-10"

def build_star_schema(input_parquet: str, output_dir: str = "data/processed"):
    """
    Processa os dados brutos e gera o modelo Star Schema em Parquet, CSV e DuckDB.
    """
    hmac_key = os.getenv("PATIENT_DATA_HMAC_KEY", "").encode("utf-8")
    if len(hmac_key) < 32:
        raise ValueError("Defina PATIENT_DATA_HMAC_KEY com pelo menos 32 caracteres aleatórios antes de processar dados do SIH/SUS.")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        out_path.chmod(0o700)
    
    print(f"🔄 Carregando dados brutos de: {input_parquet}")
    df_raw = pd.read_parquet(input_parquet)
    print(f"📊 Registros brutos lidos: {len(df_raw):,}")
    
    # 1. Filtro e saneamento básico de colunas essenciais
    cols_necessarias = [
        'N_AIH', 'DT_INTER', 'DT_SAIDA', 'DIAS_PERM', 'QT_DIARIAS',
        'DIAG_PRINC', 'PROC_REA', 'VAL_TOT', 'SEXO', 'IDADE', 'COD_IDADE',
        'MORTE', 'UTI_MES_TO', 'ANO_CMPT', 'MES_CMPT', 'IDENT',
        'SEQ_AIH5', 'SEQUENCIA'
    ]
    campos_obrigatorios = {'N_AIH', 'DT_INTER'}
    campos_ausentes = sorted(campos_obrigatorios - set(df_raw.columns))
    if campos_ausentes:
        raise ValueError(f"O arquivo SIH/SUS não contém campos obrigatórios: {', '.join(campos_ausentes)}")

    cols_presentes = [c for c in cols_necessarias if c in df_raw.columns]
    df = df_raw[cols_presentes].copy()
    for column in set(cols_necessarias) - set(cols_presentes):
        df[column] = pd.NA
    df['N_AIH'] = df['N_AIH'].astype('string').str.strip().str.upper().str.replace(r'\.0+$', '', regex=True)
    df['N_AIH'] = df['N_AIH'].mask(df['N_AIH'].isin(['', 'NAN', 'NONE', '<NA>']))
    df = df.dropna(subset=['N_AIH']).copy()
    if df.empty:
        raise ValueError("O arquivo SIH/SUS não contém números de AIH válidos.")
    
    # Converte strings e tipos
    def pseudonymize(namespace: str, source_value: object) -> str:
        source_text = str(source_value).strip()
        source_text = source_text[:-2] if source_text.endswith('.0') else source_text
        message = f"{namespace}:{source_text}".encode("utf-8")
        return hmac.new(hmac_key, message, hashlib.sha256).hexdigest()

    def normalize_code(series: pd.Series, sentinel: str, *, width: int | None = None) -> pd.Series:
        values = series.astype('string').str.strip().str.upper()
        values = values.str.replace(r'\.0+$', '', regex=True)
        values = values.mask(values.isin(['', 'NAN', 'NONE', '<NA>']))
        if width:
            numeric = values.str.fullmatch(r'\d+', na=False)
            values.loc[numeric] = values.loc[numeric].str.zfill(width)
        return values.fillna(sentinel).astype(str)

    # Consolida revisões/continuações antes de calcular permanência e valor.
    # O mesmo resolvedor é usado pela carga dos agregados públicos do benchmark.
    df, duplicate_count = consolidate_aih_versions(df)
    if duplicate_count:
        print(
            f"ℹ️ {duplicate_count:,} linhas repetidas consolidadas por N_AIH; "
            "mantida a competência mais recente (prioridade para AIH tipo 5 em empate)."
        )

    # Normalizar códigos antes de criar dimensões e fatos para que valores
    # ausentes não virem a string "nan" e quebrem as FKs na carga.
    df['PROC_REA'] = normalize_code(df['PROC_REA'], 'SEM_INFO', width=10)
    df['DIAG_PRINC'] = normalize_code(df['DIAG_PRINC'], 'SEM_INFO')

    # O número da AIH identifica o registro de faturamento. Ele não é chave de
    # pessoa e AIHs de continuidade podem pertencer à mesma internação.
    df['id_atendimento'] = df['N_AIH'].map(lambda value: pseudonymize('atendimento', value))
    
    # Datas
    def parse_sih_date(series: pd.Series) -> pd.Series:
        values = series.astype('string').str.strip().str.replace(r'\.0+$', '', regex=True)
        return pd.to_datetime(values, format='%Y%m%d', errors='coerce')

    df['data_admissao'] = parse_sih_date(df['DT_INTER'])
    df['data_alta'] = parse_sih_date(df['DT_SAIDA'])
    
    # Mantém valores ausentes como desconhecidos; não cria alta/permanência estimadas.
    df = df.dropna(subset=['data_admissao']).copy()
    if df.empty:
        raise ValueError("Nenhum registro contém uma data de admissão válida no formato SIH/SUS YYYYMMDD.")
    
    # Métricas numéricas
    def nonnegative_integer(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors='coerce')
        values = values.where(values.ge(0) & values.mod(1).eq(0))
        return values.astype('Int64')

    # Evita datas de saída impossíveis e valores negativos/fracionários em
    # campos que representam contagens inteiras.
    df.loc[df['data_alta'] < df['data_admissao'], 'data_alta'] = pd.NaT
    df['dias_permanencia'] = nonnegative_integer(df['DIAS_PERM'])
    df['dias_uti'] = nonnegative_integer(df['UTI_MES_TO'])
    
    # VAL_TOT é o valor registrado para a AIH, não comprova receita recebida.
    df['receita_faturada'] = pd.to_numeric(df['VAL_TOT'], errors='coerce')
    # O SIH/SUS informa valores da AIH, não custos contábeis do hospital.
    # Não estime custos internos nem margem a partir desses componentes.
    unknown_amount = pd.Series(float('nan'), index=df.index, dtype='float64')
    df['custo_hospitalar'] = unknown_amount.copy()
    df['custo_servicos_profissionais'] = unknown_amount.copy()
    df['custo_opme'] = unknown_amount.copy()
    df['custo_sadt'] = unknown_amount.copy()
    df['custo_total'] = unknown_amount.copy()
    df['margem_contribuicao'] = unknown_amount.copy()
    
    # Desfecho clínico
    obito = pd.to_numeric(df['MORTE'], errors='coerce')
    df['indicador_obito'] = obito.where(obito.isin([0, 1])).astype('Int64')
    df['status_desfecho'] = df['indicador_obito'].map({
        1: 'Óbito Hospitalar',
        0: 'Saída sem óbito (tipo não classificado)',
    })
    
    # O SIH/SUS usado aqui não fornece uma chave persistente de pessoa. Não
    # agrupe registros por idade/sexo/município e não invente readmissões.
    df['id_paciente'] = df['N_AIH'].map(lambda value: pseudonymize('pessoa-nao-identificada', value))
    df['readmissao_30d'] = None
    
    # Chaves de Data
    df['id_data_admissao'] = df['data_admissao'].dt.strftime('%Y%m%d').astype(int)
    df['id_data_alta'] = df['data_alta'].dt.strftime('%Y%m%d').astype('Int64')
    
    # SIH/SUS não identifica o setor/leito assistencial desta internação.
    df['id_leito'] = 'LEITO_NAO_INFORMADO'
    
    # --------------------------------------------------------------------------
    # 2. CONSTRUÇÃO DAS TABELAS DIMENSIONAIS
    # --------------------------------------------------------------------------
    print("🛠️  Construindo Dimensões...")
    
    # DIMENSÃO TEMPO
    date_bounds = pd.concat([df['data_admissao'], df['data_alta']]).dropna()
    min_date = date_bounds.min() - pd.Timedelta(days=5)
    max_date = date_bounds.max() + pd.Timedelta(days=5)
    date_range = pd.date_range(min_date, max_date, freq='D')
    
    dim_tempo = pd.DataFrame({
        'id_data': date_range.strftime('%Y%m%d').astype(int),
        'data_completa': date_range.date,
        'ano': date_range.year,
        'mes': date_range.month,
        'dia': date_range.day,
        'nome_mes': date_range.strftime('%B'),
        'trimestre': date_range.quarter,
        'ano_mes': date_range.strftime('%Y-%m'),
        'dia_semana': date_range.strftime('%A'),
        'eh_fim_semana': date_range.dayofweek.isin([5, 6])
    })
    
    # DIMENSÃO PACIENTE
    def categorizar_faixa_etaria(idade, codigo_idade):
        try:
            valor = int(idade)
            unidade = int(codigo_idade)
            if unidade == 5:
                return '80+ anos'
            if unidade == 4:
                idade_anos = valor
            elif unidade == 3:
                idade_anos = valor / 12
            elif unidade == 2:
                idade_anos = valor / 365.25
            else:
                return 'Faixa Desconhecida'
            if idade_anos < 18:
                return '0-17 anos'
            elif idade_anos < 40:
                return '18-39 anos'
            elif idade_anos < 60:
                return '40-59 anos'
            elif idade_anos < 80:
                return '60-79 anos'
            else:
                return '80+ anos'
        except (TypeError, ValueError, OverflowError):
            return 'Faixa Desconhecida'

    age_code = df['COD_IDADE'] if 'COD_IDADE' in df.columns else pd.Series(pd.NA, index=df.index)
    df_pacientes = df[['id_paciente', 'SEXO', 'IDADE']].copy()
    df_pacientes['COD_IDADE'] = age_code
    df_pacientes = df_pacientes.drop_duplicates(subset=['id_paciente']).copy()
    dim_paciente = pd.DataFrame({
        'id_paciente': df_pacientes['id_paciente'],
        'sexo': df_pacientes['SEXO'].astype(str).map({'1': 'M', '3': 'F'}).fillna('U'),
        'faixa_etaria': [
            categorizar_faixa_etaria(idade, codigo)
            for idade, codigo in zip(df_pacientes['IDADE'], df_pacientes['COD_IDADE'])
        ],
    })
    
    # DIMENSÃO PROCEDIMENTO
    procs_unicos = df['PROC_REA'].unique()
    proc_rows = []
    for p in procs_unicos:
        especialidade, complexidade = get_specialty_and_complexity(p)
        proc_rows.append({
            'id_procedimento': str(p),
            'descricao_procedimento': 'Procedimento não informado na fonte' if p == 'SEM_INFO' else f'SIGTAP {p} (descrição/classificação a validar)',
            'especialidade': especialidade,
            'complexidade': complexidade,
            'porte_cirurgico': 'Não informado' if p == 'SEM_INFO' else ('Cirúrgico' if str(p).startswith('04') else 'Clínico'),
            'tmp_protocolo_previsto': None
        })
    dim_procedimento = pd.DataFrame(proc_rows)
    
    # DIMENSÃO DIAGNÓSTICO (CID-10)
    cids_unicos = df['DIAG_PRINC'].unique()
    cid_rows = []
    for c in cids_unicos:
        cap = get_cid_chapter(c)
        cid_rows.append({
            'cid_10': str(c).strip(),
            'descricao_cid': 'Diagnóstico não informado na fonte' if c == 'SEM_INFO' else f'CID-10 {str(c).strip()}',
            'capitulo_cid': 'Não informado na fonte' if c == 'SEM_INFO' else cap,
            'grau_severidade': 'Não classificado'
        })
    dim_diagnostico = pd.DataFrame(cid_rows)
    
    # DIMENSÃO SETOR E LEITO
    dim_setor_leito = pd.DataFrame([{
        'id_leito': 'LEITO_NAO_INFORMADO',
        'tipo_acomodacao': 'Não informado na fonte',
        'setor_hospitalar': 'Não informado na fonte',
        'leitos_operacionais': None,
    }])
    
    # TABELA FATO: fato_internacoes
    fato_internacoes = pd.DataFrame({
        'id_atendimento': df['id_atendimento'],
        'id_paciente': df['id_paciente'],
        'id_procedimento': df['PROC_REA'].astype(str),
        'cid_10': df['DIAG_PRINC'].astype(str).str.strip(),
        'id_leito': df['id_leito'],
        'id_data_admissao': df['id_data_admissao'],
        'id_data_alta': df['id_data_alta'],
        'dias_permanencia': df['dias_permanencia'],
        'dias_uti': df['dias_uti'],
        'qtd_diarias': nonnegative_integer(df['QT_DIARIAS']),
        'custo_hospitalar': df['custo_hospitalar'].round(2),
        'custo_servicos_profissionais': df['custo_servicos_profissionais'].round(2),
        'custo_opme': df['custo_opme'].round(2),
        'custo_sadt': df['custo_sadt'].round(2),
        'custo_total': df['custo_total'].round(2),
        'receita_faturada': df['receita_faturada'].round(2),
        'margem_contribuicao': df['margem_contribuicao'].round(2),
        'status_desfecho': df['status_desfecho'],
        'indicador_obito': df['indicador_obito'],
        'readmissao_30d': df['readmissao_30d']
    })
    
    # --------------------------------------------------------------------------
    # 3. EXPORTAÇÃO DOS ARQUIVOS (Parquet + CSV para Power BI)
    # --------------------------------------------------------------------------
    print("💾 Salvando tabelas processadas em data/processed/...")
    
    tabelas = {
        'fato_internacoes': fato_internacoes,
        'dim_tempo': dim_tempo,
        'dim_paciente': dim_paciente,
        'dim_procedimento': dim_procedimento,
        'dim_diagnostico': dim_diagnostico,
        'dim_setor_leito': dim_setor_leito
    }
    
    for nome, tdf in tabelas.items():
        tdf.to_parquet(out_path / f"{nome}.parquet", index=False)
        tdf.to_csv(out_path / f"{nome}.csv", index=False, sep=";")
        print(f"  -> {nome}: {len(tdf):,} registros exportados.")
        
    # --------------------------------------------------------------------------
    # 4. CARGA EM BANCO DUCKDB ANALÍTICO LOCAL
    # --------------------------------------------------------------------------
    duckdb_file = out_path / "hospital_analytics.duckdb"
    print(f"🦆 Populando banco analítico DuckDB: {duckdb_file}...")
    con = duckdb.connect(str(duckdb_file))
    
    for nome, tdf in tabelas.items():
        con.execute(f"DROP TABLE IF EXISTS {nome}")
        con.register(f"temp_{nome}", tdf)
        con.execute(f"CREATE TABLE {nome} AS SELECT * FROM temp_{nome}")
        
    con.close()
    print("✅ Pipeline ETL concluído com sucesso total!")

if __name__ == "__main__":
    import glob
    raw_files = glob.glob("data/raw/*.parquet")
    if not raw_files:
        print("❌ Nenhum arquivo bruto encontrado em data/raw/. Execute extract_sih_sus.py primeiro.")
    else:
        build_star_schema(raw_files[0])
