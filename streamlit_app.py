from __future__ import annotations

import calendar
from collections import Counter
from datetime import timedelta
from html import escape
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data" / "benchmark" / "hospital_analytics.duckdb"
MONTHS_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
PALETTE = {
    "navy": "#183A53",
    "blue": "#4F7891",
    "teal": "#258C7B",
    "mint": "#9AD4C4",
    "amber": "#D59A47",
    "ink": "#243746",
    "muted": "#738391",
    "grid": "#E7ECEF",
}


st.set_page_config(page_title="Hospital Analytics · Benchmark", page_icon="🏥", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #F5F7F8; color: #243746; }
      .block-container { max-width: 1480px; padding-top: 2.1rem; padding-bottom: 3rem; }
      h1, h2, h3 { color: #183A53; letter-spacing: -0.025em; }
      h1 { font-size: clamp(2rem, 3vw, 2.8rem); }
      [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E7ECEF;
        border-radius: 14px; padding: 1rem 1.1rem; box-shadow: 0 3px 12px rgba(24,58,83,.035); }
      [data-testid="stMetricLabel"] { color: #738391; }
      [data-testid="stMetricValue"] { color: #183A53; }
      [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E7ECEF; }
      .eyebrow { color: #258C7B; font-size: .74rem; font-weight: 700; letter-spacing: .12em; }
      .note-card { background: #FFFFFF; border: 1px solid #E7ECEF; border-radius: 14px;
        padding: 1rem 1.1rem; margin: .35rem 0; }
      .note-card strong { color: #183A53; }
      .subtle { color: #738391; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Lendo o benchmark sintético…")
def load_benchmark(database_path: str) -> pd.DataFrame:
    with duckdb.connect(database_path, read_only=True) as connection:
        return connection.execute(
            """
            SELECT
                f.id_atendimento,
                f.id_procedimento,
                p.descricao_procedimento,
                p.especialidade,
                f.id_leito,
                l.setor_hospitalar,
                l.leitos_operacionais,
                f.id_leito_pos_uti,
                ward.setor_hospitalar AS setor_pos_uti,
                f.data_hora_chegada,
                f.data_hora_internacao,
                f.data_hora_alta,
                f.tempo_espera_minutos,
                f.dias_permanencia,
                f.dias_uti,
                f.custo_hospitalar,
                f.custo_servicos_profissionais,
                f.custo_opme,
                f.custo_sadt,
                f.custo_total
            FROM fato_internacoes AS f
            JOIN dim_procedimento AS p USING (id_procedimento)
            JOIN dim_setor_leito AS l USING (id_leito)
            JOIN dim_setor_leito AS ward ON f.id_leito_pos_uti = ward.id_leito
            """
        ).df()


@st.cache_data(show_spinner=False)
def load_metadata(database_path: str) -> dict[str, int]:
    with duckdb.connect(database_path, read_only=True) as connection:
        row = connection.execute(
            "SELECT num_admissoes, seed, ano_chegada, leitos_operacionais FROM benchmark_metadata LIMIT 1"
        ).fetchone()
    return {
        "num_admissoes": int(row[0]),
        "seed": int(row[1]),
        "ano_chegada": int(row[2]),
        "leitos_operacionais": int(row[3]),
    }


@st.cache_data(show_spinner=False)
def load_bed_capacity(database_path: str) -> pd.DataFrame:
    with duckdb.connect(database_path, read_only=True) as connection:
        return connection.execute(
            "SELECT setor_hospitalar, leitos_operacionais FROM dim_setor_leito"
        ).df().drop_duplicates()


def money(value: float) -> str:
    return f"R$ {value:,.0f}".replace(",", ".")


def occupancy_by_month(data: pd.DataFrame, sector_filter: str) -> pd.DataFrame:
    capacities = data[["setor_hospitalar", "leitos_operacionais"]].drop_duplicates()
    if sector_filter != "Todos os setores":
        capacities = capacities.loc[capacities["setor_hospitalar"] == sector_filter]
    capacity_by_sector = capacities.set_index("setor_hospitalar")["leitos_operacionais"].to_dict()

    patient_days: Counter[tuple[str, str]] = Counter()
    for row in data.itertuples(index=False):
        admission_day = pd.Timestamp(row.data_hora_internacao).normalize()
        total_days = int(row.dias_permanencia)
        if row.id_leito == "LEITO_UTI_01":
            icu_days = min(total_days, max(0, int(row.dias_uti)))
            stays = [
                (row.setor_hospitalar, admission_day, icu_days),
                (row.setor_pos_uti, admission_day + timedelta(days=icu_days), total_days - icu_days),
            ]
        else:
            stays = [(row.setor_hospitalar, admission_day, total_days)]

        for sector, start_day, stay_days in stays:
            if sector not in capacity_by_sector:
                continue
            for offset in range(stay_days):
                occupied_day = start_day + timedelta(days=offset)
                if occupied_day.year == 2023:
                    patient_days[(occupied_day.strftime("%Y-%m"), sector)] += 1

    rows: list[dict[str, object]] = []
    for month_number, month_name in enumerate(MONTHS_PT, start=1):
        month = pd.Period(f"2023-{month_number:02d}", freq="M")
        for sector, beds in capacity_by_sector.items():
            occupied = patient_days[(str(month), sector)]
            available_bed_days = int(beds) * month.days_in_month
            rows.append({
                "mes": month.start_time,
                "mes_nome": month_name,
                "setor_hospitalar": sector,
                "dias_paciente": occupied,
                "leitos_dia_disponiveis": available_bed_days,
                "ocupacao_pct": occupied * 100 / available_bed_days if available_bed_days else 0,
            })
    return pd.DataFrame(rows)


def apply_plot_style(fig: object, height: int = 360) -> object:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=8, r=12, t=28, b=8),
        font=dict(family="Arial, sans-serif", color=PALETTE["ink"], size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor=PALETTE["grid"], zeroline=False)
    return fig


st.markdown('<p class="eyebrow">PAINEL DE DEMONSTRAÇÃO · DADOS SINTÉTICOS</p>', unsafe_allow_html=True)
st.title("Operação hospitalar em foco")
st.markdown(
    "Benchmark reproduzível para explorar espera, ocupação, custos e concentração de chegadas. "
    "Os números descrevem somente as regras da simulação."
)

if not DATABASE.exists():
    st.info(
        "Gere primeiro o benchmark. No terminal, execute `python3 src/generate_benchmark_dataset.py`; "
        "depois abra este painel com `streamlit run streamlit_app.py`."
    )
    st.stop()

data = load_benchmark(str(DATABASE))
metadata = load_metadata(str(DATABASE))
bed_capacity = load_bed_capacity(str(DATABASE))
formatted_admissions = f"{metadata['num_admissoes']:,}".replace(",", ".")
data["data_hora_chegada"] = pd.to_datetime(data["data_hora_chegada"])
data["data_hora_internacao"] = pd.to_datetime(data["data_hora_internacao"])
data["data_hora_alta"] = pd.to_datetime(data["data_hora_alta"])
data["mes_chegada"] = data["data_hora_chegada"].dt.month

with st.sidebar:
    st.markdown("### Recorte de análise")
    available_months = sorted(int(month) for month in data["mes_chegada"].unique())
    month_options = ["Todo o ano"] + [MONTHS_PT[month - 1] for month in available_months]
    selected_month = st.selectbox("Mês de chegada", month_options)
    specialties = ["Todas as especialidades"] + sorted(data["especialidade"].dropna().unique().tolist())
    selected_specialty = st.selectbox("Especialidade", specialties)
    sectors = ["Todos os setores"] + sorted(data["setor_hospitalar"].dropna().unique().tolist())
    selected_sector = st.selectbox("Setor de destino", sectors)
    st.divider()
    st.caption(
        f"{formatted_admissions} internações simuladas · seed {metadata['seed']} · "
        f"{metadata['leitos_operacionais']} leitos fixos"
    )
    st.caption("Os filtros de mês e especialidade afetam espera e chegadas. Custos também respeitam o setor. Ocupação usa o ano completo e o setor selecionado.")

analysis = data.copy()
if selected_month != "Todo o ano":
    selected_month_number = MONTHS_PT.index(selected_month) + 1
    analysis = analysis.loc[analysis["mes_chegada"] == selected_month_number]
if selected_specialty != "Todas as especialidades":
    analysis = analysis.loc[analysis["especialidade"] == selected_specialty]

cost_data = analysis
if selected_sector != "Todos os setores":
    cost_data = cost_data.loc[cost_data["setor_hospitalar"] == selected_sector]

wait_mean = analysis["tempo_espera_minutos"].mean() if not analysis.empty else 0
cost_total = cost_data["custo_total"].sum() if not cost_data.empty else 0
occupancy = occupancy_by_month(data, selected_sector)
peak_occupancy = occupancy.loc[occupancy["ocupacao_pct"].idxmax()] if not occupancy.empty else None

metric_cols = st.columns(4)
metric_cols[0].metric("Chegadas na seleção", f"{len(analysis):,}".replace(",", "."))
metric_cols[1].metric("Espera média até leito", f"{wait_mean:.0f} min")
metric_cols[2].metric("Custo simulado", money(cost_total))
metric_cols[3].metric("Pico mensal de ocupação", f"{peak_occupancy['ocupacao_pct']:.1f}%" if peak_occupancy is not None else "—")

st.markdown("## Pressão assistencial")
wait_col, occupancy_col = st.columns([1, 1.25], gap="large")

with wait_col:
    st.markdown("### Espera até internação por setor")
    st.caption("Média e percentil 90, da chegada ao pronto atendimento à admissão no leito de destino.")
    if analysis.empty:
        st.info("Não há registros para os filtros selecionados.")
    else:
        wait_summary = (
            analysis.groupby("setor_hospitalar")["tempo_espera_minutos"]
            .agg(media="mean", p90=lambda values: values.quantile(0.90))
            .reset_index()
            .sort_values("p90")
        )
        wait_long = wait_summary.melt(
            id_vars="setor_hospitalar", var_name="estatistica", value_name="minutos"
        )
        wait_long["estatistica"] = wait_long["estatistica"].map({"media": "Média", "p90": "Percentil 90"})
        fig = px.bar(
            wait_long, x="minutos", y="setor_hospitalar", color="estatistica", barmode="group",
            color_discrete_map={"Média": PALETTE["blue"], "Percentil 90": PALETTE["teal"]},
            labels={"minutos": "Minutos", "setor_hospitalar": "Setor de destino"},
        )
        fig = apply_plot_style(fig, 400)
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})

with occupancy_col:
    st.markdown("### Ocupação mensal de leitos")
    st.caption("Dias-paciente da coorte ÷ leitos-dia disponíveis. Capacidade fixa na simulação; não representa censo real.")
    fig = px.line(
        occupancy, x="mes", y="ocupacao_pct", color="setor_hospitalar", markers=True,
        color_discrete_sequence=[PALETTE["teal"], PALETTE["blue"], PALETTE["amber"]],
        labels={"mes": "Mês de 2023", "ocupacao_pct": "Ocupação (%)", "setor_hospitalar": "Setor"},
    )
    fig.update_xaxes(tickformat="%b")
    fig.update_yaxes(ticksuffix="%")
    fig = apply_plot_style(fig, 400)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})

st.markdown("## Custos e momentos de maior procura")
cost_col, demand_col = st.columns([1.1, 1], gap="large")

with cost_col:
    st.markdown("### Custos por procedimento")
    st.caption("Valores simulados e decompostos em hotelaria, serviços profissionais, OPME e SADT.")
    if cost_data.empty:
        st.info("Não há registros para os filtros selecionados.")
    else:
        cost_columns = ["custo_hospitalar", "custo_servicos_profissionais", "custo_opme", "custo_sadt"]
        cost_labels = {
            "custo_hospitalar": "Diárias e UTI",
            "custo_servicos_profissionais": "Serviços profissionais",
            "custo_opme": "OPME",
            "custo_sadt": "SADT",
        }
        top_procedures = (
            cost_data.groupby(["id_procedimento", "descricao_procedimento"], as_index=False)["custo_total"]
            .sum().nlargest(8, "custo_total")
        )
        costs_by_procedure = (
            cost_data.merge(top_procedures[["id_procedimento", "descricao_procedimento"]], on=["id_procedimento", "descricao_procedimento"])
            .groupby(["id_procedimento", "descricao_procedimento"], as_index=False)[cost_columns]
            .sum()
        )
        cost_long = costs_by_procedure.melt(
            id_vars=["id_procedimento", "descricao_procedimento"],
            value_vars=cost_columns, var_name="componente", value_name="valor",
        )
        cost_long["componente"] = cost_long["componente"].map(cost_labels)
        order = top_procedures.sort_values("custo_total")["descricao_procedimento"].tolist()
        fig = px.bar(
            cost_long, x="valor", y="descricao_procedimento", color="componente", orientation="h",
            barmode="stack", category_orders={"descricao_procedimento": order},
            color_discrete_map={
                "Diárias e UTI": PALETTE["navy"],
                "Serviços profissionais": PALETTE["blue"],
                "OPME": PALETTE["teal"],
                "SADT": PALETTE["mint"],
            },
            labels={"valor": "Custo simulado (R$)", "descricao_procedimento": "Procedimento", "componente": "Componente"},
        )
        fig.update_xaxes(tickprefix="R$ ", tickformat="~s")
        fig = apply_plot_style(fig, 440)
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})

