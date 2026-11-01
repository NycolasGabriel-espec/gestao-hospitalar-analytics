# Recorte SIH/SUS publicado

- UF: Alagoas (AL).
- Competências de processamento: janeiro a dezembro de 2025, grupo RD.
- Extração: 31 de outubro de 2026, via PySUS 2.11.7.
- Registros brutos: 177.640.
- `N_AIH` consolidadas: 173.924.

As 12 competências foram obtidas. Quatro arquivos que não apareceram no catálogo PySUS foram confirmados e baixados diretamente do diretório público DATASUS `/dissemin/publicos/SIHSUS/200801_/Dados`, mantendo a conversão DBC pelo PySUS.

## Consolidação e recorte

O arquivo bruto preserva as colunas de competência de processamento (`ANO_CMPT`, `MES_CMPT`), tipo de AIH (`IDENT`) e sequências de longa permanência/remessa. Quando o mesmo `N_AIH` aparece mais de uma vez, o ETL seleciona a versão da competência mais recente; dentro da mesma competência, prioriza AIH tipo 5 e depois os campos sequenciais disponíveis. Se os critérios empatarem e as métricas divergirem, a transformação para com erro em vez de descartar uma versão sem justificativa.

O dashboard filtra a data de admissão (`DT_INTER`) entre 01/01/2025 e 31/12/2025. As competências de processamento de 2025 podem conter admissões anteriores a 2025; por outro lado, esta extração não inclui reapresentações/revisões de competências de 2026. Portanto, a série de 2025 é um retrato dos dados processados até dezembro de 2025 e pode ser atualizada em extrações posteriores.

O volume exibido é de registros AIH consolidados, não uma contagem garantida de pessoas ou episódios distintos. O Ministério da Saúde descreve a AIH tipo 5 como continuidade da internação e informa que ela mantém a data de início da AIH tipo 1 ([documentação SIH](https://wiki.saude.gov.br/sih/index.php/P%C3%A1gina_principal)).

O pipeline pseudonimiza o número de AIH com HMAC e mantém somente faixa etária e sexo na dimensão demográfica. Não há identificador persistente de pessoa nesta extração. Custos internos, margem e readmissão individual ficam indisponíveis quando a fonte não os fornece; o valor `VAL_TOT` é o valor registrado na AIH, não custo contábil.

Os arquivos brutos e processados permanecem locais e fora do Git. A extração pode ser repetida para um ano-calendário de competências com:

```bash
python3 src/extract_sih_sus.py --state AL --year 2025 --months 1 2 3 4 5 6 7 8 9 10 11 12
```

Para incluir competências de mais de um ano (por exemplo, atualizações posteriores de 2025), repita `--competence YYYY-MM` para cada mês desejado. Preserve o mesmo `PATIENT_DATA_HMAC_KEY` nas recargas e use a conta ETL restrita.
