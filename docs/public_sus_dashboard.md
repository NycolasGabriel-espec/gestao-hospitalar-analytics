# Dashboard com dados públicos do SUS — Alagoas, 2025

## Fontes

- **AIHs e valores registrados:** SIH/SUS de Alagoas, com data de admissão entre janeiro e dezembro de 2025. A extração local contém as competências de processamento de janeiro a dezembro de 2025, grupo RD, obtidas pelo DATASUS/PySUS.
- **Leitos cadastrados:** arquivos mensais do conjunto [Hospitais e Leitos (CNES)](https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos), competências de 2025. Leitos gerais e de UTI são somados por UF e mês; dados de estabelecimento não entram na camada agregada.
- **Fila regulatória:** relatório oficial [Fila de Espera 2022–2025 — agosto](https://cidadao.saude.al.gov.br/wp-content/uploads/2025/09/Fila-de-Espera-2022-2025-AGOSTO.pdf), da Secretaria de Estado da Saúde de Alagoas. O retrato do SISREG foi extraído em 10/08/2025.
- **Descrições SIGTAP:** nomes dos códigos exibidos no ranking foram conferidos na [tabela SIGTAP/DATASUS](https://wiki.datasus.gov.br/sigtap/index.php/P%C3%A1gina_principal). Os códigos sem descrição local continuam identificados pelo código SIGTAP.

## Regras de cálculo

- O seletor usa o mês da data de admissão (`DT_INTER`), não a competência de processamento. O panorama considera somente admissões entre 01/01/2025 e 31/12/2025.
- As tabelas contam AIHs consolidadas por `N_AIH`. Quando o mesmo número reaparece, o ETL seleciona a competência de processamento mais recente; em empate, prioriza a AIH tipo 5, seguida dos campos sequenciais disponíveis. Empates ainda conflitantes interrompem a transformação para evitar uma escolha arbitrária.
- O volume é de registros AIH, não uma contagem garantida de pessoas ou de episódios distintos. AIHs tipo 5 podem representar continuidade de uma mesma permanência; o SIH documenta que a data de início permanece a da internação original ([documentação SIH](https://wiki.saude.gov.br/sih/index.php/P%C3%A1gina_principal)).
- Permanência média e valor registrado são agregados por mês de admissão e código do procedimento. O valor da AIH não detalha custo operacional, recebimento efetivo ou margem.
- Dias-paciente estimados distribuem os dias informados na AIH entre os meses de 2025 que cada registro atravessa. A taxa apresentada é `dias-paciente SIH / (leitos SUS CNES × dias do mês) × 100`.
- O CNES é um retrato cadastral mensal. A taxa é uma aproximação estadual e pode divergir do censo diário, de leitos bloqueados, da capacidade operacional ou da ocupação observada por estabelecimento.
- Para o SISREG, a idade de cada solicitação pendente é a diferença, em dias, entre a data do pedido e 10/08/2025. O gráfico usa o percentil 90 (P90), mediana e número de solicitações. Só são apresentados grupos por procedimento com pelo menos 30 solicitações.

## Limites

A extração SIH disponível termina na competência de processamento 12/2025 e não inclui eventuais reapresentações ou revisões em competências de 2026. Assim, a coorte de admissões de 2025 não deve ser tratada como fechamento definitivo; o processamento do SIH permite reapresentações posteriores segundo as regras vigentes ([Portaria SAES/MS nº 1.110/2021](https://bvsms.saude.gov.br/bvs/saudelegis/Saes/2021/prt1110_18_11_2021.html)).

O arquivo do SISREG representa solicitações ainda pendentes, não um histórico de atendimentos concluídos. Portanto, o painel mostra espera acumulada das solicitações que continuavam na fila na data de extração; não mede tempo médio concluído, tempo até internação, espera por setor nem espera atual.

As fontes públicas deste recorte não informam hora de chegada, escala de equipe, capacidade por turno ou setor interno de destino. O painel não afirma sobrecarga por dia/horário e não substitui dados operacionais do hospital. A [documentação do Ministério da Saúde sobre sistemas de regulação](https://www.gov.br/saude/pt-br/composicao/saes/drac/regulacao/regulacao-do-acesso/sistemas-de-informacao) descreve o acesso do gestor; por isso o dashboard usa somente o relatório público estadual.

## Carga para a Vercel

Os agregados de SIH/SUS, CNES, ocupação estimada e SISREG são publicados pela conta MySQL `analytics_loader`; a aplicação Vercel recebe somente leitura nas views e tabelas destinadas ao dashboard. Os dados do SIH são reconciliados antes de agregar e somente os totais por mês/procedimento chegam ao MySQL. Para atualizar o SIH e recalcular a ocupação com os leitos CNES que já estão carregados:

```bash
npm run mysql:public-sus:setup
uv run python src/load_public_sus_to_mysql.py --sih-only --dry-run
uv run python src/load_public_sus_to_mysql.py --sih-only
```

Para atualizar também as fontes CNES e SISREG, execute o carregador sem `--sih-only`. Ele baixa ou reutiliza os arquivos em `data/public_sus/`, pasta ignorada pelo Git. Use `--cnes-zip` e `--sisreg-pdf` para apontar arquivos locais já baixados. A carga integral publica 12 agregados mensais CNES, 12 taxas estimadas e os grupos SISREG que passam a supressão mínima.

O `--dry-run` não conecta ao MySQL. Por isso, com `--sih-only --dry-run` ele valida somente os agregados SIH e informa `occupancy_checked: false`; a ocupação baseada nos leitos já carregados é validada durante a carga real. O dry-run completo valida SIH, CNES, ocupação e SISREG sem escrever no banco.

## Proveniência e qualidade da carga

Cada fonte publicada tem um registro em `public_sus_dataset_manifest`: URL de origem, período coberto, data final de referência, registros de origem, linhas agregadas, SHA-256 do arquivo e horário UTC da carga. A view `vw_public_sus_dataset_manifest` expõe somente metadados sem hash para a aplicação e Power BI. A tela apresenta a data da carga e as datas de referência SIH/SUS, CNES e SISREG; manifesto vazio ou indisponível aparece como estado incompleto.

Antes do `--dry-run` ou da escrita no MySQL, `src/public_sus_quality.py` bloqueia ausência de meses de 2025, chaves duplicadas, divergência entre total mensal e procedimento, inconsistência entre leitos gerais/UTI/total, denominadores ou fórmulas de ocupação inválidos e grupos SISREG abaixo do limite de 30. Ocupação estimada acima de 100% gera aviso para revisão, pois pode refletir a natureza do proxy ou erro na fonte. O relatório de qualidade e o resumo do manifesto aparecem no JSON do `--dry-run`.

Para validar a carga completa sem alterar o banco:

```bash
uv run python src/load_public_sus_to_mysql.py --dry-run
```

O workflow `.github/workflows/ci.yml` executa as suítes Node e Python em pull requests e pushes. A CI não acessa dados hospitalares locais nem credenciais MySQL.
