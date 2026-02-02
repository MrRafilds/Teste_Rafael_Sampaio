from __future__ import annotations

import os
import re
import csv
import zipfile
import logging
from typing import Dict, Iterable, List, Optional, Tuple
from logging.handlers import RotatingFileHandler

import requests
import pandas as pd


# =========================
# Config
# =========================

CADOP_URL = "https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv"

OUT_COLS = ["CNPJ", "RazaoSocial", "Trimestre", "Ano", "ValorDespesas"]

ACCOUNT_PREFIXES = ("411",)  # heurística por conta
DESC_KEYWORDS_RE = re.compile(r"(?:event|sinistr)", re.IGNORECASE)

CHUNKSIZE = 250_000
FINAL_ZIP_NAME = "consolidado_despesas.zip"
FINAL_CSV_NAME = "consolidado_despesas.csv"

FILE_Q_RE = re.compile(r"([1-4])T(20\d{2})", re.IGNORECASE)


# =========================
# Logging
# =========================

def setup_logger(out_dir: str) -> logging.Logger:
    os.makedirs(out_dir, exist_ok=True)
    logs_dir = os.path.join(out_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    logger = logging.getLogger("ans_1_3_v2")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    fh = RotatingFileHandler(
        os.path.join(logs_dir, "run.log"),
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    return logger


# =========================
# Utils
# =========================

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def norm_cnpj(x: str) -> str:
    return re.sub(r"\D+", "", str(x or ""))

def parse_money_br(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    s = s.str.replace("R$", "", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")

def derive_year_quarter_from_date_col(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    dt = pd.to_datetime(df["DATA"], errors="coerce")
    bad = dt.isna()
    if bad.any():
        dt2 = pd.to_datetime(df.loc[bad, "DATA"], errors="coerce", dayfirst=True)
        dt.loc[bad] = dt2
    ano = dt.dt.year
    trimestre = ((dt.dt.month - 1) // 3 + 1).astype("Int64")
    return dt, ano, trimestre

def derive_year_quarter_from_filename(path: str) -> Tuple[Optional[int], Optional[int]]:
    m = FILE_Q_RE.search(os.path.basename(path))
    if not m:
        return None, None
    return int(m.group(2)), int(m.group(1))


# =========================
# CADOP
# =========================

def download_cadop(cache_dir: str, logger: logging.Logger) -> str:
    ensure_dir(cache_dir)
    out_path = os.path.join(cache_dir, "Relatorio_cadop.csv")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        logger.info(f"CADOP cache OK: {out_path}")
        return out_path

    logger.info(f"Baixando CADOP: {CADOP_URL}")
    r = requests.get(CADOP_URL, timeout=120)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    logger.info(f"CADOP salvo em: {out_path}")
    return out_path

def pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Escolhe a primeira coluna que existir no DF, comparando de forma case-insensitive
    e tolerante a underscores.
    """
    norm_map = {}
    for c in df.columns:
        key = re.sub(r"[\s_]+", "_", str(c).strip().lower())
        norm_map[key] = c

    for cand in candidates:
        k = re.sub(r"[\s_]+", "_", cand.strip().lower())
        if k in norm_map:
            return norm_map[k]
    return None

def load_cadop_map(cadop_csv: str, logger: logging.Logger) -> pd.DataFrame:
    df = pd.read_csv(cadop_csv, sep=";", dtype=str, engine="python", encoding="utf-8", on_bad_lines="skip")

    # No seu arquivo: REGISTRO_OPERADORA, CNPJ, Razao_Social
    col_reg = pick_column(df, ["REGISTRO_OPERADORA", "REGISTRO_OPERADORA ", "Registro_ANS", "Registro ANS", "registro_ans"])
    col_cnpj = pick_column(df, ["CNPJ"])
    col_razao = pick_column(df, ["Razao_Social", "Razão Social", "Razao Social", "RAZAO_SOCIAL", "razao_social"])

    logger.info(f"CADOP columns detected -> reg='{col_reg}', cnpj='{col_cnpj}', razao='{col_razao}'")

    if not (col_reg and col_cnpj and col_razao):
        raise RuntimeError(
            "Não consegui localizar colunas no CADOP.\n"
            f"Colunas encontradas: {list(df.columns)[:80]}"
        )

    out = pd.DataFrame({
        "REG_ANS": df[col_reg].astype(str).str.strip(),
        "CNPJ": df[col_cnpj].map(norm_cnpj),
        "RazaoSocial": df[col_razao].astype(str).str.strip(),
    })

    out = out[(out["REG_ANS"] != "") & (out["CNPJ"] != "")]
    out = out.drop_duplicates(subset=["REG_ANS"], keep="last")

    logger.info(f"CADOP carregado: {len(out)} registros (map REG_ANS->CNPJ/RazaoSocial)")
    return out


# =========================
# Leitura e filtro
# =========================

def iter_filtered_rows(file_path: str, negatives_mode: str, logger: logging.Logger) -> Iterable[pd.DataFrame]:
    reader = pd.read_csv(
        file_path,
        sep=";",
        dtype=str,
        engine="python",
        encoding="utf-8",
        chunksize=CHUNKSIZE,
        on_bad_lines="skip",
    )

    y_file, q_file = derive_year_quarter_from_filename(file_path)

    for chunk in reader:
        required = ["DATA", "REG_ANS", "CD_CONTA_CONTABIL", "DESCRICAO", "VL_SALDO_INICIAL", "VL_SALDO_FINAL"]
        missing = [c for c in required if c not in chunk.columns]
        if missing:
            logger.warning(f"{file_path}: faltam colunas {missing} — chunk ignorado.")
            continue

        acc = chunk["CD_CONTA_CONTABIL"].astype(str).str.strip()
        mask_acc = acc.str.startswith(ACCOUNT_PREFIXES)

        desc = chunk["DESCRICAO"].astype(str)
        mask_desc = desc.str.contains(DESC_KEYWORDS_RE, na=False)

        filtered = chunk[mask_acc | mask_desc].copy()
        if filtered.empty:
            continue

        dt, ano, tri = derive_year_quarter_from_date_col(filtered)
        filtered["__dt"] = dt
        filtered["Ano"] = ano
        filtered["Trimestre"] = tri

        bad_dt = filtered["__dt"].isna()
        if bad_dt.any() and y_file and q_file:
            filtered.loc[bad_dt, "Ano"] = y_file
            filtered.loc[bad_dt, "Trimestre"] = q_file

        v_final = parse_money_br(filtered["VL_SALDO_FINAL"])
        value = v_final

        if negatives_mode == "zero":
            value = value.where(value >= 0, 0)

        filtered["ValorDespesas"] = value
        yield filtered


# =========================
# Consolidação
# =========================

def consolidate(files: List[str], out_dir: str, negatives_mode: str) -> Tuple[str, str]:
    logger = setup_logger(out_dir)
    ensure_dir(out_dir)
    ensure_dir(os.path.join(out_dir, "issues"))
    ensure_dir(os.path.join(out_dir, "cache"))

    logger.info("=== 1.3 Consolidação ANS: START ===")
    logger.info(f"Arquivos de entrada: {len(files)}")
    for f in files:
        logger.info(f"  - {f}")

    cadop_path = download_cadop(os.path.join(out_dir, "cache"), logger)
    cadop = load_cadop_map(cadop_path, logger)

    agg: Dict[Tuple[str, str, int, int], float] = {}
    issues_cnpj_razao: Dict[str, Dict[str, int]] = {}
    issues_valores_rows: List[Dict] = []
    issues_datas_rows: List[Dict] = []

    for file_path in files:
        logger.info(f"Processando (chunks): {file_path}")
        for filtered in iter_filtered_rows(file_path, negatives_mode, logger):
            filtered["REG_ANS"] = filtered["REG_ANS"].astype(str).str.strip()
            merged = filtered.merge(cadop, how="left", on="REG_ANS")

            no_map = merged["CNPJ"].isna() | (merged["CNPJ"].astype(str).str.strip() == "")
            if no_map.any():
                for _, r in merged.loc[no_map, ["REG_ANS", "DATA", "DESCRICAO"]].head(200).iterrows():
                    issues_datas_rows.append({
                        "tipo": "SEM_CADOP",
                        "arquivo": os.path.basename(file_path),
                        "REG_ANS": str(r["REG_ANS"]),
                        "DATA": str(r["DATA"]),
                        "DESCRICAO": str(r["DESCRICAO"])[:200],
                    })
                merged = merged.loc[~no_map].copy()

            if merged.empty:
                continue

            merged["Ano"] = pd.to_numeric(merged["Ano"], errors="coerce").astype("Int64")
            merged["Trimestre"] = pd.to_numeric(merged["Trimestre"], errors="coerce").astype("Int64")

            bad_yq = merged["Ano"].isna() | merged["Trimestre"].isna()
            if bad_yq.any():
                for _, r in merged.loc[bad_yq, ["CNPJ", "RazaoSocial", "DATA"]].head(200).iterrows():
                    issues_datas_rows.append({
                        "tipo": "DATA_INDETERMINADA",
                        "arquivo": os.path.basename(file_path),
                        "CNPJ": str(r["CNPJ"]),
                        "RazaoSocial": str(r["RazaoSocial"])[:200],
                        "DATA": str(r["DATA"]),
                    })
                merged = merged.loc[~bad_yq].copy()

            if merged.empty:
                continue

            # CNPJ x Razão
            for cnpj, razao in zip(merged["CNPJ"].astype(str), merged["RazaoSocial"].astype(str)):
                cnpj = norm_cnpj(cnpj)
                razao = razao.strip()
                if not cnpj:
                    continue
                issues_cnpj_razao.setdefault(cnpj, {})
                issues_cnpj_razao[cnpj][razao] = issues_cnpj_razao[cnpj].get(razao, 0) + 1

            # Valores 0/neg (amostras)
            raw_final = parse_money_br(merged["VL_SALDO_FINAL"])
            used = merged["ValorDespesas"].fillna(0).astype(float)
            is_zero = used == 0.0
            is_neg_raw = raw_final.fillna(0).astype(float) < 0.0

            sample = merged.loc[(is_zero | is_neg_raw), ["CNPJ", "RazaoSocial", "DATA", "CD_CONTA_CONTABIL", "DESCRICAO", "VL_SALDO_FINAL", "ValorDespesas"]].head(200)
            for idx, r in sample.iterrows():
                issues_valores_rows.append({
                    "arquivo": os.path.basename(file_path),
                    "CNPJ": norm_cnpj(r["CNPJ"]),
                    "RazaoSocial": str(r["RazaoSocial"])[:200],
                    "DATA": str(r["DATA"]),
                    "CD_CONTA_CONTABIL": str(r["CD_CONTA_CONTABIL"]),
                    "DESCRICAO": str(r["DESCRICAO"])[:200],
                    "VL_SALDO_FINAL_raw": str(r["VL_SALDO_FINAL"]),
                    "ValorDespesas_usado": float(r["ValorDespesas"]) if pd.notna(r["ValorDespesas"]) else None,
                    "flag": "ZERO" if float(r["ValorDespesas"]) == 0 else ("NEGATIVO_RAW" if (pd.notna(raw_final.loc[idx]) and float(raw_final.loc[idx]) < 0) else "OK"),
                })

            # Soma por chave
            for _, r in merged.iterrows():
                cnpj = norm_cnpj(r["CNPJ"])
                razao = str(r["RazaoSocial"]).strip()
                ano = int(r["Ano"])
                tri = int(r["Trimestre"])
                val = float(r["ValorDespesas"]) if pd.notna(r["ValorDespesas"]) else 0.0
                key = (cnpj, razao, ano, tri)
                agg[key] = agg.get(key, 0.0) + val

    logger.info(f"Agregações acumuladas: {len(agg)}")

    # Razão canônica por CNPJ
    canonical_razao: Dict[str, str] = {}
    cnpj_razao_rows = []
    for cnpj, razoes in issues_cnpj_razao.items():
        chosen = sorted(razoes.items(), key=lambda x: (-x[1], x[0]))[0][0]
        canonical_razao[cnpj] = chosen
        if len(razoes) > 1:
            cnpj_razao_rows.append({
                "CNPJ": cnpj,
                "Razoes_encontradas": " | ".join([f"{rz} (n={n})" for rz, n in sorted(razoes.items(), key=lambda x: -x[1])]),
                "Razao_canônica": chosen,
            })

    issues_cnpj_path = os.path.join(out_dir, "issues", "issues_cnpj_razao.csv")
    if cnpj_razao_rows:
        pd.DataFrame(cnpj_razao_rows).to_csv(issues_cnpj_path, index=False, encoding="utf-8")
        logger.info(f"Inconsistência CNPJ/RazaoSocial registrada: {issues_cnpj_path}")
    else:
        logger.info("Nenhuma inconsistência CNPJ/RazaoSocial relevante detectada.")

    # Reagrupar por Razão canônica
    final_agg: Dict[Tuple[str, str, int, int], float] = {}
    for (cnpj, razao, ano, tri), val in agg.items():
        rz = canonical_razao.get(cnpj, razao)
        key = (cnpj, rz, ano, tri)
        final_agg[key] = final_agg.get(key, 0.0) + val

    out_csv_path = os.path.join(out_dir, FINAL_CSV_NAME)
    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OUT_COLS)
        for (cnpj, razao, ano, tri), val in sorted(final_agg.items(), key=lambda x: (x[0][3], x[0][2], x[0][0])):
            w.writerow([cnpj, razao, int(tri), int(ano), f"{val:.2f}"])

    logger.info(f"CSV final gerado: {out_csv_path}")

    # Issues valores/datas
    issues_val_path = os.path.join(out_dir, "issues", "issues_valores.csv")
    if issues_valores_rows:
        pd.DataFrame(issues_valores_rows).to_csv(issues_val_path, index=False, encoding="utf-8")
        logger.info(f"Inconsistências de valores registradas: {issues_val_path}")

    issues_dt_path = os.path.join(out_dir, "issues", "issues_datas.csv")
    if issues_datas_rows:
        pd.DataFrame(issues_datas_rows).to_csv(issues_dt_path, index=False, encoding="utf-8")
        logger.info(f"Inconsistências de datas/mapeamento registradas: {issues_dt_path}")

    # Documentação
    readme_path = os.path.join(out_dir, "issues", "README_tratamento_inconsistencias.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            "Tratamento de inconsistências (1.3)\n"
            "===============================\n\n"
            "1) CNPJ duplicado com Razão Social diferente:\n"
            "- Consolidação por CNPJ (mantendo 1 RazaoSocial canônica).\n"
            "- Escolha da canônica: razão mais frequente no conjunto.\n"
            "- Registro: issues_cnpj_razao.csv\n\n"
            "2) Valores zerados ou negativos:\n"
            "- Zero: mantido.\n"
            "- Negativos: marcados como suspeitos.\n"
            f"- Modo de negativos: {negatives_mode}\n"
            "- Se negatives_mode='zero': negativos corrigidos para 0 na soma.\n"
            "- Se negatives_mode='keep': negativos mantidos na soma.\n"
            "- Registro: issues_valores.csv\n\n"
            "3) Datas/trimestres inconsistentes:\n"
            "- Parse robusto de DATA (infer + dayfirst).\n"
            "- Se parse falhar: tenta derivar Ano/Trimestre do nome do arquivo (1T2025 etc.).\n"
            "- Registro: issues_datas.csv\n"
        )
    logger.info(f"Documentação escrita: {readme_path}")

    # ZIP final
    out_zip_path = os.path.join(out_dir, FINAL_ZIP_NAME)
    with zipfile.ZipFile(out_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out_csv_path, arcname=FINAL_CSV_NAME)

    logger.info(f"ZIP final gerado: {out_zip_path}")
    logger.info("=== 1.3 Consolidação ANS: FINISH ===")

    return out_csv_path, out_zip_path


# =========================
# CLI
# =========================

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="ANS 1.3 – Consolidar despesas eventos/sinistros (3 trimestres). v2")
    p.add_argument("--in", dest="in_files", nargs="+", required=True,
                   help="Lista de CSVs (ex: 1T2025.csv 2T2025.csv 3T2025.csv)")
    p.add_argument("--out", default="out_1_3", help="Diretório de saída (default: out_1_3)")
    p.add_argument("--negatives", choices=["zero", "keep"], default="zero",
                   help="Tratamento de negativos: zero (corrige) ou keep (mantém). Default=zero")
    args = p.parse_args()
    consolidate(args.in_files, args.out, args.negatives)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
