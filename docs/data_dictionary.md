# 📖 Dicionário de Dados: SIH/SUS & Modelo Dimensional

Este documento descreve as fontes de dados de Autorização de Internação Hospitalar do DATASUS (SIH/SUS - Arquivos RD - AIH Reduzida) e o mapeamento para o Modelo Star Schema Analítico.

---

## 1. Campos Nativos do SIH/SUS (DATASUS)

| Campo Original | Tipo | Descrição no DATASUS | Mapeamento no Star Schema |
| :--- | :--- | :--- | :--- |
| `N_AIH` | VARCHAR | Número da Autorização de Internação Hospitalar (Identificador único) | `fato_internacoes.id_atendimento` |
| `IDENT` | VARCHAR | Tipo de identificação da AIH (1 = Principal/Inicial, 5 = Continuidade) | Usado para rastreio de continuidade/readmissão |
| `DT_INTER` | VARCHAR | Data de internação do paciente (Formato YYYYMMDD) | `fato_internacoes.data_admissao` / `dim_tempo` |
| `DT_SAIDA` | VARCHAR | Data de alta, transferência ou óbito (Formato YYYYMMDD) | `fato_internacoes.data_alta` |
| `DIAS_PERM` | INTEGER | Total de dias de permanência do paciente na internação | `fato_internacoes.dias_permanencia` |
| `QT_DIARIAS` | INTEGER | Quantidade de diárias hospitalares faturadas | `fato_internacoes.qtd_diarias` |
| `UTI_MES_TO` | INTEGER | Total de dias de permanência do paciente em leito de UTI no mês | `fato_internacoes.dias_uti` |
| `DIAG_PRINC` | VARCHAR | Código CID-10 do diagnóstico primário que motivou a internação | `dim_diagnostico.cid_10` |
| `DIAG_SECUN` | VARCHAR | Código CID-10 de comorbidade ou complicação secundária | `fato_internacoes.cid_10_secundario` |
| `PROC_REA` | VARCHAR | Código do procedimento médico-cirúrgico realizado (Tabela SIGTAP) | `dim_procedimento.id_procedimento` |
| `VAL_TOT` | DECIMAL | Valor total faturado/repassado pelo SUS para a internação | `fato_internacoes.receita_faturada` |
| `VAL_SH` | DECIMAL | Valor de Serviços Hospitalares (diárias, hotelaria, enfermagem, taxas) | `fato_internacoes.custo_hospitalar` |
| `VAL_SP` | DECIMAL | Valor de Serviços Profissionais (honorários médicos e cirúrgicos) | `fato_internacoes.custo_servicos_profissionais` |
| `VAL_ORTP` | DECIMAL | Valor de Órteses, Próteses e Materiais Especiais (OPME) | `fato_internacoes.custo_opme` |
| `VAL_SADT` | DECIMAL | Valor de Serviços de Apoio Diagnóstico e Terapêutico (exames) | `fato_internacoes.custo_sadt` |
| `VAL_UTI` | DECIMAL | Valor pago especificamente pelas diárias de leito intensivo (UTI) | `fato_internacoes.custo_uti` |
| `SEXO` | VARCHAR | Sexo biológico do paciente (1/M = Masculino, 3/F = Feminino) | `dim_paciente.sexo` |
| `IDADE` | INTEGER | Idade do paciente em anos completos | `dim_paciente.idade` / `faixa_etaria` |
| `MUNIC_RES` | VARCHAR | Código IBGE do município de residência do paciente | `dim_paciente.cod_municipio_residencia` |
| `CNES` | VARCHAR | Cadastro Nacional de Estabelecimentos de Saúde (Unidade Hospitalar) | `dim_setor_leito.cnes_hospital` |
| `MORTE` | INTEGER | Indicador de óbito hospitalar (1 = Sim, 0 = Não) | `fato_internacoes.indicador_obito` |
| `COBRANCA` | VARCHAR | Motivo de encerramento da internação (Alta, Óbito, Transferência) | `fato_internacoes.status_desfecho` |

