import os
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

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
        """Baixa o HTML do 'Index of' e devolve uma lista de links (href) encontrados."""
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
        """Retorna URLs dos anos (2007/, 2008/, ...) disponíveis na raiz."""
        hrefs = self.fetch_index_links(self.base_url)

        year_urls = []
        for h in hrefs:
            if re.fullmatch(r"\d{4}/", h):
                year_urls.append(urljoin(self.base_url, h))

        return sorted(year_urls)
    
    def list_zip_files(self, year_url: str) -> list[str]:
        """Lista URLs de arquivos .zip dentro de um ano."""

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

