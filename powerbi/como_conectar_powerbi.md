# Como conectar o Power BI Desktop aos dados do projeto

Este guia mostra como importar arquivos locais de desenvolvimento ou consultar as views agregadas do MySQL em produção.

> **macOS:** O Power BI Desktop é nativo do Windows. Em um Mac, use uma máquina Windows, o Power BI Service com conta corporativa ou abra o dashboard HTML do projeto em um navegador.

## Arquivos locais

Os arquivos CSV ficam em `data/processed/`, usam UTF-8 e `;` como delimitador. Eles podem conter uma linha por internação, com diagnóstico, datas, custos e desfecho. Use somente o benchmark sintético em ambientes pessoais e não envie arquivos derivados de dados reais ao Power BI Service.

No Power BI Desktop, selecione **Obter Dados → Texto/CSV**, escolha cada arquivo, defina o delimitador como ponto e vírgula e carregue as seis tabelas. Depois, crie relações muitos-para-um das chaves de `fato_internacoes` para as dimensões e aplique as medidas em `dax_measures.dax`.

## MySQL remoto

Em produção, conecte usando a conta `powerbi_reader` e somente as views agregadas. Use o endpoint MySQL fornecido pelo serviço de banco conectado à aplicação Vercel. Veja [docs/mysql_integration.md](../docs/mysql_integration.md).

1. No Power BI Desktop, escolha **Obter Dados → Banco de Dados MySQL**.
2. Informe o host, a porta e o banco fornecidos pelo serviço MySQL.
3. Selecione **Banco de dados** e autentique como `powerbi_reader`.
4. Habilite e valide TLS no cliente antes de salvar as credenciais.
5. Selecione somente `vw_painel_executivo_mensal`, `vw_eficiencia_leitos_setor`, `vw_detalhe_clinico_risco` e as quatro views dimensionais `vw_dim_*`.

Nunca use `root`, `dashboard_app` ou `analytics_loader` no Power BI. Não conceda leitura de `fato_internacoes` ou `dim_paciente` ao leitor de BI. As views ocultam grupos com menos de 10 internações, mas isso não garante anonimização contra cruzamentos ou ataques por diferença.

## Modelo e medidas

Quando precisar de um modelo dimensional completo para análise, use o conjunto sintético local. As views remotas foram agregadas para reduzir a exposição e não expõem as chaves de pessoa ou atendimento. Use `powerbi/dashboard_wireframe.md` para montar os visuais e `powerbi/dax_measures.dax` como referência de medidas.
