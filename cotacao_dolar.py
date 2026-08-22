# -*- coding: utf-8 -*-
"""
cotacao_dolar.py — Histórico de cotação USD/BRL via AwesomeAPI (gratuita,
sem necessidade de chave/cadastro).
Documentação: https://docs.awesomeapi.com.br/api-de-moedas

Como o preço de GPU no Brasil costuma acompanhar o câmbio (a maioria é
importada), esse histórico ajuda a separar "a placa ficou mais cara" de
"o dólar subiu e arrastou tudo junto".
"""

import pandas as pd
import requests


def obter_historico_dolar(dias=365):
    """
    Retorna um DataFrame com a cotação de fechamento diária do dólar
    (USD/BRL) para os últimos `dias` dias corridos.
    Colunas: data, cotacao_venda
    """
    url = f"https://economia.awesomeapi.com.br/json/daily/USD-BRL/{dias}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    dados = resp.json()

    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="s").dt.date
    df["cotacao_venda"] = df["bid"].astype(float)
    return df[["data", "cotacao_venda"]].sort_values("data").reset_index(drop=True)
