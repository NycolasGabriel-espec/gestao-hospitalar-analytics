# 📖 Dicionário de Dados: SIH/SUS & Modelo Dimensional

Este documento descreve as fontes de dados de Autorização de Internação Hospitalar do DATASUS (SIH/SUS - Arquivos RD - AIH Reduzida) e o mapeamento para o Modelo Star Schema Analítico. Layouts e significados podem variar por competência; valide o dicionário correspondente ao arquivo usado.

---

## 1. Campos Nativos do SIH/SUS (DATASUS)

| Campo Original | Tipo | Descrição no DATASUS | Mapeamento no Star Schema |
| :--- | :--- | :--- | :--- |
| `N_AIH` | VARCHAR | Número da Autorização de Internação Hospitalar (identificador da internação) | HMAC em `fato_internacoes.id_atendimento`; o valor original não é exportado |
| `IDENT` | VARCHAR | Tipo de identificação da AIH (1 = Principal/Inicial, 5 = Continuidade) | Não usado para inferir identidade ou readmissão |
| `DT_INTER` | VARCHAR | Data de internação do paciente (Formato YYYYMMDD) | `fato_internacoes.data_admissao` / `dim_tempo` |
| `DT_SAIDA` | VARCHAR | Data de alta, transferência ou óbito (Formato YYYYMMDD) | `fato_internacoes.data_alta` |
| `DIAS_PERM` | INTEGER | Total de dias de permanência do paciente na internação | `fato_internacoes.dias_permanencia` |
| `QT_DIARIAS` | INTEGER | Quantidade de diárias hospitalares faturadas | `fato_internacoes.qtd_diarias` |
| `UTI_MES_TO` | INTEGER | Total de dias de permanência do paciente em leito de UTI no mês | `fato_internacoes.dias_uti` |
| `DIAG_PRINC` | VARCHAR | Código CID-10 do diagnóstico primário que motivou a internação | `dim_diagnostico.cid_10` |
| `DIAG_SECUN` | VARCHAR | Código CID-10 secundário | Não persistido neste modelo |
| `PROC_REA` | VARCHAR | Código do procedimento médico-cirúrgico realizado (Tabela SIGTAP) | `dim_procedimento.id_procedimento` |
| `VAL_TOT` | DECIMAL | Valor total registrado para a AIH | `fato_internacoes.receita_faturada` como valor AIH; não comprova recebimento |
| `VAL_SH` | DECIMAL | Componente do valor registrado para a AIH | Não tratado como custo interno do hospital |
| `VAL_SP` | DECIMAL | Componente do valor registrado para a AIH | Não tratado como custo interno do hospital |
| `VAL_ORTP` | DECIMAL | Componente do valor registrado para a AIH, conforme a competência | Não tratado como custo interno do hospital |
| `VAL_SADT` | DECIMAL | Componente do valor registrado para a AIH, conforme a competência | Não tratado como custo interno do hospital |
| `VAL_UTI` | DECIMAL | Valor referente a UTI na AIH | Não usado como custo ou quantidade de dias |
| `SEXO` | VARCHAR | Sexo biológico do paciente (1/M = Masculino, 3/F = Feminino) | `dim_paciente.sexo` |
| `COD_IDADE` | VARCHAR | Unidade da idade (0 = ignorada, 2 = dias, 3 = meses, 4 = anos; validar código 5 no layout da competência) | Usado com `IDADE` para gerar a faixa; não é persistido |
| `IDADE` | INTEGER | Idade na unidade informada por `COD_IDADE` | Usada apenas para gerar `dim_paciente.faixa_etaria`; idade exata não é persistida |
| `MUNIC_RES` | VARCHAR | Código IBGE do município de residência do paciente | Descartado pelo ETL |
| `CNES` | VARCHAR | Cadastro Nacional de Estabelecimentos de Saúde (Unidade Hospitalar) | Não persistido neste modelo |
| `MORTE` | INTEGER | Indicador de óbito hospitalar (1 = Sim, 0 = Não) | `fato_internacoes.indicador_obito`; outros valores são desconhecidos |
| `COBRANCA` | VARCHAR | Motivo de saída/permanência segundo o código da competência | Não persistido neste modelo |

---

## 2. Entidades do Modelo Dimensional (Star Schema)

