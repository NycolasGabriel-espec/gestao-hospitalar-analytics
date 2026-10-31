"""
Gerador de Benchmark Clínico-Financeiro (Hospital Privado / Modelo DRG)
Simula faturamento de operadoras, variabilidade de OPME por cirurgião,
desvios de protocolo clínico (ALOS) e margens operacionais realistas.
Autor: Nycolas Gabriel / Healthcare Analytics
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb

def generate_benchmark_data(num_admissoes: int = 15000, output_dir: str = "data/processed", seed: int = 42):
    """
    Gera base de alta fidelidade simulando um complexo hospitalar de 220 leitos
    com 12 meses de dados, refletindo a dinâmica financeira de saúde suplementar e SUS.
    """
    np.random.seed(seed)
    random.seed(seed)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        out_path.chmod(0o700)
    
    print(f"🏥 Gerando dataset de benchmark com {num_admissoes:,} internações hospitalares...")
    
    # 1. Dimensão Procedimentos & Especialidades
    procedimentos_catalogo = [
        # Ortopedia (Alto volume de OPME, margens sensíveis)
        {"id": "0408050160", "nome": "Artroplastia Total de Quadril", "esp": "Ortopedia", "comp": "Alta Complexidade", "porte": "Grande", "tmp_proto": 4.0, "custo_base": 12500, "tem_opme": True, "opme_medio": 8200},
        {"id": "0408050152", "nome": "Artroplastia Total de Joelho", "esp": "Ortopedia", "comp": "Alta Complexidade", "porte": "Grande", "tmp_proto": 4.5, "custo_base": 14000, "tem_opme": True, "opme_medio": 9500},
        {"id": "0408040050", "nome": "Osteossíntese de Fratura de Fêmur", "esp": "Ortopedia", "comp": "Alta Complexidade", "porte": "Médio", "tmp_proto": 5.0, "custo_base": 9800, "tem_opme": True, "opme_medio": 5400},
        
        # Cardiologia (Alta gravidade, UTI prolongada)
        {"id": "0406010072", "nome": "Revascularização Miocárdica (Ponte de Safena)", "esp": "Cardiologia", "comp": "Alta Complexidade", "porte": "Grande", "tmp_proto": 6.5, "custo_base": 24000, "tem_opme": True, "opme_medio": 7800},
        {"id": "0406030049", "nome": "Angioplastia Coronariana com Stent", "esp": "Cardiologia", "comp": "Alta Complexidade", "porte": "Médio", "tmp_proto": 2.5, "custo_base": 11500, "tem_opme": True, "opme_medio": 6200},
        {"id": "0303060190", "nome": "Tratamento Clínico de Infarto Agudo do Miocárdio", "esp": "Cardiologia", "comp": "Alta Complexidade", "porte": "Clínico", "tmp_proto": 5.0, "custo_base": 8500, "tem_opme": False, "opme_medio": 0},
        
        # Cirurgia Geral & Digestiva (Alta rotatividade)
        {"id": "0407020140", "nome": "Colecistectomia Videolaparoscópica", "esp": "Cirurgia Geral", "comp": "Média Complexidade", "porte": "Médio", "tmp_proto": 1.5, "custo_base": 4200, "tem_opme": False, "opme_medio": 600},
        {"id": "0407010030", "nome": "Apendicectomia por Videolaparoscopia", "esp": "Cirurgia Geral", "comp": "Média Complexidade", "porte": "Médio", "tmp_proto": 2.0, "custo_base": 3800, "tem_opme": False, "opme_medio": 450},
        {"id": "0407040108", "nome": "Hernioplastia Inguinal Unilateral", "esp": "Cirurgia Geral", "comp": "Média Complexidade", "porte": "Pequeno", "tmp_proto": 1.0, "custo_base": 2600, "tem_opme": True, "opme_medio": 850},
        
        # Neurologia & Neurocirurgia
        {"id": "0403010098", "nome": "Craniotomia para Drenagem de Hematoma", "esp": "Neurologia", "comp": "Alta Complexidade", "porte": "Grande", "tmp_proto": 7.0, "custo_base": 28000, "tem_opme": True, "opme_medio": 8900},
        {"id": "0303040157", "nome": "Tratamento de Acidente Vascular Cerebral (AVC)", "esp": "Neurologia", "comp": "Alta Complexidade", "porte": "Clínico", "tmp_proto": 6.0, "custo_base": 12000, "tem_opme": False, "opme_medio": 0},
        
        # Oncologia
        {"id": "0416010080", "nome": "Ressecção de Tumor Colorretal", "esp": "Oncologia", "comp": "Alta Complexidade", "porte": "Grande", "tmp_proto": 6.0, "custo_base": 18500, "tem_opme": True, "opme_medio": 3200},
        {"id": "0304020100", "nome": "Quimioterapia de Alta Complexidade", "esp": "Oncologia", "comp": "Alta Complexidade", "porte": "Clínico", "tmp_proto": 3.0, "custo_base": 9200, "tem_opme": False, "opme_medio": 0},
        
        # Clínica Médica & Respiratório
        {"id": "0303010037", "nome": "Tratamento de Pneumonia Grave / Insuficiência Respiratória", "esp": "Clínica Médica", "comp": "Média Complexidade", "porte": "Clínico", "tmp_proto": 5.5, "custo_base": 6500, "tem_opme": False, "opme_medio": 0},
        {"id": "0303010061", "nome": "Tratamento de Sepse / Choque Séptico", "esp": "Clínica Médica", "comp": "Alta Complexidade", "porte": "Clínico", "tmp_proto": 8.0, "custo_base": 22000, "tem_opme": False, "opme_medio": 0}
    ]
    
    dim_procedimento = pd.DataFrame([
        {
            "id_procedimento": p["id"],
            "descricao_procedimento": p["nome"],
            "especialidade": p["esp"],
            "complexidade": p["comp"],
            "porte_cirurgico": p["porte"],
            "tmp_protocolo_previsto": p["tmp_proto"]
        } for p in procedimentos_catalogo
    ])
    
    # 2. Dimensão Diagnósticos (CID-10)
    cids_catalogo = [
        {"cid": "I21.9", "desc": "Infarto agudo do miocárdio, não especificado", "cap": "Doenças do Aparelho Circulatório", "sev": "Crítico"},
        {"cid": "I50.0", "desc": "Insuficiência cardíaca congestiva", "cap": "Doenças do Aparelho Circulatório", "sev": "Alto"},
        {"cid": "I64", "desc": "Acidente vascular cerebral, não especificado", "cap": "Doenças do Aparelho Circulatório", "sev": "Crítico"},
        {"cid": "M16.1", "desc": "Coxartrose primária (Artrose de quadril)", "cap": "Doenças Osteomusculares", "sev": "Moderado"},
        {"cid": "M17.1", "desc": "Gonartrose primária (Artrose de joelho)", "cap": "Doenças Osteomusculares", "sev": "Moderado"},
        {"cid": "S72.0", "desc": "Fratura do colo do fêmur", "cap": "Traumas e Fraturas", "sev": "Alto"},
        {"cid": "K80.2", "desc": "Cálculo da vesícula biliar sem colecistite", "cap": "Doenças do Aparelho Digestivo", "sev": "Moderado"},
        {"cid": "K35.8", "desc": "Apendicite aguda, outras e não especificadas", "cap": "Doenças do Aparelho Digestivo", "sev": "Moderado"},
        {"cid": "K40.9", "desc": "Hérnia inguinal unilateral", "cap": "Doenças do Aparelho Digestivo", "sev": "Leve"},
        {"cid": "J18.9", "desc": "Pneumonia bacteriana não especificada", "cap": "Doenças do Aparelho Respiratório", "sev": "Alto"},
        {"cid": "J44.1", "desc": "Doença pulmonar obstrutiva crônica com exacerbação", "cap": "Doenças do Aparelho Respiratório", "sev": "Alto"},
        {"cid": "A41.9", "desc": "Sepse não especificada", "cap": "Doenças Infecciosas", "sev": "Crítico"},
        {"cid": "C18.9", "desc": "Neoplasia maligna do cólon", "cap": "Neoplasias (Tumores)", "sev": "Alto"}
    ]
    
    dim_diagnostico = pd.DataFrame([
        {
            "cid_10": c["cid"],
            "descricao_cid": c["desc"],
            "capitulo_cid": c["cap"],
            "grau_severidade": c["sev"]
        } for c in cids_catalogo
    ])
    
    # 3. Dimensão Setor e Leito
    dim_setor_leito = pd.DataFrame([
        {"id_leito": "LEITO_UTI_01", "tipo_acomodacao": "UTI Adulto & Crítica", "setor_hospitalar": "Pavilhão Intensivo Central", "leitos_operacionais": 30},
        {"id_leito": "LEITO_CIR_01", "tipo_acomodacao": "Enfermaria Cirúrgica & PO", "setor_hospitalar": "Bloco Cirúrgico Ala B", "leitos_operacionais": 70},
        {"id_leito": "LEITO_ENF_01", "tipo_acomodacao": "Enfermaria Clínica Geral", "setor_hospitalar": "Ala de Internação Clínica", "leitos_operacionais": 120}
    ])
    
    # 4. Dimensão Tempo (Ano de 2023 completo)
    data_inicio = datetime(2023, 1, 1)
    datas = [data_inicio + timedelta(days=i) for i in range(365)]
    dim_tempo = pd.DataFrame({
        "id_data": [int(d.strftime("%Y%m%d")) for d in datas],
        "data_completa": [d.date() for d in datas],
        "ano": [d.year for d in datas],
        "mes": [d.month for d in datas],
        "dia": [d.day for d in datas],
        "nome_mes": [d.strftime("%B") for d in datas],
        "trimestre": [(d.month - 1) // 3 + 1 for d in datas],
        "ano_mes": [d.strftime("%Y-%m") for d in datas],
        "dia_semana": [d.strftime("%A") for d in datas],
        "eh_fim_semana": [d.weekday() in [5, 6] for d in datas]
    })
    
    # 5. Pacientes e Admissões
    num_pacientes = int(num_admissoes * 0.72) # Permite readmissões realistas
    faixas = ["0-17 anos", "18-39 anos", "40-59 anos", "60-79 anos", "80+ anos"]
    faixas_prob = [0.08, 0.22, 0.30, 0.28, 0.12]
    
    pacientes_list = []
    for i in range(num_pacientes):
        p_id = f"PAC_{i+1:06d}"
        fx = np.random.choice(faixas, p=faixas_prob)
        if fx == "0-17 anos":
            idade = random.randint(1, 17)
        elif fx == "18-39 anos":
            idade = random.randint(18, 39)
        elif fx == "40-59 anos":
            idade = random.randint(40, 59)
        elif fx == "60-79 anos":
            idade = random.randint(60, 79)
        else:
            idade = random.randint(80, 96)
        sexo = random.choice(["M", "F"])
        pacientes_list.append({"id_paciente": p_id, "sexo": sexo, "idade": idade, "faixa_etaria": fx, "municipio_residencia": "Capital", "uf_residencia": "BR"})
    
    # Preserve only the age band in the exported dimension.
    dim_paciente = pd.DataFrame([
        {"id_paciente": p["id_paciente"], "sexo": p["sexo"], "faixa_etaria": p["faixa_etaria"]}
        for p in pacientes_list
    ])
    
    # Gerando Fato Internações
    fato_rows = []
    # Pesos de probabilidade para os procedimentos
    proc_weights = [0.08, 0.07, 0.09, 0.06, 0.11, 0.10, 0.12, 0.08, 0.06, 0.04, 0.05, 0.03, 0.04, 0.05, 0.02]
    proc_weights = np.array(proc_weights) / sum(proc_weights)
    
    # Mapeamento Procedimento -> CID provável
    map_proc_cid = {
        "0408050160": "M16.1", "0408050152": "M17.1", "0408040050": "S72.0",
        "0406010072": "I21.9", "0406030049": "I21.9", "0303060190": "I21.9",
        "0407020140": "K80.2", "0407010030": "K35.8", "0407040108": "K40.9",
        "0403010098": "I64", "0303040157": "I64", "0416010080": "C18.9",
        "0304020100": "C18.9", "0303010037": "J18.9", "0303010061": "A41.9"
    }
    
    for i in range(num_admissoes):
        atend_id = f"ATD_2023_{i+1:06d}"
        pac = random.choice(pacientes_list)
        p_idx = np.random.choice(len(procedimentos_catalogo), p=proc_weights)
        proc = procedimentos_catalogo[p_idx]
        cid = map_proc_cid[proc["id"]]
        
        # Data de admissão distribuída ao longo de 2023
        dt_adm = data_inicio + timedelta(days=random.randint(0, 350))
        
        # Tempo de permanência: distribuição log-normal centrada no protocolo
        alvo_tmp = proc["tmp_proto"]
        # Especialidade Ortopedia e Clínica têm maior tendência a atraso de alta
        if proc["esp"] == "Ortopedia":
            dias_perm = max(1, int(np.random.normal(alvo_tmp + 1.2, 1.8)))
        elif proc["esp"] == "Cardiologia":
            dias_perm = max(1, int(np.random.normal(alvo_tmp + 0.8, 2.2)))
        else:
            dias_perm = max(1, int(np.random.normal(alvo_tmp, 1.2)))
            
        dt_alta = dt_adm + timedelta(days=dias_perm)
        
        # Leito e UTI
        if proc["esp"] in ["Cardiologia", "Neurologia"] or proc["nome"].find("Sepse") != -1:
            dias_uti = min(dias_perm, random.randint(1, max(1, dias_perm - 1)))
            id_leito = "LEITO_UTI_01"
        elif proc["porte"] in ["Grande", "Médio"]:
            dias_uti = 0
            id_leito = "LEITO_CIR_01"
        else:
            dias_uti = 0
            id_leito = "LEITO_ENF_01"
            
        # Custos Hospitalares e OPME
        # Em Ortopedia, simula forte variabilidade de custo de OPME (próteses)
        if proc["tem_opme"]:
            # Cirurgiões com grande dispersão de custo de próteses
            fator_opme = np.random.uniform(0.75, 1.65)
            custo_opme = round(proc["opme_medio"] * fator_opme, 2)
        else:
            custo_opme = 0.0
            
        custo_diarias_hosp = round(dias_perm * 850.0 + (dias_uti * 1800.0), 2)
        custo_sp = round(proc["custo_base"] * 0.35 + np.random.normal(500, 150), 2)
        custo_sadt = round(np.random.uniform(400, 2200), 2)
        custo_total = round(custo_diarias_hosp + custo_sp + custo_opme + custo_sadt, 2)
        
        # Receita Faturada (com base no pacote negociado com a operadora/SUS)
        # Ortopedia sofre achatamento de margem pelo custo descontrolado de OPME
        if proc["esp"] == "Ortopedia":
            # Margem comprimida (entre -8% e +8%)
            fator_receita = np.random.uniform(0.95, 1.10)
            receita = round((proc["custo_base"] + proc["opme_medio"]) * fator_receita, 2)
        elif proc["esp"] == "Cirurgia Geral":
            # Procedimentos rápidos videolaparoscópicos têm alta margem (> 25%)
            fator_receita = np.random.uniform(1.25, 1.45)
            receita = round(custo_total * fator_receita, 2)
        else:
            fator_receita = np.random.uniform(1.10, 1.30)
            receita = round(custo_total * fator_receita, 2)
            
        margem = round(receita - custo_total, 2)
        
        # Desfecho clínico
        prob_obito = 0.12 if proc["nome"].find("Sepse") != -1 else (0.05 if dias_uti > 0 else 0.008)
        obito = 1 if (random.random() < prob_obito) else 0
        desfecho = "Óbito Hospitalar" if obito == 1 else "Alta Curado/Melhorado"
        
        # Readmissão em 30 dias (maior em idosos, cardiopatias e pós-op ortopédico com complicação)
        prob_readm = 0.14 if (proc["esp"] == "Ortopedia" and dias_perm > alvo_tmp) else (0.12 if cid in ["I50.0", "J44.1"] else 0.05)
        readmissao = (obito == 0 and random.random() < prob_readm)
        
        fato_rows.append({
            "id_atendimento": atend_id,
            "id_paciente": pac["id_paciente"],
            "id_procedimento": proc["id"],
            "cid_10": cid,
            "id_leito": id_leito,
            "id_data_admissao": int(dt_adm.strftime("%Y%m%d")),
            "id_data_alta": int(dt_alta.strftime("%Y%m%d")),
            "dias_permanencia": dias_perm,
            "dias_uti": dias_uti,
            "qtd_diarias": dias_perm,
            "custo_hospitalar": custo_diarias_hosp,
            "custo_servicos_profissionais": custo_sp,
            "custo_opme": custo_opme,
            "custo_sadt": custo_sadt,
            "custo_total": custo_total,
            "receita_faturada": receita,
            "margem_contribuicao": margem,
            "status_desfecho": desfecho,
            "indicador_obito": obito,
            "readmissao_30d": readmissao
        })
        
    fato_internacoes = pd.DataFrame(fato_rows)
    
    # Exportação
    tabelas = {
        "fato_internacoes": fato_internacoes,
        "dim_tempo": dim_tempo,
        "dim_paciente": dim_paciente,
        "dim_procedimento": dim_procedimento,
        "dim_diagnostico": dim_diagnostico,
        "dim_setor_leito": dim_setor_leito
    }
    
    print(f"💾 Salvando tabelas de benchmark em {output_dir}...")
    for nome, tdf in tabelas.items():
        tdf.to_parquet(out_path / f"{nome}.parquet", index=False)
        tdf.to_csv(out_path / f"{nome}.csv", index=False, sep=";")
        print(f"  -> {nome}: {len(tdf):,} registros.")
        
    # Salva no DuckDB
    duckdb_file = out_path / "hospital_analytics.duckdb"
    con = duckdb.connect(str(duckdb_file))
    for nome, tdf in tabelas.items():
        con.execute(f"DROP TABLE IF EXISTS {nome}")
        con.register(f"temp_{nome}", tdf)
        con.execute(f"CREATE TABLE {nome} AS SELECT * FROM temp_{nome}")
    con.close()
    
    print(f"🚀 Benchmark concluído com sucesso e gravado em {duckdb_file}!")

if __name__ == "__main__":
    generate_benchmark_data(num_admissoes=15000)
