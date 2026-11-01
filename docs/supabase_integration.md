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
2. Python 3.11–3.14 instalado no seu ambiente (compatível com PySUS 2.11.x).
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
2. Abra o arquivo local [sql/supabase_setup.sql](../sql/supabase_setup.sql).
3. Copie todo o conteúdo do arquivo e cole no editor do Supabase.
4. Clique em **"RUN"** (ou `Ctrl + Enter` / `Cmd + Enter`).
5. O script roda em uma transação, preserva as tabelas, remove idade exata e município da dimensão, substitui a view clínica por agregações com mínimo de 10 registros, deixa ocupação indisponível sem censo diário, restringe grants e bloqueia grants padrão em novas tabelas/sequências criadas por `postgres` em `public`. Novos objetos precisam de grants explícitos e revisão de RLS. Faça backup e revise dados antigos antes da atualização.
6. Desative o cadastro público em **Authentication → Providers → Email** e limite as URLs de redirecionamento aos domínios usados. O painel aceita e-mail/senha e oferece links mágicos de uso único para contas existentes. O login deste protótipo não implementa desafio MFA nem impõe AAL2; não anuncie MFA como obrigatório até adicionar esse fluxo e a regra de autorização correspondente.
7. Crie/invite as contas por um fluxo administrativo confiável e defina `app_metadata.hospital_analytics_access` como booleano `true`. O próprio usuário não pode alterar `app_metadata`; não use `user_metadata` para autorização.

---

### Passo 3: Configurar as Variáveis de Ambiente (`.env`)
1. No terminal do projeto, crie o arquivo `.env` a partir do template:
   ```bash
   cp .env.example .env
   ```
2. No painel do Supabase, acesse **Project Settings** (ícone de engrenagem) e colete as credenciais:
   - **API URL e Chaves:** Em **Project Settings -> API**:
     - `Project URL` -> defina em `SUPABASE_URL`
     - `Publishable key` -> defina em `SUPABASE_PUBLISHABLE_KEY` para as rotas web
     - `Secret/service_role key` -> defina em `SUPABASE_SERVICE_ROLE_KEY` somente para o ETL local
   - **Conexão Direta PostgreSQL:** use uma role `analytics_loader` limitada às seis tabelas do projeto, não a conta mestre `postgres`.

Crie a role depois de executar o setup SQL, com senha exclusiva guardada em cofre:
```sql
CREATE ROLE analytics_loader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '<senha-forte-única>';
GRANT USAGE ON SCHEMA public TO analytics_loader;
GRANT SELECT, INSERT, UPDATE ON dim_tempo, dim_paciente, dim_procedimento,
  dim_diagnostico, dim_setor_leito, fato_internacoes TO analytics_loader;
CREATE POLICY analytics_loader_access ON dim_tempo FOR ALL TO analytics_loader USING (true) WITH CHECK (true);
CREATE POLICY analytics_loader_access ON dim_paciente FOR ALL TO analytics_loader USING (true) WITH CHECK (true);
CREATE POLICY analytics_loader_access ON dim_procedimento FOR ALL TO analytics_loader USING (true) WITH CHECK (true);
CREATE POLICY analytics_loader_access ON dim_diagnostico FOR ALL TO analytics_loader USING (true) WITH CHECK (true);
CREATE POLICY analytics_loader_access ON dim_setor_leito FOR ALL TO analytics_loader USING (true) WITH CHECK (true);
CREATE POLICY analytics_loader_access ON fato_internacoes FOR ALL TO analytics_loader USING (true) WITH CHECK (true);
```
As políticas dão acesso às linhas para esta role de carga; mantenha a credencial só no ambiente local controlado. Se precisar usar `--truncate`, conceda `TRUNCATE` explicitamente nas seis tabelas somente durante a janela de recarga.

