# Contrato de dados para o piloto hospitalar

O piloto começa por dados agregados diários ou mensais e fica no banco separado `hospital_pilot`. As tabelas não são consultadas pela API da Vercel nem pelas contas `dashboard_app` e `powerbi_reader`. A aplicação ainda não possui vínculo entre usuário e hospital; publicar esses dados no dashboard exige primeiro implementar e revisar autorização por unidade.

## Arquivos aceitos

Use UTF-8, cabeçalho exatamente igual ao especificado e uma linha por chave de negócio. Datas usam `YYYY-MM-DD`; mês usa `YYYY-MM`; decimais usam ponto. Campos de setor, turno, tipo, especialidade e centro de custo devem usar códigos controlados. O validador rejeita qualquer coluna extra, inclusive identificadores individuais que não fazem parte do contrato.

### `bed_census.csv`

`hospital_id,observation_date,shift_code,sector_code,bed_type,operational_beds,staffed_beds,occupied_beds,blocked_beds`

Uma linha por hospital, data, turno, setor e tipo de leito. `staffed_beds` e `blocked_beds` não podem superar `operational_beds`. Ocupação acima da capacidade gera aviso para revisão porque pode representar contingência assistencial ou erro de integração.

### `admissions_monthly.csv`

`hospital_id,ano_mes,especialidade,id_procedimento,volume_admissoes,volume_altas,dias_paciente`

Totais mensais. Não inclua número de prontuário, AIH, CNS, nome, data individual de admissão/alta ou qualquer chave que permita seguir uma pessoa. Essa tabela não permite calcular readmissões.

### `financial_monthly.csv`

`hospital_id,ano_mes,centro_custo,id_procedimento,receita_recebida,custo_hospitalar,custo_servicos_profissionais,custo_opme,custo_sadt`

Totais reconciliados com a contabilidade. Valores negativos podem ser ajustes ou estornos e precisam seguir a convenção contábil do hospital. Não derive custo ou margem a partir do valor de AIH do SIH/SUS.

## Validar antes de importar

```bash
python3 src/validate_hospital_pilot.py \
  --bed-census /caminho/bed_census.csv \
  --admissions-monthly /caminho/admissions_monthly.csv \
  --financial-monthly /caminho/financial_monthly.csv
```

O comando retorna JSON com linhas verificadas, erros e avisos sem imprimir valores das linhas. Um código de saída diferente de zero bloqueia a etapa de importação.

## Banco e governança

Execute [09_hospital_pilot_mysql.sql](../sql/09_hospital_pilot_mysql.sql) como DBA. Ele cria um banco separado e não concede acesso às contas existentes. Crie uma credencial própria de ingestão com privilégios somente no banco do piloto, restrinja a origem da conexão e mantenha a credencial fora da Vercel.

Antes de conectar uma API ou painel, o piloto precisa ter: responsável pelo dado e finalidade documentada; acordo de tratamento e retenção; vínculo de usuário com `hospital_id`; testes de acesso cruzado entre hospitais; auditoria de consultas; e fluxo de correção/exclusão. Identidade para readmissões fica fora deste contrato até aprovação de governança e desenho de pseudonimização no hospital de origem.
