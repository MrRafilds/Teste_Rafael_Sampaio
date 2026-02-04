 #!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TESTE 2.1 – Validação de Dados (CSV consolidado do 1.3)
=======================================================

Entrada:
--------
CSV do 1.3 com colunas:
  CNPJ,RazaoSocial,Trimestre,Ano,ValorDespesas

Saídas:
-------
- validated/valid_rows.csv
- validated/invalid_rows.csv      (inclui coluna ValidationErrors)
- validated/summary.json
- README_validacao.md             (documenta estratégia para CNPJ inválido)

Validações:
-----------
1) CNPJ válido:
   - aceita com ou sem máscara, mas normaliza para 14 dígitos.
   - valida dígitos verificadores (DV).
2) ValorDespesas:
   - deve ser numérico
   - deve ser > 0 (positivo)
3) RazaoSocial:
   - não pode ser vazia

Trade-off técnico (CNPJ inválido):
----------------------------------
Estratégia escolhida: "QUARANTINE" (Quarentena / Separar e não usar)
- Regra: registros com CNPJ inválido NÃO entram em valid_rows.csv.
- Eles vão para invalid_rows.csv com o motivo detalhado.

Prós:
- Evita contaminar análises agregadas por chave errada (CNPJ é chave primária de negócio).
- Mantém rastreabilidade: nada é perdido, apenas separado para investigação.
- Compatível com pipelines de qualidade (data quality gates).

Contras:
- Pode reduzir cobertura (ex.: registros com erro de formatação real, mas CNPJ “recuperável”).
- Exige etapa posterior de correção/enriquecimento.

Alternativas consideradas:
- "DROP" (descartar): simples, mas perde rastreabilidade.
- "FIX_IF_POSSIBLE" (corrigir se possível): útil para máscaras/zeros à esquerda, mas arriscado para DV inválido real.
- "MARK_AND_KEEP" (marcar e manter): preserva volume, mas polui métricas e joins por CNPJ.

