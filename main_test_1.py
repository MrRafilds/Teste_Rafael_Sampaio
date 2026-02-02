from api.ans_client import ANSClient
from processing.consolidate_1_3 import consolidate

import os
import glob


def run_test_1():
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

    if not csv_files:
        raise RuntimeError("Nenhum CSV encontrado em data/extracted. Verifique se a extração funcionou.")

    print(f"\n[1.2] CSVs encontrados ({len(csv_files)}):")
    for f in csv_files[:10]:
        print(" -", f)
    if len(csv_files) > 10:
        print(" ...")

    # =========================
    # 1.3 — Consolidação
    # =========================
    
    out_dir = "output/teste_1"
    out_csv, out_zip = consolidate(csv_files, out_dir=out_dir, negatives_mode="zero")

    print("\n[1.3] Saídas geradas:")
    print(" - CSV:", out_csv)
    print(" - ZIP:", out_zip)


def main():
    run_test_1()


if __name__ == "__main__":
    main()