with demand_col:
    st.markdown("### Chegadas por dia e hora")
    st.caption("Volume da chegada ao pronto atendimento; sem escala de pessoal, não permite afirmar sobrecarga.")
    if analysis.empty:
        st.info("Não há registros para os filtros selecionados.")
    else:
        arrivals = analysis.copy()
        arrivals["dia_semana"] = arrivals["data_hora_chegada"].dt.dayofweek
        arrivals["hora"] = arrivals["data_hora_chegada"].dt.hour
        heatmap = pd.crosstab(arrivals["dia_semana"], arrivals["hora"])
        heatmap = heatmap.reindex(index=range(7), columns=range(24), fill_value=0)
        fig = px.imshow(
            heatmap.values,
            x=[f"{hour:02d}h" for hour in range(24)],
            y=WEEKDAYS_PT,
            color_continuous_scale=["#F3F6F7", PALETTE["mint"], PALETTE["navy"]],
            labels={"x": "Hora de chegada", "y": "Dia da semana", "color": "Chegadas"},
            aspect="auto",
        )
        fig = apply_plot_style(fig, 440)
        fig.update_layout(coloraxis_colorbar=dict(title="Chegadas", thickness=12))
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})

st.markdown("## O que os dados desta seleção mostram")
insights: list[str] = []
if not analysis.empty:
    wait_by_sector = analysis.groupby("setor_hospitalar")["tempo_espera_minutos"].agg(
        media="mean", p90=lambda values: values.quantile(0.90)
    )
    slowest = wait_by_sector["p90"].idxmax()
    insights.append(
        f"<strong>Espera:</strong> {escape(str(slowest))} tem o maior percentil 90 da seleção, "
        f"{wait_by_sector.loc[slowest, 'p90']:.0f} minutos; a média do setor é {wait_by_sector.loc[slowest, 'media']:.0f} minutos."
    )

    arrivals_for_insight = analysis.assign(hora=analysis["data_hora_chegada"].dt.hour)
    peak_hour = int(arrivals_for_insight["hora"].value_counts().idxmax())
    peak_count = int((arrivals_for_insight["hora"] == peak_hour).sum())
    formatted_peak_count = f"{peak_count:,}".replace(",", ".")
    insights.append(
        f"<strong>Procura:</strong> a faixa de {peak_hour:02d}:00 concentra {formatted_peak_count} chegadas "
        f"({peak_count / len(analysis):.1%} da seleção). Isso indica volume, não saturação comprovada."
    )

