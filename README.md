# Rastreador de Preços — RX 9070 XT 16GB vs RTX 5070 Ti 16GB

## Como rodar

1. Abra a pasta no VSCode.
2. Crie um ambiente virtual (opcional, mas recomendado) e instale as dependências:
   ```
   pip install requests beautifulsoup4 pandas matplotlib plotly jupyter
   ```
3. Abra `analise_precos.ipynb` e rode as células na ordem. A célula de coleta
   (Seção 1) é a única que você precisa rodar repetidamente ao longo do
   tempo — as demais são de análise e podem ser re-executadas a qualquer
   momento.

## Arquivos

- `config.py` — URLs das lojas/modelos que estão sendo acompanhados. Edite
  aqui para trocar de SKU ou adicionar lojas.
- `scrapers.py` — lógica de extração de preço (Kabum, Terabyte, Promotech).
- `cotacao_dolar.py` — histórico de câmbio USD/BRL via AwesomeAPI (gratuita).
- `data/historico_precos.csv` — dados acumulados. Já vem com um ponto
  inicial (13/08/2026) extraído do Promotech para cada modelo.
- `analise_precos.ipynb` — notebook principal: coleta + análise + gráficos.

## Lojas ativas na coleta

- **Kabum** e **Terabyte** — scraping direto da página do produto via dados
  estruturados JSON-LD.
- **Promotech** — comparador de preços; a coleta usa a página de *busca*
  (não a de detalhe do produto, que carrega via JavaScript) e retorna o
  menor preço encontrado entre as lojas que ele compara.
- **Pichau** — fora da coleta ativa. O site responde com um desafio
  Cloudflare (HTTP 403) para requisições automatizadas, então não há como
  extrair o preço via scraping simples sem contornar essa proteção
  anti-bot — o que não fazemos aqui.

## Sobre os dados iniciais

O CSV já começa com um preço à vista de cada modelo, extraído manualmente
das páginas do Promotech (Kabum R$ 4.899,99 para a RX 9070 XT Challenger;
Shopee R$ 7.083,08 para a RTX 5070 Ti Shadow 3X OC), pois o histórico
completo daquele site carrega via JavaScript e não é acessível por scraping
simples. A partir daqui, o histórico "de verdade" é construído pelas suas
próprias coletas via Kabum, Terabyte e Promotech.

## Manutenção esperada

Scrapers de e-commerce quebram de vez em quando quando o site muda de
layout. Se isso acontecer, rode a coleta com `debug=True` (já é o padrão)
e confira o HTML salvo em `data/debug_html/` para ajustar o seletor em
`scrapers.py`. Isso é normal e não indica um problema na lógica geral da
ferramenta.
