import os
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

class LinkParser(HTMLParser):        
    """Extrai todos os href de tags <a> de 
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