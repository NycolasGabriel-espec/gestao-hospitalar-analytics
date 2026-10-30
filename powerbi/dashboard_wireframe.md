# 📊 Guia de Construção do Dashboard (Power BI / Looker)

Este documento especifica a arquitetura visual, filtros globais, layout e configurações de cada uma das 3 páginas do relatório executivo e operacional.

---

## Paleta de Cores Recomendada (Healthcare Standard)
* **Azul Escuro (Background / Títulos Primários):** `#1D3557` (Confiança, Autoridade)
* **Azul Médio (Séries Neutras):** `#457B9D`
* **Verde Clínico (Faixa Ótima / Margem Positiva):** `#2A9D8F`
* **Laranja / Âmbar (Alerta / Ociosidade):** `#F4A261`
* **Vermelho Carmim (Gargalo / Saturação > 85% / Prejuízo):** `#E63946`
* **Fundo da Página:** `#F8F9FA` (Off-white para descanso visual)

---

## Filtros Globais (Barra Lateral ou Cabeçalho)
Presentes em todas as páginas para permitir drill-down dinâmico:
1. **Ano / Mês** (Segmentação de dados deslizante ou dropdown)
2. **Especialidade Médica** (`dim_procedimento[especialidade]`)
3. **Tipo de Acomodação** (`dim_setor_leito[tipo_acomodacao]`)
4. **Faixa Etária do Paciente** (`dim_paciente[faixa_etaria]`)

---

## 🖥️ Tela 1: Visão Executiva Médico-Financeira
**Objetivo:** Permitir que o Diretor Clínico e o CFO avaliem em 5 segundos a saúde financeira e assistencial do hospital.

### Layout dos Componentes:
```
+-----------------------------------------------------------------------------------------+
| [Filtros: Período | Especialidade | Tipo de Leito]                                      |
+-----------------------------------------------------------------------------------------+
| [Card 1]           | [Card 2]           | [Card 3]           | [Card 4]                 |
| Total Internações  | TMP Médio (ALOS)   | Margem Contribuição| Taxa Readmissão 30d      |
| 14.820             | 4.2 dias           | R$ 2.41M (18.4%)   | 8.3%                     |
+-----------------------------------------------------------------------------------------+
| [Gráfico 1 - Dispersão / Matriz BCG Clínica]       | [Gráfico 2 - Curva ABC / Barras]   |
| Eixo X: TMP Médio (dias)                           | Top 10 Custos por Especialidade    |
| Eixo Y: Margem de Contribuição %                   | Destaque de cor para custos OPME   |
| Tamanho da Bolha: Custo Total                      |                                    |
| Rótulo: Especialidade / Procedimento               |                                    |
+-----------------------------------------------------------------------------------------+
| [Gráfico 3 - Linha com Meta]                                                            |
| Evolução Mensal da Receita Faturada vs. Custo Operacional vs. Margem %                  |
+-----------------------------------------------------------------------------------------+
```

* **Dica de Interação:** Clicar na bolha "Ortopedia" na dispersão filtra o gráfico de evolução mensal para exibir somente dados ortopédicos.

---

## 🏥 Tela 2: Gestão Operacional de Leitos & Eficiência
**Objetivo:** Permitir ao Gerente de Enfermagem e Gestor de Leitos (NIR - Núcleo Interno de Regulação) sincronizar a capacidade com a demanda.

### Layout dos Componentes:
```
+-----------------------------------------------------------------------------------------+
| [Card 1]                  | [Card 2]               | [Card 3]              | [Card 4]   |
| Taxa Ocupação Geral       | Taxa Ocupação UTI      | Giro de Leito         | Excesso TMP|
| 76.4% (Ideal)             | 89.2% (Crítico 🚨)     | 4.8 pac/leito         | +1.2 dias  |
+-----------------------------------------------------------------------------------------+
| [Visual 1 - Heatmap / Matriz de Ocupação]                                               |
| Linhas: Tipo de Acomodação (UTI Adulto, Neo, Cirúrgica, Clínica)                       |
| Colunas: Mês (Jan a Dez)                                                                |
| Valores: Taxa de Ocupação % (Formatação condicional Verde < 85%, Vermelho > 85%)        |
+-----------------------------------------------------------------------------------------+
| [Gráfico 2 - Barras Clusterizadas]                 | [Gráfico 3 - Cascata de Custos]    |
| Comparativo: TMP Real vs. TMP Protocolo            | Impacto Financeiro das Diárias     |
| por Capítulo CID-10                                | Excedentes por Unidade             |
+-----------------------------------------------------------------------------------------+
```

---

## 🔍 Tela 3: Detalhamento de Risco, Readmissão & Qualidade
**Objetivo:** Identificar grupos de risco e patologias com desfecho clínico adverso para reuniões de comitê de óbito e auditoria médica.

### Layout dos Componentes:
```
+-----------------------------------------------------------------------------------------+
| [Card 1]                  | [Card 2]               | [Card 3]              | [Card 4]   |
| Taxa Readmissão Geral     | Mortalidade Geral      | Reinternações OPME    | Custo Reint|
| 8.3%                      | 2.1%                   | 14.2%                 | R$ 380k    |
+-----------------------------------------------------------------------------------------+
| [Gráfico 1 - Barras Horizontais]                   | [Gráfico 2 - Treemap]              |
| Top 10 Patologias (CID-10) com maior % de         | Distribuição de Readmissões por    |
| Reinternação em até 30 dias                        | Faixa Etária e Grau de Severidade  |
+-----------------------------------------------------------------------------------------+
| [Tabela Analítica Dinâmica / Drill-Through]                                             |
| Colunas: CID-10 | Patologia | Esp. | Vol. Internações | TMP Real | Desvio | Readm % | Custo |
+-----------------------------------------------------------------------------------------+
```
