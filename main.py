"""
Ponto de entrada do projeto.

Executa:
- Teste 1 (1.1 → 1.3): Download + extração + consolidação ANS
- Teste 2 (2.1 → 2.3): Validação + enriquecimento (CADOP) + agregação + ZIP final
"""

from api.ans_client import ANSClient
from processing.consolidate_1_3 import consolidate

from processing.validate_2_1 import run as run_validate_2_1
from processing.enrich_2_2 import enrich as run_enrich_2_2
from processing.aggregate_2_3 import aggregate as run_aggregate_2_3

import os
import glob


def run_test_1() -> str:
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    base = "https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/"
    client = ANSClient(base)

    # =========================
    # 1.1 — Download dos dados
    # =========================
    zip_files = client.download_and_extract_quarter_zips(3)

    print("\n[1.1] ZIPs baixados:")
    for z in zip_files:
        print(" -", z)

    # =========================
    # 1.2 — Normalização (MVP)
    # =========================
    extracted_dir = "data/extracted"
    csv_files = glob.glob(os.path.join(extracted_dir, "**", "*.csv"), recursive=True)
    csv_files = sorted(csv_files)

    if not csv_files:
        raise RuntimeError("Nenhum CSV encontrado em data/extracted. Verifique se a extração funcionou.")

    print(f"\n[1.2] CSVs encontrados ({len(csv_files)}):")
    for f in csv_files:
        print(" -", f)

    # =========================
    # 1.3 — Consolidação
    # =========================
    out_dir = "output/teste_1"
    out_csv, out_zip = consolidate(csv_files, out_dir=out_dir, negatives_mode="zero")

    print("\n[1.3] Saídas geradas:")
    print(" - CSV:", out_csv)
    print(" - ZIP:", out_zip)

    return out_csv


def run_test_2(consolidated_csv: str) -> None:
    """
    Pipeline do Teste 2:
      2.1 -> usa consolidated_csv e gera valid_rows.csv
      2.2 -> enriquece valid_rows.csv e gera consolidado_enriquecido.csv
      2.3 -> agrega consolidado_enriquecido.csv e gera despesas_agregadas.csv + zip final
    """
    os.makedirs("output/teste_2", exist_ok=True)

    # =========================
    # 2.1 — Validação
    # =========================
    out_2_1 = "output/teste_2/out_2_1"
    run_validate_2_1(in_csv=consolidated_csv, out_dir=out_2_1)

    valid_csv = os.path.join(out_2_1, "validated", "valid_rows.csv")
    if not os.path.exists(valid_csv):
        raise RuntimeError(f"Não encontrei o arquivo de saída do 2.1: {valid_csv}")

    # =========================
    # 2.2 — Enriquecimento (CADOP)
    # =========================
    out_2_2 = "output/teste_2/out_2_2"
    run_enrich_2_2(consolidated_csv=valid_csv, out_dir=out_2_2)

    enriched_csv = os.path.join(out_2_2, "consolidado_enriquecido.csv")
    if not os.path.exists(enriched_csv):
        raise RuntimeError(f"Não encontrei o arquivo de saída do 2.2: {enriched_csv}")

    # =========================
    # 2.3 — Agregação + ZIP final
    # =========================
    out_2_3 = "output/teste_2/out_2_3"
    run_aggregate_2_3(input_csv=enriched_csv, out_dir=out_2_3)

    print("\n[TESTE 2] Concluído.")
    print(" - Validação (2.1):", os.path.abspath(out_2_1))
    print(" - Enriquecimento (2.2):", os.path.abspath(out_2_2))
    print(" - Agregação/ZIP (2.3):", os.path.abspath(out_2_3))


def main():
    consolidated_csv = run_test_1()
    run_test_2(consolidated_csv)


if __name__ == "__main__":
    main()
