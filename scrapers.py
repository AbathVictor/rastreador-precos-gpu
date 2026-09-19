# -*- coding: utf-8 -*-
"""
scrapers.py — Coletores de preço para o rastreador de GPUs.

Estratégia de extração, em ordem de preferência (Kabum e Terabyte):
1. JSON-LD (schema.org/Product) embutido na página — é o formato padrão
   que boa parte dos e-commerces usa para SEO, e tende a ser mais estável
   do que depender de classes CSS específicas do front-end.
2. Fallback: procurar o primeiro valor "R$ X.XXX,XX" no texto da página.

O Buscapé é usado de duas formas (ambas via coletar_preco_buscape /
coletar_preco_buscape_busca):
1. Página de produto (PS5): já expõe um JSON-LD (schema.org/Product, dentro
   de um bloco "@graph") com o preço agregado — `offers.lowPrice` é o menor
   preço entre as lojas que o Buscapé compara para aquele anúncio. Não
   precisa de página de busca nem de casar nome de anúncio.
2. Página de busca (GPUs): os resultados vêm embutidos como JSON dentro de
   um <script id="__NEXT_DATA__"> (cada item com "name" e "price"), então
   em vez de casar texto de card feito na marra em HTML, filtra-se essa
   lista por palavras (ver _extrair_via_busca_buscape) e usa-se o menor
   preço entre os itens que baterem. Essa é a estratégia que substituiu o
   Promotech (ver nota abaixo).

Sobre a Pichau: não está entre as lojas ativas. Ela bloqueia requisições
automatizadas com um desafio Cloudflare (HTTP 403), então nenhuma
estratégia de extração aqui resolve — não é um problema de seletor.

Sobre o Promotech: até meados de setembro/2026 alimentava a coleta das GPUs
via página de busca (card-matching em HTML). Desde então o site bloqueia
toda e qualquer requisição automatizada (inclusive a home) com um "Vercel
Security Checkpoint" (HTTP 429, header `X-Vercel-Mitigated: challenge`),
igual à Pichau — não há seletor para ajustar, o HTML real nunca chega a ser
servido. Foi substituído pela busca via Buscapé (ver item 2 acima).

Importante: nenhum scraper de e-commerce é 100% à prova de mudanças de
layout. Se uma loja redesenhar o site, a função correspondente pode parar
de encontrar o preço. Use debug=True para salvar o HTML bruto em
data/debug_html/ e inspecionar o que mudou.
"""

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

DEBUG_DIR = Path(__file__).parent / "data" / "debug_html"

# Chaves de PRODUTOS_MODELOS raspadas via coletar_preco() (JSON-LD/regex de
# uma página de produto única) dentro de coletar_todos(). "promotech_url"
# fica de fora de propósito — é só um link de referência para conferência
# manual (site bloqueado para scraping, ver nota no topo do arquivo).
# "buscape_url" e "buscape_busca_url" também ficam de fora: seguem seus
# próprios caminhos de extração (ver coletar_preco_buscape e
# coletar_preco_buscape_busca). "pichau_url" também fica de fora: o site
# bloqueia scraping com um desafio Cloudflare (ver nota no topo do arquivo).
LOJAS_ATIVAS = ("kabum_url", "terabyte_url")


def _preco_para_float(texto):
    """Converte um texto tipo 'R$ 4.899,99' em 4899.99 (float)."""
    if not texto:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})", texto)
    if not m:
        return None
    valor = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return None


def _extrair_via_jsonld(soup):
    """Procura preço em blocos <script type="application/ld+json">."""
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidatos = data if isinstance(data, list) else [data]
        for item in candidatos:
            if not isinstance(item, dict):
                continue
            oferta = item.get("offers")
            if isinstance(oferta, list):
                oferta = oferta[0] if oferta else None
            if isinstance(oferta, dict) and oferta.get("price"):
                try:
                    return float(oferta["price"]), item.get("name")
                except (TypeError, ValueError):
                    continue
    return None, None


def _extrair_via_regex(soup):
    """Fallback: primeiro valor R$ visível no texto da página."""
    texto = soup.get_text(" ", strip=True)
    preco = _preco_para_float(texto)
    titulo = soup.title.string.strip() if soup.title else None
    return preco, titulo


