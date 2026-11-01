# 🏥 Healthcare Analytics: Gestão de Custos, Ociosidade de Leitos e Eficiência Hospitalar

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8%2B-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-In--Process%20OLAP-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)
![SQL](https://img.shields.io/badge/SQL-Star%20Schema-CC292B?style=for-the-badge&logo=mysql&logoColor=white)
![PowerBI](https://img.shields.io/badge/Power_BI-DAX%20Analytics-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![DATASUS](https://img.shields.io/badge/Data-SIH%2FSUS%20%2B%20Benchmark-009B3A?style=for-the-badge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Protótipo de analytics hospitalar com recortes públicos reais do SIH/SUS, CNES e SISREG de Alagoas, além de um cenário sintético separado para exploração local no Streamlit. Valores de AIH e aproximações de ocupação são identificados com seus limites de interpretação.

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
[ DuckDB / MySQL ]                     [ Streamlit / Power BI ]
 • 02_analytical_queries.sql            • Painel Executivo Médico-Financeiro
                                       • Benchmark sintético interativo
 • sql/mysql_setup.sql                  • Detalhamento de Risco e Readmissão
```

---

## ⭐ 3. Modelagem Dimensional (Star Schema)

A modelagem analítica foi construída em esquema estrela (*Star Schema*), compatível com DuckDB e MySQL 8+:

```mermaid
erDiagram
    FATO_INTERNACOES }|..|| DIM_PACIENTE : "id_paciente"
    FATO_INTERNACOES }|..|| DIM_PROCEDIMENTO : "id_procedimento"
    FATO_INTERNACOES }|..|| DIM_DIAGNOSTICO : "cid_10"
    FATO_INTERNACOES }|..|| DIM_SETOR_LEITO : "id_leito"
    FATO_INTERNACOES }|..|| DIM_TEMPO : "id_data_admissao"
    FATO_INTERNACOES }|..|| DIM_TEMPO : "id_data_alta"

    FATO_INTERNACOES {
        string id_atendimento PK "HMAC do identificador de origem"
        string id_paciente FK "HMAC de AIH nesta fonte; não identifica pessoa persistente"
        string id_procedimento FK "Código do Procedimento (SIGTAP)"
        string cid_10 FK "Diagnóstico Primário"
        string id_leito FK "Setor e Tipo de Acomodação"
        int id_data_admissao FK "Data de Internação"
        int id_data_alta FK "Data de Saída/Alta"
        int dias_permanencia "NULL quando ausente na fonte"
        int dias_uti "NULL quando ausente na fonte"
        float custo_hospitalar "NULL sem fonte contábil validada"
        float custo_servicos_profissionais "NULL sem fonte contábil validada"
        float custo_opme "NULL sem fonte contábil validada"
        float custo_sadt "NULL sem fonte contábil validada"
        float custo_total "NULL sem fonte contábil validada"
        float receita_faturada "Valor registrado da AIH; não comprova recebimento"
        float margem_contribuicao "NULL sem custos e receitas contábeis validados"
        string status_desfecho "NULL quando ausente ou não classificável"
        int indicador_obito "NULL quando não informado ou inválido"
        boolean readmissao_30d "NULL para SIH/SUS neste pipeline"
    }

    DIM_PACIENTE {
        string id_paciente PK "HMAC de AIH; não representa uma pessoa"
        string sexo "M / F"
        string faixa_etaria "0-17, 18-39, 40-59, 60-79, 80+"
    }

    DIM_PROCEDIMENTO {
        string id_procedimento PK "Código SIGTAP"
        string descricao_procedimento "Nome do Procedimento"
        string especialidade "Classificação heurística a validar"
        string complexidade "Classificação heurística a validar"
        float tmp_protocolo_previsto "NULL sem protocolo clínico aprovado"
    }

    DIM_DIAGNOSTICO {
        string cid_10 PK "Código CID-10"
        string descricao_cid "Código CID-10; descrição externa não incluída"
        string capitulo_cid "Agrupamento amplo aproximado"
        string grau_severidade "Não classificado sem fonte validada"
    }

    DIM_SETOR_LEITO {
        string id_leito PK "Identificador da Unidade"
        string tipo_acomodacao "Não informado quando a fonte não identifica leito"
        string setor_hospitalar "Não informado quando a fonte não identifica setor"
        int leitos_operacionais "NULL quando a capacidade é desconhecida"
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

## 📈 4. Escopo e limites dos dados

O dataset gerado por `src/generate_benchmark_dataset.py` continua simulado e serve apenas para demonstração técnica no Streamlit. O dashboard HTML da Vercel usa dados públicos agregados reais: SIH/SUS de 2025, capacidade CNES mensal e fila SISREG estadual em uma extração de agosto de 2025. Valor de AIH não é custo hospitalar e ocupação SIH/CNES é uma estimativa, não um censo. Consulte [fontes, fórmulas e limitações](docs/public_sus_dashboard.md).

No fluxo SIH/SUS, a chave AIH é pseudonimizada com HMAC e não representa uma pessoa persistente. Por isso, a readmissão em 30 dias fica desconhecida (`NULL`) para dados reais. Os arquivos transformados mantêm dados clínicos por internação e continuam sendo dados sensíveis; pseudonimização não equivale a anonimização.

O código e a documentação próprios deste projeto são distribuídos sob a licença MIT. Dados públicos de terceiros, marcas, bibliotecas e outros materiais mantêm os termos definidos por seus respectivos titulares; a licença do projeto não os substitui.

---

## 📊 5. Estrutura das Telas do Dashboard (Streamlit / Power BI / Looker)

O projeto contém o dashboard HTML conectado às rotas autenticadas, wireframes e fórmulas DAX em [`powerbi/`](powerbi/). A página inicial e o Streamlit apresentam exemplos sintéticos; no dashboard autenticado, o **Panorama de internações fica limitado às admissões de janeiro a dezembro de 2025** em Alagoas. O benchmark público separado consulta agregados do SIH/SUS, CNES e SISREG.

1. **Tela 1: Visão Executiva Médico-Financeira**
   * KPIs: Total de Internações e TMP Médio. Margem e valores financeiros só aparecem com uma fonte contábil validada; readmissão exige uma fonte com identificador de pessoa apropriado.
   * Gráfico de Dispersão (Matriz de Eficiência): *Tempo de Permanência (X)* vs. *Margem % (Y)* vs. *Custo Total (Tamanho da Bolha)*.
   * Curva ABC (Pareto) de Procedimentos e Especialidades.

2. **Tela 2: Gestão Operacional de Leitos & Eficiência**
   * Mapa de Calor da ocupação somente após integrar capacidade instalada por setor; o SIH/SUS deste pipeline não fornece esse dado.
   * Gráfico de colunas com desvio de permanência (TMP Real vs. Meta de Protocolo).
   * Indicador de Giro de Leito (Pacientes atendidos por leito-dia).

3. **Tela 3: Detalhamento de Risco, Readmissão & Qualidade Clínica**
   * Gráfico com indicadores por coorte; a readmissão fica indisponível para o fluxo SIH/SUS atual.
   * Coortes agregadas para indicadores disponíveis; severidade clínica não é inferida do CID, e custos ficam vazios sem fonte contábil validada.

---

## 📂 6. Estrutura do Repositório

```bash
gestao-hospitalar-analytics/
├── data/
│   ├── raw/                  # Arquivos brutos baixados (Parquet SIH/SUS DATASUS)
│   ├── processed/            # Tabelas dimensionais, Fato e banco DuckDB
│   └── benchmark/            # Benchmark sintético local (gerado, não versionado)
├── sql/
│   ├── mysql_setup.sql                # Star Schema, contas e views agregadas no MySQL
│   ├── 06_benchmark_mysql.sql         # Tabelas e views separadas para o benchmark sintético
│   ├── 07_public_sus_mysql.sql        # Views SIH/SUS e tabelas agregadas CNES/SISREG
│   ├── 08_panorama_2025_mysql.sql     # Ano de admissão no detalhe clínico para o recorte 2025
│   ├── 09_hospital_pilot_mysql.sql    # Banco isolado para contratos agregados do piloto
│   ├── mysql_grants.sql               # Permissões mínimas das contas web, ETL e BI
│   ├── 02_analytical_queries.sql      # Queries analíticas (Margem, TMP, Leitos, Readmissão, ABC)
│   └── 03_views_bi.sql                # Nota de compatibilidade; views ficam no setup protegido
├── src/
│   ├── extract_sih_sus.py             # Extração automatizada de AIH do DATASUS via PySUS
│   ├── transform_star_schema.py       # Pipeline ETL de saneamento e modelagem dimensional
│   ├── generate_benchmark_dataset.py  # Gerador de benchmark hospitalar clínico-financeiro
│   ├── load_benchmark_to_mysql.py     # Carga de agregados sintéticos para a Vercel
│   ├── load_public_sus_to_mysql.py    # Agregação e carga pública SIH/SUS, CNES e SISREG
│   ├── public_sus_quality.py           # Bloqueios de qualidade antes da publicação
│   ├── validate_hospital_pilot.py      # Pré-validação dos CSVs agregados do piloto
│   ├── load_to_mysql.py               # Carga direta idempotente em MySQL
│   └── mysql_client.py                # Diagnóstico e consultas das views agregadas
├── streamlit_app.py                   # Painel local para o benchmark sintético
├── powerbi/
│   ├── dashboard_preview.html         # Painel HTML com dados agregados das rotas protegidas
│   ├── dashboard.css                  # Layout responsivo do painel
│   ├── dashboard.js                   # Filtros SIH/SUS e indicadores públicos via API
│   ├── dax_measures.dax               # Catálogo completo de métricas DAX prontas para Power BI
│   └── dashboard_wireframe.md         # Wireframe detalhado das telas, layout e cores
├── docs/
│   ├── business_problem.md            # Problema de negócio, dores e Tríplice Meta da Saúde
│   ├── benchmark_dashboard.md         # Regras sintéticas e conclusões do dashboard Streamlit
│   ├── public_sus_dashboard.md        # Fontes, regras, agregações e limites dos dados públicos
│   ├── pilot_data_contract.md         # Campos e governança exigidos no piloto hospitalar
│   ├── data_dictionary.md             # Dicionário de dados do DATASUS e Star Schema
│   └── security.md                    # Controles e requisitos de implantação segura
├── .github/workflows/ci.yml           # Qualidade contínua para Node e Python
├── .github/dependabot.yml             # Atualizações semanais de dependências e Actions
├── pyproject.toml                     # Dependências e faixa Python do projeto
├── uv.lock                            # Versões Python reproduzíveis para a CI
├── requirements.txt                   # Dependências do pipeline (pysus, duckdb, pandas, pyarrow)
├── requirements-dashboard.txt         # Dependências do dashboard (Streamlit e Plotly)
└── README.md                          # Apresentação executiva e técnica do projeto
```

---

## 🚀 7. Como Executar o Projeto

### API REST na Vercel

O diretório `api/` contém funções serverless. Configure na Vercel `MYSQL_URL` com a URL do banco MySQL, `MYSQL_TLS=true`, a CA TLS em `MYSQL_SSL_CA` quando exigida e `AUTH_RATE_LIMIT_SECRET` (32 bytes aleatórios). Use a conta `dashboard_app` com permissões somente nas views e tabelas de autenticação; não use `root`. O login aceita e-mail e senha de contas previamente autorizadas. As sessões ficam em cookies `HttpOnly`, `Secure` em produção e `SameSite=Strict`; o cadastro público fica desativado. `/api/health` permanece público.

| Rota | Uso | Filtros opcionais |
| --- | --- | --- |
| `GET /api/health` | Verifica se a função está ativa | — |
| `GET /api/executive` | KPIs mensais por especialidade | `ano_mes`, `especialidade`, `limit` |
| `GET /api/beds` | Admissões e capacidade informada por setor; ocupação retorna `null` sem censo diário | `ano_mes`, `id_leito`, `limit` |
| `GET /api/risk` | Indicadores clínicos agregados por coorte; grupos com menos de 10 internações são ocultados | `ano_mes`, `cid_10`, `especialidade`, `grau_severidade`, `limit` |
| `GET /api/benchmark` | Agregados SIH/SUS, CNES e fila SISREG pública de Alagoas | Requer sessão autorizada; `period=all` ou `2025-MM` |
| `GET /api/filters?dimension=...` | Dimensões para filtros do dashboard | `dimension`: `procedures`, `diagnoses`, `beds` ou `months`; `limit` |

Exemplos:

```bash
curl 'https://SEU-PROJETO.vercel.app/api/health'
curl -c cookies.txt -X POST 'https://SEU-PROJETO.vercel.app/api/auth/login' \
  -H 'Origin: https://SEU-PROJETO.vercel.app' -H 'Content-Type: application/json' \
  --data '{"email":"usuario@hospital.org","password":"SENHA"}'
curl -b cookies.txt 'https://SEU-PROJETO.vercel.app/api/executive?ano_mes=2023-01&limit=50'
curl -b cookies.txt 'https://SEU-PROJETO.vercel.app/api/beds?ano_mes=2023-01'
curl -b cookies.txt 'https://SEU-PROJETO.vercel.app/api/risk?grau_severidade=Não%20classificado&limit=25'
curl -b cookies.txt 'https://SEU-PROJETO.vercel.app/api/benchmark?period=all'
curl -b cookies.txt 'https://SEU-PROJETO.vercel.app/api/filters?dimension=procedures'
```

As rotas retornam `{ "data": [...], "count": 1, "limit": 100 }`, com limite de 1.000 linhas e `Cache-Control: no-store`. Execute `sql/mysql_setup.sql` como administrador do banco e depois aplique `sql/mysql_grants.sql`, substituindo nomes e senhas de exemplo. As views ocultam grupos com menos de 10 registros. Crie ou atualize uma conta autorizada com `INITIAL_ADMIN_EMAIL=<email> npm run mysql:bootstrap-user`; o script solicita a senha sem mostrá-la. A Vercel recebe somente a URL da conta web limitada, nunca a credencial administrativa. Configure TLS validado e faça backup do volume MySQL.

Para publicar os dados públicos no dashboard Vercel, aplique a migração aditiva e valide os agregados antes da carga. O CNES e o relatório SISREG são baixados para `data/public_sus/`, ignorado pelo Git; também é possível indicar arquivos locais:

```bash
npm run mysql:public-sus:setup
npm run mysql:panorama-2025:setup
uv run python src/load_public_sus_to_mysql.py --dry-run
uv run python src/load_public_sus_to_mysql.py
```

A migração cria views e tabelas próprias e atualiza permissões; não recria contas nem altera os fatos SIH/SUS. O Panorama e os diagnósticos aceitam somente o ano de admissão de 2025; o benchmark público filtra internações e valores AIH por competência. A fila SISREG é um retrato histórico de solicitações ainda pendentes e não mede a espera interna até um leito. O Streamlit permanece como demonstração sintética separada.

### Pré-requisitos
* Python 3.11–3.14 instalado (a faixa compatível com a versão atual do PySUS)
* [uv](https://docs.astral.sh/uv/) para instalar as versões travadas em `uv.lock` (ou pip para instalação compatível)

### Passo a Passo

1. **Clonar ou acessar o repositório:**
```bash
cd gestao-hospitalar-analytics
```

2. **Instalar dependências:**
```bash
uv sync --locked
```
O `uv.lock` fixa as versões Python usadas pela CI. Para a instalação tradicional com pip, use `pip install -r requirements.txt`.

3. **Opção A: Extrair dados reais do DATASUS (SIH/SUS):**
```bash
# Gere uma chave secreta com `python3 -c 'import secrets; print(secrets.token_hex(32))'`
# e salve em PATIENT_DATA_HMAC_KEY no .env antes de transformar os dados.
# Baixa as internações do Acre (AC) de janeiro de 2023
uv run python src/extract_sih_sus.py --state AC --year 2023 --month 1

# Processa e gera o Star Schema
uv run python src/transform_star_schema.py
```
O ETL não grava o número de AIH nem idade exata/município nos arquivos processados. Como o SIH/SUS não fornece uma chave persistente de pessoa neste fluxo, `readmissao_30d` fica desconhecida (`NULL`) para os dados reais; o benchmark usa readmissões simuladas.

4. **Opção B: Gerar dataset de benchmark clínico-financeiro (15.000 internações completas):**
```bash
uv run python src/generate_benchmark_dataset.py
```
Os artefatos sintéticos são salvos em `data/benchmark/`, separados dos dados SIH/SUS em `data/processed/`.

5. **Abrir o dashboard interativo do benchmark:**
```bash
uv sync --locked --extra dashboard
uv run streamlit run streamlit_app.py
```
O painel usa Pandas e consultas SQL no DuckDB para explorar espera por setor, ocupação mensal, custos por procedimento e concentração de chegadas. O simulador permite alterar admissões mensais, permanência média e leitos com equipe disponível; todo o cenário é sintético. As regras da simulação estão em [`docs/benchmark_dashboard.md`](docs/benchmark_dashboard.md).

6. **Executar consultas analíticas no DuckDB:**
```bash
uv run python -c "import duckdb
con = duckdb.connect('data/benchmark/hospital_analytics.duckdb', read_only=True)
print(con.execute('SELECT especialidade, COUNT(*), ROUND(AVG(dias_permanencia), 1) as tmp, ROUND(SUM(margem_contribuicao), 2) as margem FROM fato_internacoes f JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento GROUP BY especialidade ORDER BY margem DESC').df())
"
```

7. **Carregar o Star Schema no MySQL:**
* Disponibilize um banco MySQL 8+ acessível pelas funções Vercel, com armazenamento persistente e TLS. A Vercel hospeda a aplicação e conecta bancos externos; as opções do Marketplace são descritas na [documentação de storage](https://vercel.com/docs/storage).
* Execute [sql/mysql_setup.sql](sql/mysql_setup.sql) no banco criado e aplique [sql/mysql_grants.sql](sql/mysql_grants.sql) com usuários separados para aplicação, ETL e Power BI.
* Copie `.env.example` para `.env`, configure a URL pública do MySQL e os segredos locais. A URL de produção deve usar TLS com certificado validado.
* Gere ou extraia os arquivos em `data/processed/`, valide e carregue:
```bash
uv run python src/load_to_mysql.py --dry-run
uv run python src/load_to_mysql.py
```
Para substituir dados anteriores, faça backup e use explicitamente `--truncate --confirm-truncate` com a role ETL apropriada. Consulte [`docs/mysql_integration.md`](docs/mysql_integration.md) para provisionamento e permissões.

8. **Importar no Power BI:**
* Abra o Power BI Desktop.
* Para uma demonstração sintética, importe os arquivos de `data/benchmark/`; para o fluxo SIH/SUS, use os artefatos validados em `data/processed/`. As duas pastas são ignoradas pelo Git.
* Para conectar ao banco, use `powerbi_reader` com `SELECT` somente nas views agregadas; nunca use `root`. Veja [docs/mysql_integration.md](docs/mysql_integration.md).
* Cole as medidas DAX do arquivo [`powerbi/dax_measures.dax`](powerbi/dax_measures.dax).

### Qualidade dos dados e piloto hospitalar

O workflow [CI](.github/workflows/ci.yml) executa as suítes Node e Python em pushes e pull requests. O [Dependabot](.github/dependabot.yml) procura atualizações semanais de npm, pacotes Python e GitHub Actions. Antes de publicar os agregados SIH/SUS, rode `uv run python src/load_public_sus_to_mysql.py --dry-run`; o processo interrompe a carga se encontrar cobertura mensal incompleta, chaves duplicadas ou inconsistência entre os agregados. A data das fontes e do ETL fica visível no dashboard.

Para preparar dados reais de um hospital, use o banco separado definido em [sql/09_hospital_pilot_mysql.sql](sql/09_hospital_pilot_mysql.sql) e valide os CSVs com `python3 src/validate_hospital_pilot.py`. O contrato e a lista de campos estão em [docs/pilot_data_contract.md](docs/pilot_data_contract.md). A API atual não acessa esse banco.

---

## 📄 Licença

O código e a documentação próprios deste repositório estão sob [MIT](LICENSE). Dados e materiais de terceiros permanecem sob seus próprios termos.

---

## 👨‍💻 Autor
Desenvolvido por **Nycolas Gabriel**  
*Estudante de Análise e Desenvolvimento de Sistemas / Engenharia e Análise de Dados*  
Foco em SQL Avançado, Modelagem Dimensional, Analytics Engineering e Saúde Baseada em Valor (*Value-Based Healthcare*).