### Tabela Fato: `fato_internacoes`
Registra cada evento de internação com grão atômico (1 linha por internação/AIH):
* `id_atendimento` (PK): HMAC do número da AIH usando `PATIENT_DATA_HMAC_KEY`.
* `id_paciente` (FK): Chave pseudonimizada de nível de internação; o fluxo SIH/SUS não contém identificador persistente de pessoa.
* `id_procedimento` (FK): Chave de relacionamento com `dim_procedimento`.
* `cid_10` (FK): Chave de relacionamento com `dim_diagnostico`.
* `id_leito` (FK): Chave de relacionamento com `dim_setor_leito`.
* `id_data_admissao` (FK): Chave de relacionamento com `dim_tempo` (Data de entrada).
* `id_data_alta` (FK): Chave de relacionamento com `dim_tempo` (Data de saída).
* **Métricas Aditivas e Semi-aditivas:**
  * `dias_permanencia`: Dias informados na fonte; ausências permanecem `NULL`.
  * `dias_uti`: Dias informados na coluna SIH disponível; ausências permanecem `NULL`.
  * `qtd_diarias`: Quantidade informada em `QT_DIARIAS`; não é substituída por dias de permanência.
  * `custo_hospitalar`, `custo_servicos_profissionais`, `custo_opme`, `custo_sadt`, `custo_total` e `margem_contribuicao`: `NULL` para SIH/SUS. Valores da AIH não representam custos contábeis do hospital.
  * `receita_faturada`: Para SIH/SUS, contém `VAL_TOT` quando disponível (valor registrado da AIH), sem comprovar faturamento contábil ou recebimento.
  * `readmissao_30d`: `NULL` para SIH/SUS neste pipeline, que não identifica uma mesma pessoa em internações diferentes. No benchmark, o valor é simulado.
  * `indicador_obito`: 1/0 quando `MORTE` é válido; valores ausentes ou inesperados ficam `NULL`.
  * `status_desfecho`: classifica óbito conhecido; demais saídas são agrupadas sem inferir alta curada, transferência ou outro motivo.
  * `id_leito`: `LEITO_NAO_INFORMADO` no fluxo SIH/SUS; a fonte deste pipeline não identifica a unidade assistencial.

### Dimensão: `dim_paciente`
* `id_paciente` (PK): HMAC pseudonimizado com chave local; pseudonimização não equivale a anonimização.
* `sexo`: M / F / U (desconhecido ou não mapeado).
* `faixa_etaria`: Categorias padronizadas e `Faixa Desconhecida` quando não informada.
* Idade exata e município são descartados antes de gravar os arquivos processados.

### Dimensão: `dim_procedimento`
* `id_procedimento` (PK): Código de 10 dígitos da Tabela Unificada SIGTAP do SUS.
* `descricao_procedimento`: O fluxo SIH/SUS exporta o código com aviso de que a descrição oficial deve ser validada no catálogo SIGTAP.
* `especialidade` e `complexidade`: Categorias heurísticas baseadas no prefixo do código; exigem revisão com catálogo oficial e especialista.
* `tmp_protocolo_previsto`: `NULL` para dados SIH/SUS; só deve ser preenchido com protocolo clínico validado.

### Dimensão: `dim_diagnostico`
* `cid_10` (PK): Código alfanumérico da Classificação Internacional de Doenças (10ª Revisão).
* `descricao_cid`: Código CID-10, sem inventar um nome clínico detalhado.
* `capitulo_cid`: Classificação ampla heurística pelo primeiro caractere do código.
* `grau_severidade`: `Não classificado` para dados SIH/SUS; não é inferido pela letra do CID.

### Dimensão: `dim_setor_leito`
* `id_leito` (PK): Identificador do agrupamento de acomodação.
* `tipo_acomodacao` e `setor_hospitalar`: `Não informado na fonte` para dados SIH/SUS.
* `leitos_operacionais`: `NULL` para dados SIH/SUS; a fonte não informa capacidade instalada por setor.

### Dimensão: `dim_tempo`
* `id_data` (PK): Inteiro no formato YYYYMMDD.
* `data_completa`: Formato DATE (YYYY-MM-DD).
* `ano`, `mes`, `dia`, `trimestre`, `semestre`.
* `nome_mes`, `dia_da_semana`, `eh_fim_de_semana`.