def _contem_todas_palavras(texto_norm, palavras):
    return all(re.search(rf"\b{re.escape(p)}\b", texto_norm) for p in palavras)


def _contem_alguma_palavra(texto_norm, palavras):
    return any(re.search(rf"\b{re.escape(p)}\b", texto_norm) for p in palavras)


def _extrair_via_busca_buscape(soup, termo_esperado, excluir_termos=()):
    """
    Procura, nos resultados de busca do Buscapé (embutidos como JSON dentro
    de <script id="__NEXT_DATA__">, em props.initialReduxState.hits.hits —
    cada item com "name" e "price"), o menor preço entre os itens cujo nome
    contém todas as palavras de `termo_esperado` (por palavra inteira, não
    por posição — o texto do anúncio varia de loja pra loja) e nenhuma das
    palavras de `excluir_termos` (ex.: "ti", pra não misturar RTX 5070 Ti
    nos resultados da RTX 5070 comum). Retorna (None, None) se nada bater.
    """
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None, None
    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError:
        return None, None

    hits = (
        data.get("props", {})
        .get("initialReduxState", {})
        .get("hits", {})
        .get("hits", [])
    )
    palavras_incluir = termo_esperado.strip().lower().split()
    palavras_excluir = [t.lower() for t in excluir_termos]

    melhor_preco, melhor_nome = None, None
    for hit in hits:
        nome = hit.get("name") or ""
        nome_norm = nome.lower()
        if not _contem_todas_palavras(nome_norm, palavras_incluir):
            continue
        if palavras_excluir and _contem_alguma_palavra(nome_norm, palavras_excluir):
            continue
        preco = hit.get("price")
        if not isinstance(preco, (int, float)):
            continue
        if melhor_preco is None or preco < melhor_preco:
            melhor_preco, melhor_nome = preco, nome
    return melhor_preco, melhor_nome


def _extrair_via_jsonld_buscape(soup):
    """
    Procura, no JSON-LD do Buscapé (schema.org/Product dentro de um bloco
    "@graph"), o preço agregado mínimo (offers.lowPrice) entre as lojas que
    o Buscapé compara para aquele anúncio.
    """
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        grafo = data.get("@graph") if isinstance(data, dict) else None
        if not grafo:
            continue
        for item in grafo:
            if not isinstance(item, dict) or item.get("@type") != "Product":
                continue
            oferta = item.get("offers")
            if isinstance(oferta, dict) and oferta.get("lowPrice"):
                try:
                    return float(oferta["lowPrice"]), item.get("name")
                except (TypeError, ValueError):
                    continue
    return None, None


def _salvar_debug_html(nome, html):
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    caminho = DEBUG_DIR / f"{nome}_{datetime.now():%Y%m%d_%H%M%S}.html"
    caminho.write_text(html, encoding="utf-8")
    return caminho


