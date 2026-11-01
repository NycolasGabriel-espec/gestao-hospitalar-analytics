# Recorte SIH/SUS publicado

- UF: Alagoas (AL).
- Competências: janeiro a dezembro de 2025, grupo RD.
- Extração: 31 de outubro de 2026, via PySUS 2.11.7.
- Registros brutos: 177.640.
- AIHs distintas após remoção de duplicatas: 173.924.

As 12 competências foram obtidas. Quatro arquivos que não apareceram no catálogo PySUS foram confirmados e baixados diretamente do diretório público DATASUS `/dissemin/publicos/SIHSUS/200801_/Dados`, mantendo a conversão DBC pelo PySUS.

As datas de admissão podem ser anteriores a 2025: o recorte seleciona a competência de processamento da AIH. Os gráficos do dashboard agrupam por mês de admissão, identificado no filtro. As views suprimem grupos com menos de 10 internações, portanto os totais publicados podem ser menores que o conjunto carregado.

O pipeline pseudonimiza as chaves com HMAC e mantém somente faixa etária e sexo na dimensão de paciente. Custos internos, margem, capacidade de leitos e readmissão individual ficam indisponíveis quando não são fornecidos pela fonte. A deduplicação por AIH mantém a primeira ocorrência na ordem das competências.

Os arquivos brutos e processados permanecem locais e fora do Git. A credencial web consulta somente views agregadas. A extração pode ser repetida com:

```bash
python3 src/extract_sih_sus.py --state AL --year 2025 --months 1 2 3 4 5 6 7 8 9 10 11 12
```

Para recargas, preserve o mesmo `PATIENT_DATA_HMAC_KEY` e use a conta ETL restrita.
