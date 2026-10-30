# 🚀 Integração com o Supabase (Cloud PostgreSQL & PostgREST API)

Este documento detalha como conectar o projeto **Healthcare Analytics** ao **Supabase**, transformando o modelo dimensional local em um Data Warehouse em nuvem com alta disponibilidade, conexão direta para Power BI / Metabase e API REST/GraphQL instantânea.

---

## 🏗️ Arquitetura da Solução em Nuvem

```
[ Datasets Processados (CSV/Parquet) ]
                │
                ▼
       [ src/load_to_supabase.py ]
         │                     │
         │ (Método Direct)     │ (Método REST API)
         ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE (PostgreSQL 15+)                │
│                                                             │
│   [ Star Schema: Dimensões & Fato (26.000+ registros) ]    │
│   [ Índices Analíticos de Alta Performance ]                │
│   [ 3 Views Analíticas de Negócio (vw_painel_executivo...) ]│
│   [ Políticas de Segurança Row Level Security (RLS) ]       │
└──────────────────────────────┬──────────────────────────────┘
                               │
       ┌───────────────────────┴───────────────────────┐
       ▼                                               ▼
[ Dashboards de BI ]                        [ Aplicações & APIs ]
 • Power BI (PostgreSQL Connector)           • Python (pandas / requests)
 • Metabase / Looker Studio                  • Web Apps (Next.js, React)
 • Tableau / Excel                           • PostgREST / GraphQL API
```

---

## 📋 Pré-requisitos

1. Uma conta gratuita no [Supabase](https://supabase.com).
2. Python 3.10+ instalado no seu ambiente.
3. Dependências do projeto instaladas (`pip install -r requirements.txt`).

---

## 🛠️ Passo a Passo de Configuração

### Passo 1: Criar o Projeto no Supabase
1. Acesse o painel do [Supabase Dashboard](https://supabase.com/dashboard).
2. Clique em **"New Project"**.
3. Defina um nome para o projeto (ex: `gestao-hospitalar-analytics`).
4. Escolha uma senha forte para o banco de dados PostgreSQL (**guarde esta senha**).
5. Selecione a região mais próxima (ex: `São Paulo (sa-east-1)`).
6. Aguarde 1 a 2 minutos até que o provisionamento seja concluído.

---

### Passo 2: Executar o Script DDL no Supabase SQL Editor
1. No menu lateral esquerdo do Supabase, clique no ícone **SQL Editor** (`>_`).
2. Abra o arquivo local [`sql/supabase_setup.sql`](file:///Users/nycolas/Documents/gestao-hospitalar-analytics/sql/supabase_setup.sql).
3. Copie todo o conteúdo do arquivo e cole no editor do Supabase.
4. Clique em **"RUN"** (ou `Ctrl + Enter` / `Cmd + Enter`).
5. Você verá a confirmação `Success. No rows returned`. O Star Schema, índices analíticos, views e regras de RLS estarão criados.

---

### Passo 3: Configurar as Variáveis de Ambiente (`.env`)
1. No terminal do projeto, crie o arquivo `.env` a partir do template:
   ```bash
   cp .env.example .env
   ```
2. No painel do Supabase, acesse **Project Settings** (ícone de engrenagem) e colete as credenciais:
   - **API URL e Chaves:** Em **Project Settings -> API**:
     - `Project URL` -> defina em `SUPABASE_URL`
     - `Project API Keys (anon public)` -> defina em `SUPABASE_KEY`
     - `Project API Keys (service_role secret)` -> defina em `SUPABASE_SERVICE_ROLE_KEY`
   - **Conexão Direta PostgreSQL:** Em **Project Settings -> Database -> Connection String -> URI**:
     - Substitua `[YOUR-PASSWORD]` pela senha definida no Passo 1 e cole em `DATABASE_URL`.

Exemplo de `.env`:
```env
SUPABASE_URL=https://xyzcompanyproject.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
DATABASE_URL=postgresql://postgres:SuaSenhaAqui@db.xyzcompanyproject.supabase.co:5432/postgres
```

---

### Passo 4: Executar a Carga de Dados Automatizada

O script [`src/load_to_supabase.py`](file:///Users/nycolas/Documents/gestao-hospitalar-analytics/src/load_to_supabase.py) carrega as 5 dimensões e a tabela fato respeitando a integridade referencial:

#### Opção A: Carga via API PostgREST (Padrão e Recomendada - Sem necessidade de driver Postgres)
```bash
python src/load_to_supabase.py --method api
```
*Vantagens:* Funciona instantaneamente via HTTP/HTTPS sem restrições de firewall ou IPv6.

#### Opção B: Carga via Conexão Direta PostgreSQL (SQLAlchemy)
```bash
pip install psycopg2-binary
python src/load_to_supabase.py --method direct
```

#### Modo Validação (Dry-run):
Para testar a integridade dos dados locais sem conectar à internet:
```bash
python src/load_to_supabase.py --dry-run
```

---

### Passo 5: Testar a Conexão e Integridade dos Dados

Execute o script de diagnóstico para verificar se todas as tabelas e views estão ativas no Supabase:
```bash
python src/supabase_client.py
```

Você verá a contagem de registros em cada tabela:
- `dim_tempo`: 365 linhas
- `dim_paciente`: 10.800 linhas
- `dim_procedimento`: 15 linhas
- `dim_diagnostico`: 13 linhas
- `dim_setor_leito`: 3 linhas
- `fato_internacoes`: 15.000 linhas
- Views analíticas ativas e prontas para consulta!

---

## 📊 Como Conectar o Power BI ao Supabase

O Supabase é um banco de dados **PostgreSQL** nativo, permitindo conexão direta com o Power BI Desktop:

1. No **Power BI Desktop**, clique em **Obter Dados -> Banco de Dados PostgreSQL**.
2. No campo **Servidor**, informe o host do Supabase:
   - Exemplo: `db.xyzcompanyproject.supabase.co` ou o pooler `aws-0-sa-east-1.pooler.supabase.com:6543`
3. No campo **Banco de Dados**, informe `postgres`.
4. Em **Modo de Conectividade**, escolha:
   - **Importar:** Mais rápido para relatórios interativos.
   - **DirectQuery:** Para relatórios em tempo real sem importar dados localmente.
5. Em **Autenticação**, selecione a aba **Banco de Dados**:
   - **Nome de usuário:** `postgres` (ou `postgres.xyzcompanyproject` se estiver usando o Pooler).
   - **Senha:** A senha mestra do banco criada no Passo 1.
6. Na lista de objetos, selecione diretamente as views analíticas:
   - `vw_painel_executivo_mensal`
   - `vw_eficiencia_leitos_setor`
   - `vw_detalhe_clinico_risco`

---

## 💻 Consumo via Código (Python / API)

### Exemplo 1: Consultando Views com Python (via PostgREST)
```python
from src.supabase_client import query_table

# Obter KPIs mensais de Ortopedia
df_kpi = query_table(
    table_or_view="vw_painel_executivo_mensal",
    select="ano_mes,especialidade,volume_internacoes,margem_contribuicao,margem_pct",
    filters={"especialidade": "eq.Ortopedia"}
)
print(df_kpi.head())
```

### Exemplo 2: Consulta via cURL / HTTP
```bash
curl 'https://<PROJECT-REF>.supabase.co/rest/v1/vw_painel_executivo_mensal?select=*' \
  -H "apikey: <SUA_SUPABASE_KEY>" \
  -H "Authorization: Bearer <SUA_SUPABASE_KEY>"
```

