// ==============================================================================
// PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
// ARQUIVO: power_query_setup.m
// DESCRIÇÃO: Código M do Power Query para carregar as tabelas do Star Schema
// ==============================================================================

// INSTRUÇÕES:
// No Power BI Desktop:
// 1. Vá em "Página Inicial" > "Transformar Dados" (abre o Power Query).
// 2. Crie um parâmetro chamado "PastaProjeto" apontando para a pasta "data/processed".
// 3. Em "Nova Consulta" > "Consulta Nula" > "Editor Avançado", cole os códigos abaixo.

// ------------------------------------------------------------------------------
// CONSULTA 1: dim_tempo
// ------------------------------------------------------------------------------
let
    Fonte = Csv.Document(File.Contents(PastaProjeto & "dim_tempo.csv"), [Delimiter=";", Columns=10, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos,{
        {"id_data", Int64.Type}, 
        {"data_completa", type date}, 
        {"ano", Int64.Type}, 
        {"mes", Int64.Type}, 
        {"dia", Int64.Type}, 
        {"nome_mes", type text}, 
        {"trimestre", Int64.Type}, 
        {"ano_mes", type text}, 
        {"dia_semana", type text}, 
        {"eh_fim_semana", type logical}
    })
in
    Tipos

// ------------------------------------------------------------------------------
// CONSULTA 2: dim_paciente
// ------------------------------------------------------------------------------
let
    Fonte = Csv.Document(File.Contents(PastaProjeto & "dim_paciente.csv"), [Delimiter=";", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos,{
        {"id_paciente", type text}, 
        {"sexo", type text}, 
        {"faixa_etaria", type text}
    })
in
    Tipos

// ------------------------------------------------------------------------------
// CONSULTA 3: dim_procedimento
// ------------------------------------------------------------------------------
let
    Fonte = Csv.Document(File.Contents(PastaProjeto & "dim_procedimento.csv"), [Delimiter=";", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos,{
        {"id_procedimento", type text}, 
        {"descricao_procedimento", type text}, 
        {"especialidade", type text}, 
        {"complexidade", type text}, 
        {"porte_cirurgico", type text}, 
        {"tmp_protocolo_previsto", type number}
    })
in
    Tipos

// ------------------------------------------------------------------------------
// CONSULTA 4: dim_diagnostico
// ------------------------------------------------------------------------------
let
    Fonte = Csv.Document(File.Contents(PastaProjeto & "dim_diagnostico.csv"), [Delimiter=";", Columns=4, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos,{
        {"cid_10", type text}, 
        {"descricao_cid", type text}, 
        {"capitulo_cid", type text}, 
        {"grau_severidade", type text}
    })
in
    Tipos

// ------------------------------------------------------------------------------
// CONSULTA 5: dim_setor_leito
// ------------------------------------------------------------------------------
let
    Fonte = Csv.Document(File.Contents(PastaProjeto & "dim_setor_leito.csv"), [Delimiter=";", Columns=4, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos,{
        {"id_leito", type text}, 
        {"tipo_acomodacao", type text}, 
        {"setor_hospitalar", type text}, 
        {"leitos_operacionais", Int64.Type}
    })
in
    Tipos

// ------------------------------------------------------------------------------
// CONSULTA 6: fato_internacoes
// ------------------------------------------------------------------------------
let
    Fonte = Csv.Document(File.Contents(PastaProjeto & "fato_internacoes.csv"), [Delimiter=";", Columns=20, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos,{
        {"id_atendimento", type text}, 
        {"id_paciente", type text}, 
        {"id_procedimento", type text}, 
        {"cid_10", type text}, 
        {"id_leito", type text}, 
        {"id_data_admissao", Int64.Type}, 
        {"id_data_alta", Int64.Type}, 
        {"dias_permanencia", Int64.Type}, 
        {"dias_uti", Int64.Type}, 
        {"qtd_diarias", Int64.Type}, 
        {"custo_hospitalar", type number}, 
        {"custo_servicos_profissionais", type number}, 
        {"custo_opme", type number}, 
        {"custo_sadt", type number}, 
        {"custo_total", type number}, 
        {"receita_faturada", type number}, 
        {"margem_contribuicao", type number}, 
        {"status_desfecho", type text}, 
        {"indicador_obito", Int64.Type}, 
        {"readmissao_30d", type logical}
    })
in
    Tipos
