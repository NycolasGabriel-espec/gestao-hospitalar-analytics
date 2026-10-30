# 🔌 Como Conectar o Power BI Desktop aos Dados do Projeto

Este tutorial passo a passo explica como carregar as tabelas do projeto no **Power BI Desktop**, configurar o modelo de dados (*Star Schema*) e aplicar as medidas DAX.

---

> [!NOTE]
> **Aviso sobre macOS:** O aplicativo **Power BI Desktop** é desenvolvido nativamente pela Microsoft apenas para **Windows**. 
> Se você estiver utilizando um Mac, você pode:
> 1. Abrir o Power BI Desktop em uma máquina virtual Windows (Parallels Desktop, UTM ou VMware Fusion) ou em uma máquina corporativa/remota.
> 2. Utilizar o **Power BI Service (Navegador)** em [app.powerbi.com](https://app.powerbi.com) com sua conta corporativa/estudante.
> 3. Visualizar o dashboard interativo gerado em Python/HTML localmente no Safari ou Google Chrome.

---

## 📥 Passo 1: Localização dos Arquivos de Dados

Os arquivos processados prontos para importação estão localizados em:
```
gestao-hospitalar-analytics/data/processed/
```

Arquivos disponíveis:
* `fato_internacoes.csv` (ou `.parquet`)
* `dim_tempo.csv` (ou `.parquet`)
* `dim_paciente.csv` (ou `.parquet`)
* `dim_procedimento.csv` (ou `.parquet`)
* `dim_diagnostico.csv` (ou `.parquet`)
* `dim_setor_leito.csv` (ou `.parquet`)

*(Obs: Os arquivos CSV utilizam **delimitador ponto e vírgula `;`** e codificação **UTF-8**).*

---

## ⚙️ Passo 2: Importando no Power BI Desktop

### Método A: Importação Rápida via Interface
1. Abra o **Power BI Desktop**.
2. Na aba **Página Inicial (Home)**, clique em **Obter Dados (Get Data)** > **Texto/CSV**.
3. Navegue até a pasta `gestao-hospitalar-analytics/data/processed/` e selecione `fato_internacoes.csv`.
4. Na janela de pré-visualização:
   * **Delimitador:** selecione `Ponto e vírgula (Semicolon)`.
   * **Codificação de Arquivo:** `65001: Unicode (UTF-8)`.
5. Clique em **Carregar (Load)**.
6. Repita o processo para as outras 5 tabelas dimensionais:
   * `dim_tempo.csv`
   * `dim_paciente.csv`
   * `dim_procedimento.csv`
   * `dim_diagnostico.csv`
   * `dim_setor_leito.csv`

### Método B: Usando o Script Power Query (M) Automatizado
1. No menu superior, clique em **Transformar Dados (Transform Data)**.
2. No painel esquerdo, clique com o botão direito > **Nova Consulta** > **Consulta Nula**.
3. Clique em **Editor Avançado** e copie o código correspondente do arquivo [`powerbi/power_query_setup.m`](file:///Users/nycolas/gestao-hospitalar-analytics/powerbi/power_query_setup.m).

---

## 🔗 Passo 3: Configurando os Relacionamentos (Star Schema)

No Power BI Desktop, vá para a visão de **Modelo (Model View)** no painel esquerdo (ícone de diagrama).

Conecte as tabelas arrastando os campos correspondentes:

| Da Tabela Fato (`fato_internacoes`) | Para a Tabela Dimensão | Cardinalidade | Direção do Filtro |
| :--- | :--- | :--- | :--- |
| `id_paciente` | `dim_paciente[id_paciente]` | Muitos para um `(*:1)` | Única (Dimensão filtra Fato) |
| `id_procedimento` | `dim_procedimento[id_procedimento]` | Muitos para um `(*:1)` | Única |
| `cid_10` | `dim_diagnostico[cid_10]` | Muitos para um `(*:1)` | Única |
| `id_leito` | `dim_setor_leito[id_leito]` | Muitos para um `(*:1)` | Única |
| `id_data_admissao` | `dim_tempo[id_data]` | Muitos para um `(*:1)` | Única (Ativa) |
| `id_data_alta` | `dim_tempo[id_data]` | Muitos para um `(*:1)` | Única (Inativa - opcional) |

---

## 📐 Passo 4: Criando a Tabela de Medidas DAX

1. Na visão de **Relatório (Report View)**, clique em **Inserir Dados (Enter Data)** na aba *Página Inicial*.
2. Dê o nome de `_Medidas` à tabela e clique em **Carregar**.
3. Clique com o botão direito na tabela `_Medidas` e selecione **Nova Medida**.
4. Copie as fórmulas prontas do arquivo [`powerbi/dax_measures.dax`](file:///Users/nycolas/gestao-hospitalar-analytics/powerbi/dax_measures.dax).
   * Exemplo:
     ```dax
     Total Internacoes = COUNTROWS(fato_internacoes)
     ```
     ```dax
     TMP Medio (Dias) = AVERAGE(fato_internacoes[dias_permanencia])
     ```
     ```dax
     Margem de Contribuicao % = DIVIDE([Margem de Contribuicao Total], [Receita Total Faturada], 0)
     ```

---

## 🎨 Passo 5: Montando os Visuais

Siga o roteiro de telas e wireframes detalhado em [`powerbi/dashboard_wireframe.md`](file:///Users/nycolas/gestao-hospitalar-analytics/powerbi/dashboard_wireframe.md) para montar os cartões de KPIs, gráficos de dispersão médico-financeira, mapa de calor de ocupação de leitos e análise de readmissão.
