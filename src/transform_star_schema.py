"""
Pipeline ETL: Transformação dos Dados Brutos do SUS em Modelo Dimensional Star Schema
Criação das Dimensões (Tempo, Paciente, Procedimento, Diagnóstico, Leito) e Tabela Fato
Autor: Nycolas Gabriel / Healthcare Analytics
"""

import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import duckdb

def get_specialty_and_protocol(proc_code: str) -> tuple[str, str, float]:
    """
    Classifica a especialidade médica, complexidade e TMP de protocolo esperado
    a partir dos prefixos e regras da Tabela Unificada de Procedimentos do SUS (SIGTAP).
    """
    code_str = str(proc_code).zfill(10)
    prefix_sub = code_str[:4]
    
    # 04 = Procedimentos Cirúrgicos
    if code_str.startswith("04"):
        if prefix_sub in ["0408", "0409"]:
            return ("Ortopedia & Traumatologia", "Alta Complexidade", 4.0)
        elif prefix_sub in ["0406", "0407"]:
            return ("Cardiologia Cirúrgica", "Alta Complexidade", 5.5)
        elif prefix_sub in ["0403", "0404"]:
            return ("Cirurgia Geral & Digestiva", "Média Complexidade", 3.0)
        elif prefix_sub in ["0411", "0412"]:
            return ("Obstetrícia & Ginecologia", "Média Complexidade", 2.0)
        elif prefix_sub in ["0401", "0402"]:
            return ("Neurologia & Neurocirurgia", "Alta Complexidade", 6.0)
        else:
            return ("Cirurgia Geral", "Média Complexidade", 3.5)
    # 03 = Procedimentos Clínicos
    elif code_str.startswith("03"):
        if prefix_sub in ["0303", "0304"]:
            return ("Clínica Médica / Infectologia", "Média Complexidade", 4.5)
        elif prefix_sub in ["0301", "0302"]:
            return ("Pediatria Clínica", "Média Complexidade", 3.0)
        elif prefix_sub in ["0305", "0306"]:
            return ("Oncologia Clínica", "Alta Complexidade", 5.0)
        else:
            return ("Clínica Médica", "Média Complexidade", 4.0)
    else:
        return ("Outras Especialidades", "Média Complexidade", 3.0)

def get_cid_chapter_and_severity(cid_code: str) -> tuple[str, str, str]:
    """
    Mapeia os grandes capítulos da CID-10 e infere severidade clínica estimada.
    """
    cid = str(cid_code).upper().strip()
    if not cid:
        return ("Não Informado", "Não Classificado", "Leve")
        
    letter = cid[0]
    
    if letter in ['A', 'B']:
        return ("Doenças Infecciosas e Parasitárias", "Gastroenterite / Sepse / Infecções", "Moderado")
    elif letter == 'C' or (letter == 'D' and cid[1:3] <= '48'):
        return ("Neoplasias (Tumores)", "Câncer e Doenças Hematológicas", "Alto")
    elif letter == 'E':
        return ("Doenças Endócrinas e Metabólicas", "Diabetes / Distúrbios Metabólicos", "Moderado")
    elif letter == 'I':
        return ("Doenças do Aparelho Circulatório", "Infarto, AVC, Insuficiência Cardíaca", "Crítico")
    elif letter == 'J':
        return ("Doenças do Aparelho Respiratório", "Pneumonia, DPOC, Asma Aguda", "Alto")
    elif letter == 'K':
        return ("Doenças do Aparelho Digestivo", "Apendicite, Hérnia, Colecistite", "Moderado")
    elif letter == 'M':
        return ("Doenças do Sistema Osteomuscular", "Artrose, Fraturas Patológicas, Deformidades", "Moderado")
    elif letter == 'O':
        return ("Gravidez, Parto e Puerpério", "Parto Cesáreo / Normal e Complicações", "Leve")
    elif letter == 'S' or letter == 'T':
        return ("Lesões, Envenenamentos e Traumas", "Fraturas, Politraumas, Acidentes", "Alto")
    else:
        return ("Outros Capítulos CID-10", "Condições Clínicas Diversas", "Moderado")

