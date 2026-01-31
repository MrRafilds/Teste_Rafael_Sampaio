import os
# Manipulação de arquivos e diretórios no sistema operacional
import re
from urllib import response
# Expressões regulares para identificar padrões como anos (YYYY/) e trimestres (1T2025)
import requests
# Realiza requisições HTTP para acessar a API pública da ANS
import zipfile
# Utilizado para extrair os arquivos ZIP baixados da ANS

from html.parser import HTMLParser
# Parser padrão do Python para interpretar HTML e extrair links (<a href>)
from urllib.parse import urljoin
# Monta URLs completas a partir de links relativos encontrados no HTML

class LinkParser(HTMLParser):        
    """Parser que extrai todos os href de tags <a> de 
    uma página HTML simples (Index of Apache)."""

    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self.hrefs.append(href)
      
class ANSClient:
    """
    Cliente para navegar no diretório público da ANS (formato "Index of ...")
    e baixar arquivos de demonstrações contábeis.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/") + "/"

    def fetch_index_links(self, url: str) -> list[str]:
        #Baixa o HTML do 'Index of' e devolve uma lista de links (href) encontrados.

        r = requests.get(url, timeout=30)
        r.raise_for_status()

        parser = LinkParser()
        parser.feed(r.text)

        # Remove links de navegação comuns
        clean = []
        for href in parser.hrefs:
            if href in ("../", "/"):
                continue
            clean.append(href)

        return clean

    def list_year_urls(self) -> list[str]:
        #Retorna URLs dos anos (2007/, 2008/, ...) disponíveis na raiz.
        hrefs = self.fetch_index_links(self.base_url)

        year_urls = []
        for h in hrefs:
            if re.fullmatch(r"\d{4}/", h):
                year_urls.append(urljoin(self.base_url, h))

        return sorted(year_urls)
    
    def list_zip_files(self, year_url: str) -> list[str]:
        #Lista URLs de arquivos .zip dentro de um ano.

        hrefs = self.fetch_index_links(year_url)
        zips = [urljoin(year_url, h) for h in hrefs if h.lower().endswith(".zip")]
        
        return sorted(zips)
    
    def get_last_quarter_zip_urls(self, n: int = 3) -> list[str]:
        """
        Pega os últimos n arquivos de trimestre (ex: 1T2025.zip).
        Estratégia simples: varre anos do mais recente para trás e coleta zips que combinem padrão.
        """
        year_urls = self.list_year_urls()
        year_urls = sorted(year_urls, reverse=True)  # mais recente primeiro

        quarter_files = []
        pattern = re.compile(r".*/([1-4]T)(\d{4})\.zip$", re.IGNORECASE)

        for yurl in year_urls:
            for z in self.list_zip_files(yurl):
                if pattern.match(z):
                    quarter_files.append(z)

            if len(quarter_files) >= n:
                break

        # Ordena por ano e trimestre (ex: 3T2025 > 2T2025)
        def key(u: str):
            m = pattern.match(u)
            t = int(m.group(1)[0])  # 1..4
            y = int(m.group(2))     # ano
            return (y, t)

        quarter_files = sorted(quarter_files, key=key, reverse=True)
        return quarter_files[:n]
    
    def download_file(self, url: str, out_dir: str) -> str:
        """
        Baixa um arquivo ZIP da URL e salva no diretório informado.
        Retorna o caminho do arquivo salvo.
        """
        os.makedirs(out_dir, exist_ok=True)

        filename = url.split("/")[-1]
        out_path = os.path.join(out_dir, filename)

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

        return out_path

    def extract_zip(self, zip_path: str, extract_dir: str) -> None:
        """
        Extrai um arquivo ZIP para o diretório informado.
        """
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

    def download_and_extract_quarter_zips(self, n: int = 3):
        """
        Baixa os ZIPs dos últimos n trimestres e extrai os arquivos CSV.
        """
        zip_urls = self.get_last_quarter_zip_urls(n)

        downloaded_files = []

        for url in zip_urls:
            zip_path = self.download_file(url, out_dir="data/raw")
            downloaded_files.append(zip_path)

            self.extract_zip(zip_path, extract_dir="data/extracted")
        return downloaded_files