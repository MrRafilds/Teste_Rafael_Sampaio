from api.ans_client import ANSClient

def main():
    base = "https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/"
    client = ANSClient(base)

    files = client.download_and_extract_quarter_zips(3)

    print("ZIPs baixados:")
    for f in files:
        print("-", f)

if __name__ == "__main__":
    main()