---

## 2. Entidades do Modelo Dimensional (Star Schema)

### Tabela Fato: `fato_internacoes`
Registra cada evento de internação com grão atômico (1 linha por internação/AIH):
* `id_atendimento` (PK): Identificador exclusivo da AIH.
* `id_paciente` (FK): Chave de relacionamento com `dim_paciente`.
* `id_procedimento` (FK): Chave de relacionamento com `dim_procedimento`.
* `cid_10` (FK): Chave de relacionamento com `dim_diagnostico`.
* `id_leito` (FK): Chave de relacionamento com `dim_setor_leito`.
* `id_data_admissao` (FK): Chave de relacionamento com `dim_tempo` (Data de entrada).
* `id_data_alta` (FK): Chave de relacionamento com `dim_tempo` (Data de saída).
* **Métricas Aditivas e Semi-aditivas:**
  * `dias_permanencia`: TMP em dias inteiros.
  * `dias_uti`: Dias em cuidado intensivo.
  * `custo_hospitalar`: Gastos com diárias e estrutura.
  * `custo_servicos_profissionais`: Honorários médicos.
  * `custo_opme`: Gastos com próteses/órteses.
  * `custo_sadt`: Gastos com diagnóstico/imagem/laboratório.
  * `custo_total`: Somatório de custos operacionais diretos.
  * `receita_faturada`: Valor repassado / faturado.
  * `margem_contribuicao`: `receita_faturada - custo_total`.
  * `readmissao_30d`: Booleano (1/0) indicando reinternação no mesmo diagnóstico dentro de 30 dias.
  * `indicador_obito`: Booleano (1/0) de óbito intra-hospitalar.

### Dimensão: `dim_paciente`
* `id_paciente` (PK): Código anônimo / hash de identificação.
* `sexo`: M / F.
* `idade`: Idade no momento do atendimento.
* `faixa_etaria`: Categorias padronizadas (0-17 anos, 18-39 anos, 40-59 anos, 60-79 anos, 80+ anos).
* `municipio_residencia`: Nome e UF do município.

### Dimensão: `dim_procedimento`
* `id_procedimento` (PK): Código de 10 dígitos da Tabela Unificada SIGTAP do SUS.
* `descricao_procedimento`: Descrição médica oficial do procedimento.
* `especialidade`: Clínica Médica, Cirurgia Geral, Ortopedia, Cardiologia, Obstetrícia, Oncologia, Pediatria, etc.
* `tipo_complexidade`: Média Complexidade vs. Alta Complexidade.
* `tmp_protocolo_previsto`: Tempo de permanência de referência clínica (em dias) para cálculo de desvio de diretriz.

### Dimensão: `dim_diagnostico`
* `cid_10` (PK): Código alfanumérico da Classificação Internacional de Doenças (10ª Revisão).
* `descricao_cid`: Nome da patologia / condição clínica.
* `capitulo_cid`: Grande grupo clínico (ex: Doenças do Aparelho Circulatório, Neoplasias, Doenças Respiratórias).
* `grau_severidade`: Baixo, Moderado, Alto, Crítico.

### Dimensão: `dim_setor_leito`
* `id_leito` (PK): Identificador do agrupamento de acomodação.
* `tipo_leito`: UTI Adulto, UTI Neonatal, Semi-Intensiva, Enfermaria Cirúrgica, Enfermaria Clínica, Berçário.
* `setor_ala`: Ala Norte, Ala Sul, Bloco Cirúrgico, Pavilhão Central.
* `capacidade_leitos_instalados`: Quantidade de leitos disponíveis para cálculo de leito-dia.

### Dimensão: `dim_tempo`
* `id_data` (PK): Inteiro no formato YYYYMMDD.
* `data_completa`: Formato DATE (YYYY-MM-DD).
* `ano`, `mes`, `dia`, `trimestre`, `semestre`.
* `nome_mes`, `dia_da_semana`, `eh_fim_de_semana`.