def coletar_preco(url, loja, modelo, debug=False):
    """
    Faz uma requisição à página do produto e tenta extrair o preço.
    Retorna um dict pronto para virar linha no CSV, ou None se falhar.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{loja}] Falha ao acessar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    preco, titulo = _extrair_via_jsonld(soup)
    if preco is None:
        preco, titulo = _extrair_via_regex(soup)

    if preco is None:
        print(f"[{loja}] Não foi possível extrair o preço de {url}.")
        if debug:
            caminho = _salvar_debug_html(f"{loja}_{modelo}".replace(" ", "_"), resp.text)
            print(f"  HTML salvo em: {caminho} — confira a estrutura para ajustar o seletor.")
        return None

    return {
        "data_hora": datetime.now().isoformat(timespec="seconds"),
        "loja": loja,
        "modelo": modelo,
        "preco": preco,
        "titulo_produto": titulo or "",
        "url": url,
    }


def coletar_preco_buscape_busca(url_busca, termo_esperado, modelo, excluir_termos=(), debug=False):
    """
    Busca `termo_esperado` na página de busca do Buscapé (comparador de
    preços) e extrai o menor preço encontrado ali para esse produto.
    Diferente de coletar_preco_buscape(), a página tem vários anúncios,
    então primeiro é preciso filtrar os que batem com o modelo esperado
    (ver _extrair_via_busca_buscape). Retorna um dict pronto para virar
    linha no CSV, ou None se falhar.
    """
    loja = "Buscapé (menor preço)"
    try:
        resp = requests.get(url_busca, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{loja}] Falha ao acessar {url_busca}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    preco, nome_anuncio = _extrair_via_busca_buscape(soup, termo_esperado, excluir_termos)

    if preco is None:
        print(f'[{loja}] Não encontrou preço para "{termo_esperado}" em {url_busca}.')
        if debug:
            nome_debug = f"Buscape_busca_{modelo}".replace(" ", "_")
            caminho = _salvar_debug_html(nome_debug, resp.text)
            print(f"  HTML salvo em: {caminho} — confira a estrutura para ajustar o seletor.")
        return None

    return {
        "data_hora": datetime.now().isoformat(timespec="seconds"),
        "loja": loja,
        "modelo": modelo,
        "preco": preco,
        "titulo_produto": nome_anuncio,
        "url": url_busca,
    }


def coletar_preco_buscape(url, modelo, debug=False):
    """
    Busca o menor preço agregado de um produto no Buscapé (comparador de
    preços), via o JSON-LD que a própria página de produto já expõe
    (offers.lowPrice, ver _extrair_via_jsonld_buscape). Diferente do
    Promotech, não precisa de página de busca separada.
    Retorna um dict pronto para virar linha no CSV, ou None se falhar.
    """
    loja = "Buscapé (menor preço)"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{loja}] Falha ao acessar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    preco, titulo = _extrair_via_jsonld_buscape(soup)

    if preco is None:
        print(f"[{loja}] Não foi possível extrair o preço de {url}.")
        if debug:
            caminho = _salvar_debug_html(f"Buscape_{modelo}".replace(" ", "_"), resp.text)
            print(f"  HTML salvo em: {caminho} — confira a estrutura para ajustar o seletor.")
        return None

    return {
        "data_hora": datetime.now().isoformat(timespec="seconds"),
        "loja": loja,
        "modelo": modelo,
        "preco": preco,
        "titulo_produto": titulo or "",
        "url": url,
    }


def coletar_todos(produtos_modelos, pausa_min=2, pausa_max=5, debug=False):
    """
    Percorre todos os modelos/lojas definidos em config.PRODUTOS_MODELOS e
    retorna uma lista de registros coletados com sucesso. Pausa entre
    requisições para não sobrecarregar os sites.
    """
    registros = []
    for modelo, info in produtos_modelos.items():
        for chave, url in info.items():
            if chave not in LOJAS_ATIVAS or not url:
                continue
            loja = chave.replace("_url", "").capitalize()
            registro = coletar_preco(url, loja, modelo, debug=debug)
            if registro:
                registros.append(registro)
                print(f"[OK] {modelo} — {loja}: R$ {registro['preco']:.2f}")
            time.sleep(random.uniform(pausa_min, pausa_max))

        url_buscape = info.get("buscape_url")
        if url_buscape:
            registro = coletar_preco_buscape(url_buscape, modelo, debug=debug)
            if registro:
                registros.append(registro)
                print(f"[OK] {modelo} — {registro['loja']}: R$ {registro['preco']:.2f}")
            time.sleep(random.uniform(pausa_min, pausa_max))

        url_busca_buscape = info.get("buscape_busca_url")
        termo_busca_buscape = info.get("buscape_busca_termo")
        if url_busca_buscape and termo_busca_buscape:
            excluir = info.get("buscape_busca_excluir", ())
            registro = coletar_preco_buscape_busca(
                url_busca_buscape, termo_busca_buscape, modelo, excluir_termos=excluir, debug=debug
            )
            if registro:
                registros.append(registro)
                print(f"[OK] {modelo} — {registro['loja']}: R$ {registro['preco']:.2f}")
            time.sleep(random.uniform(pausa_min, pausa_max))
    return registros
