import requests

class ANSClient:
    """
    Cliente responsável por acessar a API pública da ANS.
    """

    def __init__(self, url):
        # URL base da API da ANS
        self.url = url

    def get_page(self):
        """
        Faz uma requisição HTTP GET e imprime parte do conteúdo retornado.
        """
        response = requests.get(self.url)

        # Exibe o status da resposta (200 = sucesso)
        print(response.status_code)

        # Exibe apenas parte do HTML para inspeção inicial
        print(response.text[:1000])