Exemplo de `.env`:
```env
SUPABASE_URL=https://xyzcompanyproject.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_sua-chave
SUPABASE_SERVICE_ROLE_KEY=<segredo-apenas-para-carga-local-via-api>
DATABASE_URL=postgresql://analytics_loader:<senha-forte>@db.xyzcompanyproject.supabase.co:5432/postgres
PATIENT_DATA_HMAC_KEY=segredo-local-aleatorio-de-64-caracteres
```

Gere `PATIENT_DATA_HMAC_KEY` com um gerador criptográfico, guarde-o fora do Git e mantenha o mesmo valor para recargas. Não use uma chave Supabase como chave HMAC. O ETL não persiste o número AIH original, idade exata ou município. O SIH/SUS não fornece uma chave persistente de pessoa nesse pipeline, então `readmissao_30d` fica desconhecida (`NULL`) para os dados reais.

---

### Passo 4: Executar a Carga de Dados Automatizada

O script [`src/load_to_supabase.py`](../src/load_to_supabase.py) carrega as dimensões e a tabela fato respeitando a integridade referencial:

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

Uma substituição completa apaga os dados antes da carga e não é uma única transação via API. Faça backup, conceda temporariamente `TRUNCATE` à role de carga e confirme explicitamente: `python src/load_to_supabase.py --method direct --truncate --confirm-truncate`.

---

### Passo 5: Testar a Conexão e Integridade dos Dados

Execute o script de diagnóstico para verificar se as views permitidas estão ativas. Ele precisa de `SUPABASE_SERVICE_ROLE_KEY` somente no ambiente local e consulta apenas views agregadas:
```bash
python src/supabase_client.py
```

O relatório mostra o estado e a contagem retornada pelas views permitidas; ele não lista linhas individuais de pacientes.

---

## 📊 Como Conectar o Power BI ao Supabase

Para dados reais, use um papel PostgreSQL dedicado `powerbi_reader`, nunca o usuário mestre `postgres`. Depois de executar o setup, um administrador deve criar uma role com senha única em um cofre e conceder acesso apenas às views agregadas:

```sql
CREATE ROLE powerbi_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '<senha-forte-única>';
GRANT USAGE ON SCHEMA public TO powerbi_reader;
GRANT SELECT ON vw_painel_executivo_mensal,
                vw_eficiencia_leitos_setor,
                vw_detalhe_clinico_risco,
                vw_dim_procedimento,
                vw_dim_diagnostico,
                vw_dim_setor_leito,
                vw_dim_tempo TO powerbi_reader;
```

As views aceitam essa role e ocultam coortes com menos de 10 internações. Não conceda acesso às tabelas base.

1. No **Power BI Desktop**, clique em **Obter Dados -> Banco de Dados PostgreSQL**.
2. No campo **Servidor**, informe o host do Supabase:
   - Exemplo: `db.xyzcompanyproject.supabase.co` ou o pooler `aws-0-sa-east-1.pooler.supabase.com:6543`
3. No campo **Banco de Dados**, informe `postgres`.
4. Em **Modo de Conectividade**, escolha:
   - **Importar:** Mais rápido para relatórios interativos.
   - **DirectQuery:** Para relatórios em tempo real sem importar dados localmente.
5. Em **Autenticação**, selecione a aba **Banco de Dados**:
   - **Nome de usuário:** `powerbi_reader` (ou `powerbi_reader.xyzcompanyproject` no pooler, se exigido).
   - **Senha:** a senha exclusiva dessa role, guardada no cofre.
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
    filters={"especialidade": "Ortopedia"}
)
print(df_kpi.head())
```

### Exemplo 2: Consulta via API da aplicação
```bash
curl -X POST 'https://<APP>/api/auth/magic-link' \
  -H 'Origin: https://<APP>' -H 'Content-Type: application/json' \
  --data '{"email":"<conta-aprovada>"}'
curl -b cookies.txt 'https://<APP>/api/executive?ano_mes=2023-01'
```