if not cost_data.empty:
    procedure_costs = cost_data.groupby("descricao_procedimento")["custo_total"].sum().sort_values(ascending=False)
    procedure_name = escape(str(procedure_costs.index[0]))
    share = procedure_costs.iloc[0] / procedure_costs.sum() if procedure_costs.sum() else 0
    insights.append(
        f"<strong>Custos:</strong> {procedure_name} lidera o recorte com {money(procedure_costs.iloc[0])}, "
        f"equivalente a {share:.1%} dos custos simulados selecionados."
    )

if peak_occupancy is not None:
    insights.append(
        f"<strong>Ocupação:</strong> o maior valor mensal do ano é {peak_occupancy['ocupacao_pct']:.1f}% em "
        f"{escape(str(peak_occupancy['mes_nome']))} no setor {escape(str(peak_occupancy['setor_hospitalar']))}. "
        "A capacidade fixa e a coorte sintética limitam essa leitura."
    )

for insight in insights:
    st.markdown(f'<div class="note-card">{insight}</div>', unsafe_allow_html=True)

with st.container(border=True):
    st.subheader("Simulador de capacidade · cenário sintético")
    st.caption(
        "Altere admissões mensais, permanência média e leitos com equipe disponível. "
        "A fórmula simplificada é admissões × permanência ÷ leitos-dia; não prevê sazonalidade, "
        "transferências, bloqueios por turno ou demanda clínica real."
    )

    scenario_data = data.copy()
    if selected_month != "Todo o ano":
        scenario_data = scenario_data.loc[scenario_data["mes_chegada"] == selected_month_number]
    if selected_specialty != "Todas as especialidades":
        scenario_data = scenario_data.loc[scenario_data["especialidade"] == selected_specialty]
    if selected_sector != "Todos os setores":
        scenario_data = scenario_data.loc[scenario_data["setor_hospitalar"] == selected_sector]

    months_in_scope = 12 if selected_month == "Todo o ano" else 1
    arrivals_default = int(round(len(scenario_data) / months_in_scope))
    stay_default = float(scenario_data["dias_permanencia"].mean()) if not scenario_data.empty else 5.0
    if selected_sector == "Todos os setores":
        beds_default = int(bed_capacity["leitos_operacionais"].sum())
    else:
        sector_capacity = bed_capacity.loc[
            bed_capacity["setor_hospitalar"] == selected_sector, "leitos_operacionais"
        ]
        beds_default = int(sector_capacity.iloc[0]) if not sector_capacity.empty else 1

    input_cols = st.columns(3)
    with input_cols[0]:
        scenario_arrivals = st.number_input(
            "Admissões por mês", min_value=0, max_value=max(1000, arrivals_default * 3),
            value=arrivals_default, step=max(1, round(max(arrivals_default, 1) / 50)),
        )
    with input_cols[1]:
        stay_max = max(30.0, float(calendar.monthrange(2023, 1)[1]), min(90.0, stay_default * 2))
        scenario_stay = st.slider(
            "Permanência média (dias)", min_value=0.5, max_value=stay_max,
            value=min(stay_max, max(0.5, round(stay_default * 2) / 2)), step=0.5,
        )
    with input_cols[2]:
        scenario_beds = st.number_input(
            "Leitos com equipe disponível", min_value=1,
            max_value=max(100, beds_default * 3), value=max(1, beds_default), step=1,
        )

    days_in_month = (
        calendar.monthrange(2023, selected_month_number)[1]
        if selected_month != "Todo o ano"
        else 365 / 12
    )
    projected_occupancy = scenario_arrivals * scenario_stay / (scenario_beds * days_in_month) * 100
    baseline_period = occupancy
    if selected_month != "Todo o ano":
        baseline_period = baseline_period.loc[
            baseline_period["mes"].dt.month == selected_month_number
        ]
    baseline_bed_days = baseline_period["leitos_dia_disponiveis"].sum()
    baseline_occupancy = (
        baseline_period["dias_paciente"].sum() * 100 / baseline_bed_days
        if baseline_bed_days
        else None
    )
    if selected_specialty != "Todas as especialidades":
        st.caption(
            "A referência de ocupação inclui todas as especialidades do setor selecionado; "
            "o cenário usa o volume filtrado pela especialidade."
        )

    result_cols = st.columns(2)
    result_cols[0].metric(
        "Referência observada na simulação",
        f"{baseline_occupancy:.1f}%" if baseline_occupancy is not None else "—",
    )
    result_cols[1].metric("Ocupação no cenário", f"{projected_occupancy:.1f}%")
    if projected_occupancy > 100:
        st.warning(
            "O cenário ultrapassa 100% da capacidade modelada. Isso é um sinal para revisar as premissas, "
            "não uma previsão de ocupação real."
        )

st.caption(
    f"Benchmark demonstrativo, seed {metadata['seed']}. Espera e horários foram inventados para este exercício; "
    "custos e capacidade não correspondem a uma instituição real."
)
