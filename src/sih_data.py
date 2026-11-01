"""Normalização e reconciliação de versões dos registros SIH/SUS (RD)."""

from __future__ import annotations

import pandas as pd


METRIC_COLUMNS = [
    "DT_INTER", "DT_SAIDA", "DIAS_PERM", "QT_DIARIAS", "DIAG_PRINC",
    "PROC_REA", "VAL_TOT", "SEXO", "IDADE", "COD_IDADE", "MORTE", "UTI_MES_TO",
]


def consolidate_aih_versions(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Return one best-supported row per N_AIH and the number of extra rows.

    The latest processing competence wins. For records in the same competence,
    AIH type 5 (continuation) wins, followed by its sequence, the source row
    sequence and available field completeness. Equally ranked conflicting rows
    are rejected rather than silently selected.
    """
    if "N_AIH" not in frame.columns:
        raise ValueError("O arquivo SIH/SUS precisa conter N_AIH.")

    df = frame.copy()
    for column in ("ANO_CMPT", "MES_CMPT", "IDENT", "SEQ_AIH5", "SEQUENCIA"):
        if column not in df.columns:
            df[column] = pd.NA

    df["N_AIH"] = (
        df["N_AIH"].astype("string").str.strip().str.upper()
        .str.replace(r"\.0+$", "", regex=True)
    )
    df["N_AIH"] = df["N_AIH"].mask(df["N_AIH"].isin(["", "NAN", "NONE", "<NA>"]))
    df = df.dropna(subset=["N_AIH"]).copy()
    extra_rows = int(df.duplicated(subset=["N_AIH"]).sum())
    if not extra_rows:
        return df, 0

    def integer_rank(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce").fillna(-1).astype("int64")

    year = integer_rank(df["ANO_CMPT"])
    month = integer_rank(df["MES_CMPT"])
    valid_competence = year.ge(1992) & month.between(1, 12)
    df["_competence_rank"] = (year * 100 + month).where(valid_competence, -1)
    df["_type_rank"] = df["IDENT"].astype("string").str.strip().map({"1": 1, "5": 2}).fillna(0).astype("int64")
    df["_aih5_sequence_rank"] = integer_rank(df["SEQ_AIH5"])
    df["_source_sequence_rank"] = integer_rank(df["SEQUENCIA"])

    duplicate_ids = df.loc[df.duplicated("N_AIH", keep=False), "N_AIH"].unique()
    unresolved = df.loc[df["N_AIH"].isin(duplicate_ids)].groupby("N_AIH")["_competence_rank"].max().le(0)
    if unresolved.any():
        raise ValueError(
            "Há N_AIH repetidos sem competência de processamento válida; "
            "reextraia preservando ANO_CMPT e MES_CMPT."
        )

    metric_columns = [column for column in METRIC_COLUMNS if column in df.columns]
    df["_completeness_rank"] = df[metric_columns].notna().sum(axis=1)
    rank_columns = [
        "_competence_rank", "_type_rank", "_aih5_sequence_rank",
        "_source_sequence_rank", "_completeness_rank",
    ]
    ordered = df.sort_values(["N_AIH", *rank_columns], kind="mergesort")
    highest_rank = ordered.groupby("N_AIH")[rank_columns].transform("last")
    candidates = ordered.loc[ordered[rank_columns].eq(highest_rank).all(axis=1)]
    conflicts = candidates.groupby("N_AIH")[metric_columns].nunique(dropna=False).gt(1).any(axis=1)
    if conflicts.any():
        raise ValueError(
            f"{int(conflicts.sum()):,} AIHs têm versões conflitantes na mesma competência "
            "sem desempate seguro; a transformação foi interrompida."
        )

    consolidated = ordered.drop_duplicates(subset=["N_AIH"], keep="last").copy()
    consolidated.drop(columns=rank_columns, inplace=True)
    return consolidated, extra_rows
