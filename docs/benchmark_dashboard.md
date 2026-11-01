# Dashboard local do benchmark sintético

O dashboard em `streamlit_app.py` explora quatro perguntas operacionais usando Pandas, SQL no DuckDB e gráficos Plotly. Ele lê somente `data/benchmark/hospital_analytics.duckdb`, gerado pelo projeto. Esse arquivo fica fora do Git e separado dos dados SIH/SUS em `data/processed/`.

## Executar

```bash
pip install -r requirements-dashboard.txt
python3 src/generate_benchmark_dataset.py --seed 42
streamlit run streamlit_app.py
```

O gerador aceita `--admissions` e `--output-dir`. A semente padrão é 42, o volume padrão é 15.000 internações e a saída padrão é `data/benchmark/`. Ao repetir a mesma versão do código com a mesma semente, a amostra é reproduzível.

## Regras do benchmark

- As datas de chegada são distribuídas ao longo de 2023. A hora é sorteada com maior peso entre 8h–10h e 13h–17h; por isso, os picos horários fazem parte da regra de geração.
- A espera representa minutos entre a chegada ao pronto atendimento e a internação no primeiro leito. A média-base é 190 minutos para UTI, 140 para cirurgia e 100 para clínica. O gerador acrescenta 35 minutos entre 7h e 10h e 20 minutos entre 16h e 18h, aplica variação normal de 25% da média-base e limita o valor mínimo a 15 minutos.
- A internação ocorre no horário da chegada mais a espera. A duração da permanência parte do tempo de protocolo de cada procedimento, com variação sintética por especialidade.
- A UTI tem 50 leitos, a unidade cirúrgica 92 e a clínica 78 (220 leitos no total). Para pacientes com passagem pela UTI, os primeiros `dias_uti` são alocados à UTI. Os dias restantes vão à unidade cirúrgica para revascularização/craniotomia e à unidade clínica nos outros casos críticos. As demais internações permanecem no setor de destino original.
- A ocupação mensal é `dias-paciente no mês / (leitos fixos × dias do mês)`. Os dias são distribuídos a partir da data de internação; a data de alta não conta como noite ocupada. São contados somente os dias de 2023 da coorte gerada.
- O custo total simulado soma diária hospitalar e UTI, serviços profissionais, OPME e SADT. A mistura de procedimentos, preços e variações está codificada em `src/generate_benchmark_dataset.py`.

Essas escolhas fabricam as diferenças que o painel demonstra. Não descrevem fluxos, contratos, protocolos, custos, capacidade, equipes nem resultados de um hospital real.

## Quatro conclusões do recorte padrão

Resultados calculados com 15.000 internações e seed 42:

1. **Maior espera:** o Pavilhão Intensivo Central tem média de 202 minutos e percentil 90 de 268 minutos. O Bloco Cirúrgico Ala B tem média de 153 minutos e a Ala de Internação Clínica, 114 minutos.
2. **Pico de ocupação:** o Bloco Cirúrgico Ala B chega a 98,2% em dezembro. O pico mensal da UTI é 86,1% em abril; o da Ala de Internação Clínica é 61,0% em dezembro.
3. **Maior concentração de custo:** Angioplastia Coronariana com Stent soma R$ 30,58 milhões, 13,6% do custo simulado da amostra (R$ 224,41 milhões).
4. **Horário com mais chegadas:** 9h registra 1.175 chegadas, ou 7,8% da amostra. É concentração de volume; sem escalas, capacidade horária ou filas observadas, não comprova sobrecarga de equipe ou serviço.

Os valores são descritivos do benchmark de referência. Mudar semente, quantidade ou regras de geração pode alterar essas conclusões.

## Simulador de capacidade

O painel inclui um cenário editável de admissões por mês, permanência média e leitos com equipe disponível. O cálculo é `admissões × permanência média / (leitos com equipe × dias do mês)`. A referência do painel usa os dias-paciente e a capacidade fixa da mesma amostra sintética. O cenário não é previsão e não representa um hospital real.

## Como interpretar

- “Espera” é chegada até admissão em leito, não tempo até triagem ou atendimento médico.
- A ocupação é uma reconstrução de dias-paciente com capacidade fixa e transferências definidas pelo gerador. Um indicador hospitalar real precisa do censo diário de ocupação e do histórico de leitos ativos por setor.
- O gráfico por hora mostra demanda simulada. Para afirmar sobrecarga, seriam necessários volume observado, escala da equipe, capacidade disponível e um limite operacional definido.
- Os custos são valores artificiais do benchmark. O SIH/SUS deste repositório não fornece custos contábeis, capacidade histórica nem identificador persistente de pessoa para readmissão.
