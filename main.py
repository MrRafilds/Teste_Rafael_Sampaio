from api.ans_client import ANSClient

def main():
    base = "https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/"
    client = ANSClient(base)

    years = client.list_year_urls()
    print("Total de anos encontrados:", len(years))
    print("Últimos 3 anos:", years[-3:])

if __name__ == "__main__":
    main()
