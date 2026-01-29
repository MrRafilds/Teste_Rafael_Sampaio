
from api.ans_client import ANSClient

def main():
    url = "https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/"
    client = ANSClient(url)
    client.get_page()

if __name__ == "__main__":
    main()
