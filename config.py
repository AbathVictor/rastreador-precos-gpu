# -*- coding: utf-8 -*-
"""
config.py — Ponto único de configuração do rastreador de preços.

Edite este arquivo para:
- trocar a SKU/versão específica de cada produto que você quer acompanhar
- adicionar ou remover lojas
- adicionar outros produtos no futuro (não precisa ser GPU — ver PS5 abaixo)

Nota sobre a RTX 5070 Ti: ela só existe com 16GB de memória (a versão de
12GB é a RTX 5070 "normal", sem o Ti). Os dados abaixo já refletem isso.

Nota sobre a Pichau: removida das lojas ativas — o site bloqueia
requisições automatizadas com um desafio Cloudflare (HTTP 403,
"Cf-Mitigated: challenge"), então nunca chega a servir o HTML com o preço.
Não é um link quebrado; é bloqueio anti-bot deliberado do site.

Nota sobre o Promotech: desde setembro/2026 o site bloqueia toda requisição
automatizada (busca, produto e até a home) com um desafio "Vercel Security
Checkpoint" (HTTP 429, `X-Vercel-Mitigated: challenge`) — mesma categoria de
bloqueio da Pichau, não é mais raspável. `promotech_url` fica abaixo só como
link de referência para conferência manual (abrindo num navegador de
verdade); a coleta automática (`coletar_todos` em scrapers.py) não usa mais
essa chave, e a busca das GPUs no comparador foi substituída pelo Buscapé
(ver abaixo).

Nota sobre o Buscapé: usado de duas formas diferentes.
- PS5 (`buscape_url`): a própria página de produto já expõe o preço via
  JSON-LD (schema.org/Product, com `offers.lowPrice`), sem precisar de
  página de busca nem de casar nome de anúncio — ver `coletar_preco_buscape`
  em scrapers.py.
- GPUs (`buscape_busca_url`/`buscape_busca_termo`/`buscape_busca_excluir`,
  opcional): substitui a antiga busca via Promotech. A página de busca do
  Buscapé embute os resultados como JSON dentro de um bloco
  `<script id="__NEXT_DATA__">` (cada item com `name` e `price`), então em
  vez de casar texto de card na marra (como era com o Promotech) o scraper
  filtra os itens cujo nome contém todas as palavras de
  `buscape_busca_termo` (comparação por palavra, não por posição — os nomes
  variam entre anúncios) e nenhuma das palavras de `buscape_busca_excluir`
  (usado para não misturar RTX 5070 Ti nos resultados da RTX 5070 comum), e
  usa o menor preço entre os que sobrarem — ver
  `coletar_preco_buscape_busca` em scrapers.py.
"""

PRODUTOS_MODELOS = {
    "RX 9070 XT 16GB": {
        "fabricante_modelo": "ASRock Challenger",
        "kabum_url": (
            "https://www.kabum.com.br/produto/921271/"
            "placa-de-video-asrock-radeon-rx-9070-xt-challenger-amd-16gb-90-ga61zz-00uanf"
        ),
        "terabyte_url": (
            "https://www.terabyteshop.com.br/produto/38584/"
            "placa-de-video-asrock-amd-radeon-rx-9070-xt-challenger-16gb-gddr6-fsr-ray-tracing-90-ga61zz-00uanf"
        ),
        "promotech_url": (
            "https://promotech.app.br/produtos/placa-de-video/modelo/un3ua4ft/"
            "asrock-rx-9070-xt-challenger?visao=avancada"
        ),
        "buscape_busca_url": "https://www.buscape.com.br/search?q=rx%209070%20xt",
        "buscape_busca_termo": "ASRock RX 9070 XT Challenger",
    },
    "RTX 5070 Ti 16GB": {
        "fabricante_modelo": "MSI Shadow 3X OC",
        "kabum_url": (
            "https://www.kabum.com.br/produto/779497/"
            "placa-de-video-msi-geforce-rtx-5070-ti-shadow-3x-oc-16gb-gddr7-256-bit-g507t-16s3c"
        ),
        "terabyte_url": (
            "https://www.terabyteshop.com.br/produto/35475/"
            "placa-de-video-msi-nvidia-geforce-rtx-5070-ti-shadow-3x-oc-16gb-gddr7-dlss-ray-tracing-912-v531-097"
        ),
        "promotech_url": (
            "https://promotech.app.br/produtos/placa-de-video/modelo/bdh32uxm?visao=avancada"
        ),
        # Busca dedicada "rtx 5070 ti" (não "rtx 5070" genérico): testada e
        # confirmada — a busca genérica não traz o SKU MSI Shadow 3X OC Ti
        # entre os resultados retornados pelo Buscapé.
        "buscape_busca_url": "https://www.buscape.com.br/search?q=rtx%205070%20ti",
        "buscape_busca_termo": "MSI RTX 5070 Ti Shadow 3X OC",
    },
    "RTX 5070 12GB": {
        # Diferente das outras duas linhas, aqui cada loja aponta para um
        # modelo/fabricante diferente (PNY na Promotech, MSI na Kabum, Palit
        # na Terabyte) — a RTX 5070 12GB comum (não-Ti) é acompanhada pelo
        # menor preço disponível em cada loja, não por uma SKU fixa única.
        "fabricante_modelo": "diversos (menor preço por loja)",
        "kabum_url": (
            "https://www.kabum.com.br/produto/725587/"
            "placa-de-video-msi-geforce-rtx-5070-12g-ventus-2x-oc-12-gb-gddr7-28gbps-nvidia-geforce-rtx-5070-g5070-12v2c"
        ),
        "terabyte_url": (
            "https://www.terabyteshop.com.br/produto/40135/"
            "placa-de-video-palit-nvidia-geforce-rtx-5070-white-oc-12gb-gddr7-dlss-ray-tracing-ne75070u19k9-gb2050w"
        ),
        "promotech_url": (
            "https://promotech.app.br/produtos/placa-de-video/modelo/k8ydt19i/pny-rtx-5070-oc"
        ),
        # Sem SKU fixa (ver nota acima) — pega o menor preço entre qualquer
        # RTX 5070 12GB não-Ti listada pela busca.
        "buscape_busca_url": "https://www.buscape.com.br/search?q=rtx%205070",
        "buscape_busca_termo": "RTX 5070",
        "buscape_busca_excluir": ("ti",),
    },
    "PS5 Edição Digital 825GB": {
        "fabricante_modelo": "Sony (menor preço entre lojas via Buscapé)",
        "buscape_url": (
            "https://www.buscape.com.br/console-de-video-game/"
            "console-playstation-5-edicao-digital-sony-4k"
            "?_lc=88&experiencevariant=cro-12-2&searchterm=ps5%2Bconsole"
        ),
    },
    "PS5 Slim 1TB": {
        "fabricante_modelo": "Sony (menor preço entre lojas via Buscapé)",
        "buscape_url": (
            "https://www.buscape.com.br/console-de-video-game/"
            "pre-venda-console-playstation-5-slim-1-tb-sony-1214a-4k"
            "?_lc=88&experiencevariant=cro-12-2&searchterm=ps5%2Bconsole"
        ),
    },
}

CSV_HISTORICO = "data/historico_precos.csv"
CSV_DOLAR = "data/cotacao_dolar.csv"