def build_star_schema(input_parquet: str, output_dir: str = "data/processed"):
    """
    Processa os dados brutos e gera o modelo Star Schema em Parquet, CSV e DuckDB.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    print(f"🔄 Carregando dados brutos de: {input_parquet}")
    df_raw = pd.read_parquet(input_parquet)
    print(f"📊 Registros brutos lidos: {len(df_raw):,}")
    
    # 1. Filtro e saneamento básico de colunas essenciais
    cols_necessarias = [
        'N_AIH', 'DT_INTER', 'DT_SAIDA', 'DIAS_PERM', 'DIAG_PRINC', 'PROC_REA',
        'VAL_TOT', 'VAL_SH', 'VAL_SP', 'VAL_ORTP', 'VAL_SADT', 'VAL_UTI',
        'SEXO', 'IDADE', 'MORTE', 'COBRANCA', 'CNES', 'UTI_MES_TO', 'MUNIC_RES'
    ]
    cols_presentes = [c for c in cols_necessarias if c in df_raw.columns]
    df = df_raw[cols_presentes].copy()
    
    # Converte strings e tipos
    df['id_atendimento'] = df['N_AIH'].astype(str)
    
    # Datas
    df['data_admissao'] = pd.to_datetime(df['DT_INTER'].astype(str).str.strip(), format='%Y%m%d', errors='coerce')
    df['data_alta'] = pd.to_datetime(df['DT_SAIDA'].astype(str).str.strip(), format='%Y%m%d', errors='coerce')
    
    # Preenchimento de datas nulas caso necessário
    df = df.dropna(subset=['data_admissao']).copy()
    df['data_alta'] = df['data_alta'].fillna(df['data_admissao'] + pd.to_timedelta(df['DIAS_PERM'].fillna(1).astype(int), unit='D'))
    
    # Métricas numéricas
    df['dias_permanencia'] = pd.to_numeric(df['DIAS_PERM'], errors='coerce').fillna(1).astype(int)
    # Se dias de permanência for 0 (alta no mesmo dia), ajusta para 1 leito-dia
    df['dias_permanencia'] = df['dias_permanencia'].apply(lambda x: 1 if x <= 0 else x)
    df['dias_uti'] = pd.to_numeric(df.get('UTI_MES_TO', 0), errors='coerce').fillna(0).astype(int)
    
    # Valores financeiros (R$)
    df['receita_faturada'] = pd.to_numeric(df['VAL_TOT'], errors='coerce').fillna(0.0)
    df['custo_hospitalar'] = pd.to_numeric(df['VAL_SH'], errors='coerce').fillna(0.0)
    df['custo_servicos_profissionais'] = pd.to_numeric(df['VAL_SP'], errors='coerce').fillna(0.0)
    df['custo_opme'] = pd.to_numeric(df.get('VAL_ORTP', 0.0), errors='coerce').fillna(0.0)
    df['custo_sadt'] = pd.to_numeric(df.get('VAL_SADT', 0.0), errors='coerce').fillna(0.0)
    
    # Custo direto total
    df['custo_total'] = df['custo_hospitalar'] + df['custo_servicos_profissionais'] + df['custo_opme'] + df['custo_sadt']
    # Caso custo_total seja 0, aloca baseado em percentual da receita
    df.loc[df['custo_total'] <= 0, 'custo_total'] = df['receita_faturada'] * 0.85
    
    # Margem de Contribuição
    df['margem_contribuicao'] = df['receita_faturada'] - df['custo_total']
    
    # Desfecho clínico
    df['indicador_obito'] = pd.to_numeric(df.get('MORTE', 0), errors='coerce').fillna(0).astype(int)
    df['status_desfecho'] = df['indicador_obito'].apply(lambda x: 'Óbito Hospitalar' if x == 1 else 'Alta Curado/Melhorado')
    
    # ID Paciente (Hash anônimo determinístico com base em município, idade, sexo)
    df['id_paciente'] = df.apply(
        lambda r: hashlib.md5(f"{r.get('MUNIC_RES','')}-{r.get('IDADE','')}-{r.get('SEXO','')}-{r.name % 300}".encode()).hexdigest()[:16],
        axis=1
    )
    
    # Cálculo de Readmissão em 30 Dias (pacientes com mais de 1 internação dentro da janela de 30 dias)
    df = df.sort_values(by=['id_paciente', 'data_admissao'])
    df['prev_alta'] = df.groupby('id_paciente')['data_alta'].shift(1)
    df['dias_desde_ultima_alta'] = (df['data_admissao'] - df['prev_alta']).dt.days
    df['readmissao_30d'] = df['dias_desde_ultima_alta'].apply(lambda d: True if (pd.notnull(d) and 0 <= d <= 30) else False)
    
    # Chaves de Data
    df['id_data_admissao'] = df['data_admissao'].dt.strftime('%Y%m%d').astype(int)
    df['id_data_alta'] = df['data_alta'].dt.strftime('%Y%m%d').astype(int)
    
    # Alocação de Setor e Leito
    def alocar_leito(r):
        if r['dias_uti'] > 0:
            return 'LEITO_UTI_01'
        elif str(r['PROC_REA']).startswith('04'):
            return 'LEITO_CIR_01'
        else:
            return 'LEITO_ENF_01'
    df['id_leito'] = df.apply(alocar_leito, axis=1)
    
    # --------------------------------------------------------------------------
    # 2. CONSTRUÇÃO DAS TABELAS DIMENSIONAIS
    # --------------------------------------------------------------------------
    print("🛠️  Construindo Dimensões...")
    
    # DIMENSÃO TEMPO
    min_date = df['data_admissao'].min() - pd.Timedelta(days=5)
    max_date = df['data_alta'].max() + pd.Timedelta(days=5)
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
    def categorizar_faixa_etaria(idade):
        try:
            idade_int = int(idade)
            if idade_int < 18:
                return '0-17 anos'
            elif idade_int < 40:
                return '18-39 anos'
            elif idade_int < 60:
                return '40-59 anos'
            elif idade_int < 80:
                return '60-79 anos'
            else:
                return '80+ anos'
        except:
            return 'Faixa Desconhecida'
            
    df_pacientes = df[['id_paciente', 'SEXO', 'IDADE', 'MUNIC_RES']].drop_duplicates(subset=['id_paciente']).copy()
    dim_paciente = pd.DataFrame({
        'id_paciente': df_pacientes['id_paciente'],
        'sexo': df_pacientes['SEXO'].astype(str).map({'1': 'M', '3': 'F'}).fillna('M'),
        'idade': pd.to_numeric(df_pacientes['IDADE'], errors='coerce').fillna(45).astype(int),
        'faixa_etaria': df_pacientes['IDADE'].apply(categorizar_faixa_etaria),
        'municipio_residencia': df_pacientes['MUNIC_RES'].astype(str),
        'uf_residencia': 'BR'
    })
    
    # DIMENSÃO PROCEDIMENTO
    procs_unicos = df['PROC_REA'].dropna().unique()
    proc_rows = []
    for p in procs_unicos:
        especialidade, complexidade, tmp_proto = get_specialty_and_protocol(p)
        desc = f"Procedimento SUS {p} - {especialidade}"
        proc_rows.append({
            'id_procedimento': str(p),
            'descricao_procedimento': desc,
            'especialidade': especialidade,
            'complexidade': complexidade,
            'porte_cirurgico': 'Cirúrgico' if str(p).startswith('04') else 'Clínico',
            'tmp_protocolo_previsto': tmp_proto
        })
    dim_procedimento = pd.DataFrame(proc_rows)
    
    # DIMENSÃO DIAGNÓSTICO (CID-10)
    cids_unicos = df['DIAG_PRINC'].dropna().unique()
    cid_rows = []
    for c in cids_unicos:
        cap, desc, severidade = get_cid_chapter_and_severity(c)
        cid_rows.append({
            'cid_10': str(c).strip(),
            'descricao_cid': desc,
            'capitulo_cid': cap,
            'grau_severidade': severidade
        })
    dim_diagnostico = pd.DataFrame(cid_rows)
    
    # DIMENSÃO SETOR E LEITO
    dim_setor_leito = pd.DataFrame([
        {
            'id_leito': 'LEITO_UTI_01',
            'tipo_acomodacao': 'UTI Adulto & Crítica',
            'setor_hospitalar': 'Pavilhão Intensivo Central',
            'leitos_operacionais': 30
        },
        {
            'id_leito': 'LEITO_CIR_01',
            'tipo_acomodacao': 'Enfermaria Cirúrgica & PO',
            'setor_hospitalar': 'Bloco Cirúrgico Ala B',
            'leitos_operacionais': 70
        },
        {
            'id_leito': 'LEITO_ENF_01',
            'tipo_acomodacao': 'Enfermaria Clínica Geral',
            'setor_hospitalar': 'Ala de Internação Clínica',
            'leitos_operacionais': 120
        }
    ])
    
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
        'qtd_diarias': df['dias_permanencia'],
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
