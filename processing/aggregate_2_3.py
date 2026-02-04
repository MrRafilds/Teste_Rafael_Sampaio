#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TESTE 2.3 – Agregação com Múltiplas Estratégias
==============================================

Entrada:
--------
CSV enriquecido (fase 2.2) com colunas:
  CNPJ, RazaoSocial, UF, Trimestre, Ano, ValorDespesas

Saída:
------
- despesas_agregadas.csv
- Teste_Rafael_Sampaio.zip (contendo o CSV)

Agregações:
-----------
Por RazaoSocial + UF:
- ValorTotalDespesas
- MediaTrimestralDespesas
- DesvioPadraoDespesas

Ordenação:
----------
- Por ValorTotalDespesas (decrescente)

Trade-off:
----------
Ordenação em memória após agregação (volume reduzido).
"""

import os
import csv
import zipfile
from collections import defaultdict
from statistics import mean, pstdev


# =========================
# Config
# =========================

OUT_CSV = "despesas_agregadas.csv"
OUT_ZIP = "Teste_Rafael_Sampaio.zip"


# =========================
# Execução
# =========================

def aggregate(input_csv: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    # 1) Soma por RazaoSocial + UF + Ano + Trimestre
    trimestral = defaultdict(float)

    with open(input_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                razao = (r.get("RazaoSocial") or "").strip()
                uf = (r.get("UF") or "").strip()
                ano = int(r["Ano"])
                tri = int(r["Trimestre"])
                valor = float(r["ValorDespesas"])

                if not razao or not uf:
                    continue
                if valor <= 0:
                    continue

            except Exception:
                continue

            key = (razao, uf, ano, tri)
            trimestral[key] += valor

    # 2) Agrupa por RazaoSocial + UF
    por_operadora = defaultdict(list)

    for (razao, uf, _, _), valor_tri in trimestral.items():
        por_operadora[(razao, uf)].append(valor_tri)

    # 3) Calcula métricas finais
    resultado = []

    for (razao, uf), valores in por_operadora.items():
        total = sum(valores)
        media = mean(valores)
        desvio = pstdev(valores) if len(valores) > 1 else 0.0

        resultado.append({
            "RazaoSocial": razao,
            "UF": uf,
            "ValorTotalDespesas": round(total, 2),
            "MediaTrimestralDespesas": round(media, 2),
            "DesvioPadraoDespesas": round(desvio, 2),
        })

    # 4) Ordenação (maior -> menor)
    resultado.sort(key=lambda x: x["ValorTotalDespesas"], reverse=True)

    # 5) Salvar CSV
    out_csv_path = os.path.join(out_dir, OUT_CSV)
    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "RazaoSocial",
                "UF",
                "ValorTotalDespesas",
                "MediaTrimestralDespesas",
                "DesvioPadraoDespesas",
            ],
        )
        writer.writeheader()
        writer.writerows(resultado)

    # 6) Compactar
    out_zip_path = os.path.join(out_dir, OUT_ZIP)
    with zipfile.ZipFile(out_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out_csv_path, arcname=OUT_CSV)

    print("[INFO] Agregação concluída")
    print(f"[INFO] CSV: {out_csv_path}")
    print(f"[INFO] ZIP: {out_zip_path}")


# =========================
# CLI
# =========================

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Teste 2.3 – Agregação de despesas")
    p.add_argument("--in", dest="input_csv", required=True, help="CSV enriquecido (fase 2.2)")
    p.add_argument("--out", default="out_2_3", help="Diretório de saída")
    args = p.parse_args()

    aggregate(args.input_csv, args.out)
