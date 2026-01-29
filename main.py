from api.ans_client import ANSClient

def main():
    base = "https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/"
    client = ANSClient(base)

    last3 = client.get_last_quarter_zip_urls(3)
    print("Últimos 3 arquivos ZIP disponíveis:")
    for u in last3:
        print(" -", u)
        
if __name__ == "__main__":
    main()
