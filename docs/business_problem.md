# 🏥 Definição do Problema de Negócio (Healthcare Analytics)

> Este documento descreve perguntas de negócio, não resultados medidos. O benchmark do projeto é sintético, e os limiares de ocupação são exemplos a validar localmente. O SIH/SUS não fornece custos contábeis, censo diário/capacidade histórica por leito nem uma chave de pessoa para calcular readmissão neste pipeline; essas métricas exigem fontes adicionais validadas.

## Contexto do Setor
No ecossistema de saúde — tanto na saúde pública (SUS) quanto na saúde suplementar (hospitais privados e operadoras de planos de saúde) — as instituições enfrentam o que a literatura médica e de gestão chama de **"Tríplice Meta da Saúde" (Triple Aim)**:
1. **Melhorar a experiência e a qualidade do cuidado** ao paciente;
2. **Aumentar a saúde populacional e a segurança clínica** (reduzir infecções hospitalares e óbitos evitáveis);
3. **Reduzir o custo per capita do cuidado** e eliminar desperdícios operacionais.

Com o envelhecimento populacional, inflação médica (VCMH) historicamente acima dos índices gerais de preços e escassez de recursos hospitalares, a gestão intuitiva tornou-se inviável. É imperativo adotar uma governança analítica orientada a dados (**Data-Driven Healthcare**).

---

## As 4 Dores Críticas da Diretoria Médico-Financeira

### 1. Rentabilidade, Custos e Margem de Procedimentos
* **Problema:** A instituição realiza milhares de procedimentos por mês, mas não tem clareza de quais linhas de cuidado são superavitárias e quais geram prejuízo operacional crônico.
* **Agravante:** O consumo desregulamentado de **OPME (Órteses, Próteses e Materiais Especiais)** e medicamentos de alto custo varia desproporcionalmente entre cirurgiões para a mesma patologia, corroendo margens financeiras.
* **Questão-Chave:** *Quais especialidades e procedimentos trazem maior retorno vs. quais geram déficit operacional após custos de materiais e hotelaria hospitalar?*

### 2. Eficiência Assistencial e Tempo Médio de Permanência (TMP / ALOS)
* **Problema:** Pacientes internados além do protocolo clínico previsto aumentam drasticamente o custo por atendimento e elevam o risco de infecções hospitalares (IRAS - Infecções Relacionadas à Assistência à Saúde).
* **Agravante:** No modelo de diária fixa ou tabela pré-fixada (SUS / DRG), cada dia excedente após a alta prevista representa custo puro sem receita incremental associada.
* **Questão-Chave:** *Qual é o desvio médio entre o tempo de internação real vs. o protocolo de referência? Quanto as diárias excedentes custam à instituição anualmente?*

### 3. Gestão e Ociosidade de Leitos (Bed Capacity & Turnaround)
* **Problema:** A falta de sincronização entre altas hospitalares, higienização de leitos e admissões cirúrgicas gera o paradoxo de **filas no pronto-socorro / UTI** coexistindo com **ociosidade em enfermarias gerais**.
* **Impacto Operacional:**
  * Ocupação de UTI acima de 85% gera risco de saturação e cancelamento de cirurgias eletivas de alta complexidade.
  * Ocupação geral abaixo de 65% indica capacidade instalada ociosa e capital imobilizado gerando custo fixo.
* **Questão-Chave:** *Qual a taxa de ocupação real por tipo de acomodação (UTI vs. Enfermaria) e qual é o giro de leito efetivo?*

### 4. Taxa de Readmissão Hospitalar em 30 Dias (Qualidade & Desfecho)
* **Problema:** Pacientes que recebem alta e retornam ao hospital pelo mesmo diagnóstico em menos de 30 dias representam potenciais falhas no desmame, descontinuidade terapêutica ambulatorial ou complicações pós-operatórias.
* **Impacto:** Além de sobrecarregar leitos de urgência, no setor privado a readmissão frequentemente acarreta glosas contratuais por parte das operadoras e penalidades nos modelos de remuneração baseados em valor (*Fee-for-Value*).
* **Questão-Chave:** *Quais diagnósticos (CID-10) e especialidades concentram as maiores taxas de readmissão precoce e quais são os fatores de risco associados?*

---

## Indicadores de Desempenho (KPIs)

| Indicador | Sigla / Fórmula | Significado de Negócio |
| :--- | :--- | :--- |
| **Tempo Médio de Permanência** | `TMP` / `ALOS = Total Dias-Paciente / Total Admissões` | Eficiência clínica no giro do leito |
| **Taxa de Ocupação de Leitos** | `(Total Dias-Paciente / Total Leitos-Dia Disponíveis) * 100` | Saturação vs. Ociosidade da infraestrutura hospitalar |
| **Custo Médio Paciente-Dia** | `Custo Total Alocado / Dias de Permanência` | Intensidade de consumo diário de recursos |
| **Margem de Contribuição** | `Receita Faturada - Custos Diretos (Serviços + OPME + Insumos)` | Lucratividade ou déficit por linha de cuidado |
| **Taxa de Readmissão em 30 Dias** | `Readmissões conhecidas <= 30d / internações com indicador conhecido` | Indicador descritivo; exige chave de pessoa validada e cobertura conhecida |
| **Índice de Mortalidade Hospitalar** | `Óbitos conhecidos / internações com indicador conhecido * 100` | Indicador descritivo, não ajustado por severidade |
