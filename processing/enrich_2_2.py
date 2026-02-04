#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TESTE 2.2 – Enriquecimento de Dados com Tratamento de Falhas
============================================================

Entrada:
--------
CSV consolidado (1.3 / 2.1):
  CNPJ,RazaoSocial,Trimestre,Ano,ValorDespesas

Fonte externa:
--------------
Cadastro de Operadoras Ativas (ANS – CADOP)
https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv

Saída:
------
CSV enriquecido com:
  RegistroANS, Modalidade, UF, CadastroStatus

E relatórios de inconsistência:
- issues/issues_sem_match_cadastro.csv
- issues/issues_cadastro_duplicado.csv

Join:
-----
LEFT JOIN (consolidado -> cadastro), por CNPJ

Trade-offs:
-----------
- Cadastro (CADOP) é carregado em memória e convertido em dict por CNPJ:
  rápido no join e adequado ao tamanho esperado do cadastro.
- Consolidação é processada linha-a-linha (csv.DictReader), evitando uso excessivo de RAM.
"""

from __future__ import annotations

import os
import csv
import re
import requests
from collections import defaultdict
from typing import Dict, List, Tuple, Any


CADOP_URL = (
    "https://dadosabertos.ans.gov.br/FTP/PDA/"
    "operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv"
)

OUT_ENRICHED_NAME = "consolidado_enriquecido.csv"


# =========================
# Utils
# =========================

def norm_cnpj(cnpj: str) -> str:
    return re.sub(r"\D+", "", str(cnpj or ""))

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def pick_registro_ans(row: Dict[str, str]) -> str:
    """
    CADOP pode variar o nome da coluna. Aqui tentamos variações comuns.
    """
    return (
        (row.get("REGISTRO_OPERADORA") or "")
        or (row.get("Registro_ANS") or "")
        or (row.get("REGISTRO_ANS") or "")
        or (row.get("registro_ans") or "")
    ).strip()


# =========================
# Load CADOP (cache)
# =========================

def download_cadop_if_needed(cache_dir: str) -> str:
    ensure_dir(cache_dir)
    cadop_path = os.path.join(cache_dir, "Relatorio_cadop.csv")

    if os.path.exists(cadop_path) and os.path.getsize(cadop_path) > 0:
        return cadop_path

    r = requests.get(CADOP_URL, timeout=120)
    r.raise_for_status()
    with open(cadop_path, "wb") as f:
        f.write(r.content)

    return cadop_path


def load_cadop_rows(cache_dir: str) -> List[Dict[str, str]]:
    """
    Carrega o CSV do CADOP e devolve uma lista mínima de colunas necessárias.
    """
    cadop_path = download_cadop_if_needed(cache_dir)

    rows: List[Dict[str, str]] = []
    # errors="replace" evita crash se vier algum caractere fora do esperado.
    with open(cadop_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            cnpj = norm_cnpj(r.get("CNPJ"))
            if not cnpj:
                continue

            rows.append({
                "CNPJ": cnpj,
                "RegistroANS": pick_registro_ans(r),
                "Modalidade": (r.get("Modalidade") or "").strip(),
                "UF": (r.get("UF") or "").strip(),
            })

    return rows


# =========================
# Canonical cadastro per CNPJ
# =========================

def canonicalize_cadastro(rows: List[Dict[str, str]]) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, Any]]]:
    """
    Resolve duplicidades do CADOP por CNPJ.
    Estratégia: escolhe o trio (RegistroANS, Modalidade, UF) mais frequente.
    """
    by_cnpj: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_cnpj[r["CNPJ"]].append(r)

    cadastro: Dict[str, Dict[str, str]] = {}
    duplicates_report: List[Dict[str, Any]] = []

    for cnpj, items in by_cnpj.items():
        if len(items) == 1:
            cadastro[cnpj] = items[0]
            continue

        counter: Dict[Tuple[str, str, str], int] = defaultdict(int)
        for i in items:
            key = (i["RegistroANS"], i["Modalidade"], i["UF"])
            counter[key] += 1

        chosen = max(counter, key=counter.get)
        cadastro[cnpj] = {
            "CNPJ": cnpj,
            "RegistroANS": chosen[0],
            "Modalidade": chosen[1],
            "UF": chosen[2],
        }

        # Salva "bonitinho" para CSV (strings, não listas Python cruas)
        opcoes_str = " | ".join([f"{a},{m},{u} (n={n})" for (a, m, u), n in sorted(counter.items(), key=lambda x: -x[1])])
        escolhido_str = f"{chosen[0]},{chosen[1]},{chosen[2]}"

        duplicates_report.append({
            "CNPJ": cnpj,
            "Opcoes": opcoes_str,
            "Escolhido": escolhido_str,
        })

    return cadastro, duplicates_report


# =========================
# Enrichment
# =========================

def enrich(consolidated_csv: str, out_dir: str) -> str:
    ensure_dir(out_dir)
    issues_dir = os.path.join(out_dir, "issues")
    cache_dir = os.path.join(out_dir, "cache")
    ensure_dir(issues_dir)
    ensure_dir(cache_dir)

    cadop_rows = load_cadop_rows(cache_dir)
    cadastro, duplicates = canonicalize_cadastro(cadop_rows)

    out_csv = os.path.join(out_dir, OUT_ENRICHED_NAME)

    sem_match_rows: List[Dict[str, str]] = []

    with open(consolidated_csv, encoding="utf-8", newline="") as fin, \
         open(out_csv, "w", newline="", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            raise RuntimeError("CSV de entrada não possui cabeçalho (fieldnames).")

        # mantém colunas originais + adiciona novas
        fieldnames = list(reader.fieldnames) + ["RegistroANS", "Modalidade", "UF", "CadastroStatus"]
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            cnpj = norm_cnpj(row.get("CNPJ", ""))
            cad = cadastro.get(cnpj)

            if cad:
                row["RegistroANS"] = cad.get("RegistroANS", "")
                row["Modalidade"] = cad.get("Modalidade", "")
                row["UF"] = cad.get("UF", "")
                row["CadastroStatus"] = "OK"
            else:
                row["RegistroANS"] = ""
                row["Modalidade"] = ""
                row["UF"] = ""
                row["CadastroStatus"] = "SEM_MATCH_CADOP"
                sem_match_rows.append({"CNPJ": cnpj})

            writer.writerow(row)

    # issues: sem match
    if sem_match_rows:
        issues_sem_match = os.path.join(issues_dir, "issues_sem_match_cadastro.csv")
        with open(issues_sem_match, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["CNPJ"])
            w.writeheader()
            w.writerows(sem_match_rows)

    # issues: duplicidades
    if duplicates:
        issues_dup = os.path.join(issues_dir, "issues_cadastro_duplicado.csv")
        with open(issues_dup, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["CNPJ", "Opcoes", "Escolhido"])
            w.writeheader()
            w.writerows(duplicates)

    # README (gerado automaticamente)
    readme_path = os.path.join(out_dir, "README_enriquecimento.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            "# Enriquecimento de Dados – Teste 2.2\n\n"
            "## O que foi feito\n"
            "- Fonte: Cadastro de Operadoras Ativas (ANS – CADOP)\n"
            "- Join: **LEFT JOIN** do consolidado com o cadastro usando **CNPJ**\n"
            "- Colunas adicionadas: `RegistroANS`, `Modalidade`, `UF`, `CadastroStatus`\n\n"
            "## Tratamento de falhas / inconsistências\n"
            "- Registros sem match no cadastro: **mantidos** e marcados como `SEM_MATCH_CADOP`\n"
            "- Duplicidades no cadastro (mesmo CNPJ com dados diferentes): resolvidas por regra determinística\n"
            "  (escolhe a combinação mais frequente de `RegistroANS`, `Modalidade`, `UF`).\n\n"
            "## Trade-off técnico\n"
            "- Cadastro (CADOP) é carregado em memória (tamanho esperado pequeno/moderado) para join rápido.\n"
            "- CSV consolidado é processado linha-a-linha para reduzir uso de memória.\n"
        )

    print("[INFO] Enriquecimento concluído")
    print(f"[INFO] CSV final: {out_csv}")
    return out_csv


# =========================
# CLI
# =========================

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Teste 2.2 – Enriquecimento de dados ANS (CADOP).")
    p.add_argument("--in", dest="input_csv", required=True, help="CSV consolidado (1.3/2.1)")
    p.add_argument("--out", default="out_2_2", help="Diretório de saída (default: out_2_2)")
    args = p.parse_args()

    enrich(args.input_csv, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
