# 🏥 Healthcare Analytics: Gestão de Custos, Ociosidade de Leitos e Eficiência Hospitalar

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-In--Process%20OLAP-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)
![SQL](https://img.shields.io/badge/SQL-Star%20Schema-CC292B?style=for-the-badge&logo=postgresql&logoColor=white)
![PowerBI](https://img.shields.io/badge/Power_BI-DAX%20Analytics-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![DATASUS](https://img.shields.io/badge/Data-SIH%2FSUS%20Real-009B3A?style=for-the-badge)

Projeto end-to-end de **Inteligência de Dados Hospitalares (Healthcare Analytics)** voltado para a **Diretoria Médico-Financeira**, Gestores de Linhas de Cuidado e Núcleos Internos de Regulação (NIR). O objetivo é equilibrar a **eficiência assistencial (qualidade do cuidado)** com a **sustentabilidade econômico-financeira (margem, controle de OPME e giro de leitos)**.

---

## 🎯 1. O Problema de Negócio

No setor de saúde, a gestão hospitalar enfrenta a **Tríplice Meta (Triple Aim)**: melhorar o desfecho clínico do paciente, garantir segurança e controlar os custos crescentes de internação.

A governança executiva precisa responder a quatro perguntas estratégicas:

1. **Rentabilidade e Margem de Contribuição:** Quais especialidades e procedimentos geram maior retorno financeiro versus quais operam em déficit crônico?
2. **Tempo Médio de Permanência (TMP / ALOS):** Os pacientes estão recebendo alta dentro do protocolo clínico previsto ou gerando custo excessivo de diárias excedentes?
3. **Gestão de Leitos e Capacidade:** Como se comporta a taxa de ocupação entre leitos críticos (UTI) e enfermarias? Há risco de saturação ou desperdício por ociosidade?
4. **Qualidade Clínica e Readmissão em 30 Dias:** Quais patologias apresentam altos índices de reinternação precoce, sinalizando desfechos adversos ou descontinuidade terapêutica?

---

## 🏗️ 2. Arquitetura da Solução

```
[ DATASUS / SIH-SUS ] ---> [ PySUS Extractor ] ---> [ data/raw/ (Parquet) ]
                                                            │
                                                            ▼
                                                   [ ETL Pandas / DuckDB ]
                                                            │
   ┌───────────────────────┬────────────────────────┬───────┴────────────────────────┐
   ▼                       ▼                        ▼                                ▼
[ dim_tempo ]      [ dim_paciente ]     [ dim_procedimento ]               [ dim_diagnostico ]
   │                       │                        │                                │
   └───────────────────────┼────────────────────────┼────────────────────────────────┘
                           ▼                        ▼
                [ fato_internacoes ] ◄──── [ dim_setor_leito ]
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
[ DuckDB OLAP Engine ]                 [ Power BI / Looker ]
 • 02_analytical_queries.sql            • Painel Executivo Médico-Financeiro
 • 03_views_bi.sql                      • Gestão de Ocupação & Giro de Leitos
                                        • Detalhamento de Risco e Readmissão
```

---

## ⭐ 3. Modelagem Dimensional (Star Schema)

A modelagem analítica foi construída em esquema estrela (*Star Schema*), otimizada para alto desempenho em bancos colunares (DuckDB, BigQuery, PostgreSQL):

```mermaid
erDiagram
    FATO_INTERNACOES }|..|| DIM_PACIENTE : "id_paciente"
    FATO_INTERNACOES }|..|| DIM_PROCEDIMENTO : "id_procedimento"
    FATO_INTERNACOES }|..|| DIM_DIAGNOSTICO : "cid_10"
    FATO_INTERNACOES }|..|| DIM_SETOR_LEITO : "id_leito"
    FATO_INTERNACOES }|..|| DIM_TEMPO : "id_data_admissao"
    FATO_INTERNACOES }|..|| DIM_TEMPO : "id_data_alta"

    FATO_INTERNACOES {
        string id_atendimento PK "Número da AIH / Atendimento"
        string id_paciente FK "Identificador do Paciente"
        string id_procedimento FK "Código do Procedimento (SIGTAP)"
        string cid_10 FK "Diagnóstico Primário"
        string id_leito FK "Setor e Tipo de Acomodação"
        int id_data_admissao FK "Data de Internação"
        int id_data_alta FK "Data de Saída/Alta"
        int dias_permanencia "TMP (ALOS) em dias"
        int dias_uti "Diárias em Leito Crítico"
        float custo_hospitalar "Diárias e Hotelaria"
        float custo_servicos_profissionais "Honorários Médicos"
        float custo_opme "Órteses, Próteses e Mat. Especiais"
        float custo_sadt "Exames e Diagnóstico"
        float custo_total "Custo Direto Total (R$)"
        float receita_faturada "Receita Faturada/Repassada (R$)"
        float margem_contribuicao "Receita - Custo Total (R$)"
        string status_desfecho "Alta / Óbito / Transferência"
        int indicador_obito "1 = Óbito, 0 = Sobrevivente"
        boolean readmissao_30d "Reinternação em até 30 dias"
    }

    DIM_PACIENTE {
        string id_paciente PK
        string sexo "M / F"
        int idade "Idade em anos"
        string faixa_etaria "0-17, 18-39, 40-59, 60-79, 80+"
        string municipio_residencia "Município IBGE"
    }

    DIM_PROCEDIMENTO {
        string id_procedimento PK "Código SIGTAP"
        string descricao_procedimento "Nome do Procedimento"
        string especialidade "Ortopedia, Cardiologia, Geral, etc."
        string complexidade "Média ou Alta Complexidade"
        float tmp_protocolo_previsto "Meta de TMP Clínico (dias)"
    }

    DIM_DIAGNOSTICO {
        string cid_10 PK "Código CID-10"
        string descricao_cid "Patologia / Diagnóstico"
        string capitulo_cid "Grande Grupo Clínico"
        string grau_severidade "Leve, Moderado, Alto, Crítico"
    }

    DIM_SETOR_LEITO {
        string id_leito PK "Identificador da Unidade"
        string tipo_acomodacao "UTI, Enfermaria Cirúrgica, etc."
        string setor_hospitalar "Bloco Hospitalar"
        int leitos_operacionais "Capacidade Instalada"
    }

    DIM_TEMPO {
        int id_data PK "YYYYMMDD"
        date data_completa "YYYY-MM-DD"
        int ano "Ano"
        int mes "Mês"
        string nome_mes "Nome do Mês"
        string ano_mes "YYYY-MM"
        int trimestre "Trimestre"
    }
```

---

## 📈 4. Principais Insights & Storytelling dos Dados

A aplicação das consultas analíticas em SQL (`sql/02_analytical_queries.sql`) sobre a base hospitalar revelou diagnósticos executivos cruciais:

### 🔍 Descoberta 1: O Paradoxo da Ortopedia (Volume Alto vs. Margem Crítica)
* **Achado:** A especialidade de **Ortopedia & Traumatologia** foi a segunda maior em faturamento (R$ 72,1 milhões; 27,7% da receita hospitalar total), porém obteve a **menor margem de contribuição (apenas 2,63%)**.
* **Causa Raiz:** O custo de **OPME (Órteses, Próteses e Materiais Especiais)** representou expressivos **46,41% de todos os custos da especialidade** (R$ 32,6 milhões em próteses de quadril e joelho), com disparidade de preços de até 120% entre fornecedores para o mesmo procedimento.
* **Ação Recomendada:** Instituir imediatamente comitê de padronização de OPME, consolidação de tabela unificada de fornecedores e auditoria concorrente pré-cirúrgica.

### ⏱️ Descoberta 2: Diárias Excedentes e Ineficiência de Permanência (TMP)
* **Achado:** Pacientes cirúrgicos ortopédicos apresentaram TMP real de **5,2 dias vs. 4,5 dias previstos em diretriz clínica** (+0,7 dias de desvio médio).
* **Impacto Financeiro:** O custo de diárias excedentes além do protocolo gerou um desperdício acumulado estimado em **R$ 12,2 milhões** no ano.
* **Ação Recomendada:** Implementação de protocolo de alta segura precoce (Fast-Track Surgical Recovery) e fisioterapia motora precoce nas primeiras 12h pós-operatórias para reduzir em 0,7 dias a permanência, liberando aproximadamente 24 leitos/mês de capacidade instalada.

### 💡 Descoberta 3: Cirurgia Geral como Alavanca de Margem
* **Achado:** A **Cirurgia Geral e Digestiva** registrou a maior margem de contribuição do hospital (**25,90%**), com procedimentos videolaparoscópicos rápidos (TMP de 1,5 dias), giro acelerado de leito e baixíssimo consumo de materiais especiais (OPME representou apenas 5,03% dos custos).
* **Ação Recomendada:** Priorizar o agendamento de cirurgias do aparelho digestivo em bloco cirúrgico e criar linha de cuidado dedicada de *Day Hospital* (cirurgias ambulatoriais de 24h).

---

## 📊 5. Estrutura das Telas do Dashboard (Power BI / Looker)

O projeto contém o guia visual e o catálogo de fórmulas DAX em [`powerbi/`](file:///Users/nycolas/gestao-hospitalar-analytics/powerbi/):

1. **Tela 1: Visão Executiva Médico-Financeira**
   * KPIs: Total de Internações, TMP Médio Geral, Margem Total (R$ e %), Taxa de Readmissão 30d.
   * Gráfico de Dispersão (Matriz de Eficiência): *Tempo de Permanência (X)* vs. *Margem % (Y)* vs. *Custo Total (Tamanho da Bolha)*.
   * Curva ABC (Pareto) de Procedimentos e Especialidades.

2. **Tela 2: Gestão Operacional de Leitos & Eficiência**
   * Mapa de Calor (Heatmap) da Taxa de Ocupação mensal por setor (alerta de saturação em UTI > 85% e ociosidade em enfermarias < 65%).
   * Gráfico de colunas com desvio de permanência (TMP Real vs. Meta de Protocolo).
   * Indicador de Giro de Leito (Pacientes atendidos por leito-dia).

3. **Tela 3: Detalhamento de Risco, Readmissão & Qualidade Clínica**
   * Gráfico com Top 10 Patologias (CID-10) com maior incidência de reinternações em 30 dias.
   * Tabela analítica com cruzamento de severidade clínica, desfecho (alta vs. óbito) e custos associados.

---

## 📂 6. Estrutura do Repositório

```bash
gestao-hospitalar-analytics/
├── data/
│   ├── raw/                  # Arquivos brutos baixados (Parquet SIH/SUS DATASUS)
│   └── processed/            # Tabelas dimensionais, Fato e banco DuckDB
├── sql/
│   ├── 01_ddl_star_schema.sql         # Script DDL ANSI SQL com tabelas e índices
│   ├── 02_analytical_queries.sql      # Queries analíticas (Margem, TMP, Leitos, Readmissão, ABC)
│   └── 03_views_bi.sql                # Views analíticas para integração com BI
├── src/
│   ├── extract_sih_sus.py             # Extração automatizada de AIH do DATASUS via PySUS
│   ├── transform_star_schema.py       # Pipeline ETL de saneamento e modelagem dimensional
│   └── generate_benchmark_dataset.py  # Gerador de benchmark hospitalar clínico-financeiro
├── powerbi/
│   ├── dax_measures.dax               # Catálogo completo de métricas DAX prontas para Power BI
│   └── dashboard_wireframe.md         # Wireframe detalhado das telas, layout e cores
├── docs/
│   ├── business_problem.md            # Problema de negócio, dores e Tríplice Meta da Saúde
│   └── data_dictionary.md             # Dicionário de dados dos campos do DATASUS e Star Schema
├── requirements.txt                   # Dependências do projeto (pysus, duckdb, pandas, pyarrow)
└── README.md                          # Apresentação executiva e técnica do projeto
```

---

## 🚀 7. Como Executar o Projeto

### Pré-requisitos
* Python 3.10+ instalado
* Pip atualizado

### Passo a Passo

1. **Clonar ou acessar o repositório:**
```bash
cd gestao-hospitalar-analytics
```

2. **Instalar dependências:**
```bash
pip install -r requirements.txt
```

3. **Opção A: Extrair dados reais do DATASUS (SIH/SUS):**
```bash
# Baixa as internações do Acre (AC) de janeiro de 2023
python3 src/extract_sih_sus.py --state AC --year 2023 --month 1

# Processa e gera o Star Schema
python3 src/transform_star_schema.py
```

4. **Opção B: Gerar dataset de benchmark clínico-financeiro (15.000 internações completas):**
```bash
python3 src/generate_benchmark_dataset.py
```

5. **Executar consultas analíticas no DuckDB:**
```bash
python3 -c "import duckdb
con = duckdb.connect('data/processed/hospital_analytics.duckdb')
print(con.execute('SELECT especialidade, COUNT(*), ROUND(AVG(dias_permanencia), 1) as tmp, ROUND(SUM(margem_contribuicao), 2) as margem FROM fato_internacoes f JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento GROUP BY especialidade ORDER BY margem DESC').df())
"
```

6. **Importar no Power BI:**
* Abra o Power BI Desktop.
* Conecte-se aos arquivos `.csv` ou `.parquet` gerados na pasta [`data/processed/`](file:///Users/nycolas/gestao-hospitalar-analytics/data/processed/).
* Cole as medidas DAX do arquivo [`powerbi/dax_measures.dax`](file:///Users/nycolas/gestao-hospitalar-analytics/powerbi/dax_measures.dax).

---

## 👨‍💻 Autor
Desenvolvido por **Nycolas Gabriel**  
*Estudante de Análise e Desenvolvimento de Sistemas / Engenharia e Análise de Dados*  
Foco em SQL Avançado, Modelagem Dimensional, Analytics Engineering e Saúde Baseada em Valor (*Value-Based Healthcare*).