Obs:
----
Este script normaliza CNPJ removendo caracteres não numéricos.
Se o DV continuar inválido, é considerado inválido.
"""

from __future__ import annotations

import os
import csv
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple


# =========================
# CNPJ: validação DV
# =========================

def only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def calc_cnpj_dv(base12: str) -> str:
    """
    Calcula os 2 dígitos verificadores (DV) do CNPJ a partir dos 12 primeiros dígitos.
    """
    assert len(base12) == 12 and base12.isdigit()

    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def dv_for(num: str, weights: List[int]) -> int:
        total = 0
        for digit, w in zip(num, weights):
            total += int(digit) * w
        mod = total % 11
        return 0 if mod < 2 else (11 - mod)

    d1 = dv_for(base12, weights1)
    d2 = dv_for(base12 + str(d1), weights2)
    return f"{d1}{d2}"

def is_valid_cnpj(cnpj_raw: str) -> Tuple[bool, str]:
    """
    Retorna (is_valid, normalized_14digits_or_empty)
    """
    cnpj = only_digits(cnpj_raw)
    if len(cnpj) != 14:
        return False, cnpj

    # rejeita sequências iguais (muito comuns em lixo)
    if cnpj == cnpj[0] * 14:
        return False, cnpj

    base = cnpj[:12]
    dv = cnpj[12:]
    expected = calc_cnpj_dv(base)
    return (dv == expected), cnpj


# =========================
# ValorDespesas
# =========================

def parse_float(value: str) -> Tuple[bool, float]:
    """
    Parse robusto:
    - aceita "1234.56"
    - aceita "1.234,56" (BR) -> converte
    """
    if value is None:
        return False, 0.0

    s = str(value).strip()
    if s == "":
        return False, 0.0

    # Heurística BR: se tem vírgula e ponto, remove pontos e troca vírgula por ponto
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # "123,45" -> "123.45"
        s = s.replace(",", ".")

    try:
        return True, float(s)
    except Exception:
        return False, 0.0


# =========================
# Estratégia de CNPJ inválido
# =========================

CNPJ_INVALID_STRATEGY = "QUARANTINE"  # escolha implementada


def validate_row(row: Dict[str, str]) -> Tuple[bool, Dict[str, str], List[str]]:
    """
    Valida 1 linha do CSV consolidado.
    Retorna:
      - ok (bool)
      - normalized_row (dict)
      - errors (list[str])
    """
    errors: List[str] = []

    cnpj_ok, cnpj_norm = is_valid_cnpj(row.get("CNPJ", ""))
    if not cnpj_ok:
        errors.append("CNPJ_INVALIDO")

    razao = (row.get("RazaoSocial") or "").strip()
    if not razao:
        errors.append("RAZAO_SOCIAL_VAZIA")

    ok_num, val = parse_float(row.get("ValorDespesas", ""))
    if not ok_num:
        errors.append("VALOR_NAO_NUMERICO")
    else:
        if val <= 0:
            errors.append("VALOR_NAO_POSITIVO")

    # Normaliza (mesmo que seja inválido, para rastreio)
    normalized = dict(row)
    normalized["CNPJ"] = cnpj_norm
    normalized["RazaoSocial"] = razao
    normalized["ValorDespesas"] = f"{val:.2f}" if ok_num else row.get("ValorDespesas", "")

    return (len(errors) == 0), normalized, errors


# =========================
# Execução
# =========================

def write_readme(out_dir: str, summary: Dict) -> None:
    """
    Gera README com decisão e prós/contras.
    """
    path = os.path.join(out_dir, "README_validacao.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Teste 2.1 – Validação do CSV Consolidado (1.3)\n\n")
        f.write("## Validações implementadas\n")
        f.write("- CNPJ válido (formato e dígitos verificadores)\n")
        f.write("- ValorDespesas numérico e positivo (> 0)\n")
        f.write("- RazaoSocial não vazia\n\n")

        f.write("## Estratégia escolhida para CNPJ inválido\n")
        f.write(f"**Estratégia: {CNPJ_INVALID_STRATEGY} (Quarentena)**\n\n")
        f.write("### Como funciona\n")
        f.write("- Registros com CNPJ inválido **não entram** no `valid_rows.csv`.\n")
        f.write("- Esses registros vão para `invalid_rows.csv` com `ValidationErrors`.\n\n")

        f.write("### Prós\n")
        f.write("- Evita contaminar análises agregadas e joins por chave legal inválida.\n")
        f.write("- Mantém rastreabilidade (nenhuma linha é perdida; apenas segregada).\n")
        f.write("- Facilita auditoria e processos de correção posteriores.\n\n")

        f.write("### Contras\n")
        f.write("- Pode reduzir cobertura se existirem muitos CNPJs com erro de digitação.\n")
        f.write("- Requer etapa posterior de saneamento/enriquecimento.\n\n")

        f.write("### Alternativas consideradas\n")
        f.write("- **DROP**: descarta linhas inválidas (simples, mas perde rastreabilidade).\n")
        f.write("- **MARK_AND_KEEP**: mantém inválidos com flag (preserva volume, mas polui métricas).\n")
        f.write("- **FIX_IF_POSSIBLE**: corrige quando for só máscara/zeros; arriscado quando DV falha.\n\n")

        f.write("## Resumo de execução\n")
        f.write("```json\n")
        f.write(json.dumps(summary, ensure_ascii=False, indent=2))
        f.write("\n```\n")


def run(in_csv: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    validated_dir = os.path.join(out_dir, "validated")
    os.makedirs(validated_dir, exist_ok=True)

    valid_path = os.path.join(validated_dir, "valid_rows.csv")
    invalid_path = os.path.join(validated_dir, "invalid_rows.csv")
    summary_path = os.path.join(validated_dir, "summary.json")

    total = 0
    valid = 0
    invalid = 0

    # contadores de erros
    error_counts: Dict[str, int] = {}

    with open(in_csv, "r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        in_cols = reader.fieldnames or []

        # Valid CSV writer
        with open(valid_path, "w", encoding="utf-8", newline="") as f_ok, \
             open(invalid_path, "w", encoding="utf-8", newline="") as f_bad:

            ok_writer = csv.DictWriter(f_ok, fieldnames=in_cols)
            bad_writer = csv.DictWriter(f_bad, fieldnames=in_cols + ["ValidationErrors"])

            ok_writer.writeheader()
            bad_writer.writeheader()

            for row in reader:
                total += 1
                is_ok, norm_row, errs = validate_row(row)

                if is_ok:
                    valid += 1
                    ok_writer.writerow(norm_row)
                else:
                    invalid += 1
                    for e in errs:
                        error_counts[e] = error_counts.get(e, 0) + 1

                    # Estratégia QUARANTINE: inválidos ficam no arquivo invalid_rows.csv
                    bad_row = dict(norm_row)
                    bad_row["ValidationErrors"] = "|".join(errs)
                    bad_writer.writerow(bad_row)

    summary = {
        "input_csv": os.path.abspath(in_csv),
        "output_dir": os.path.abspath(out_dir),
        "strategy_cnpj_invalid": CNPJ_INVALID_STRATEGY,
        "total_rows": total,
        "valid_rows": valid,
        "invalid_rows": invalid,
        "error_counts": error_counts,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "outputs": {
            "valid_rows_csv": os.path.abspath(valid_path),
            "invalid_rows_csv": os.path.abspath(invalid_path),
            "summary_json": os.path.abspath(summary_path),
            "readme": os.path.abspath(os.path.join(out_dir, "README_validacao.md")),
        }
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    write_readme(out_dir, summary)

    print("[INFO] Validação finalizada")
    print(f"[INFO] Total: {total} | Válidas: {valid} | Inválidas: {invalid}")
    print(f"[INFO] Saídas em: {os.path.abspath(out_dir)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Teste 2.1 – Validar CSV consolidado (1.3).")
    ap.add_argument("--in", dest="in_csv", required=True, help="CSV consolidado do 1.3 (consolidado_despesas.csv)")
    ap.add_argument("--out", default="out_2_1", help="Diretório de saída (default: out_2_1)")
    args = ap.parse_args()

    run(args.in_csv, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
