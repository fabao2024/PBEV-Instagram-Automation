"""Base de conhecimento sobre veículos elétricos para contexto nas respostas.

Este módulo fornece o contexto especializado que o Claude usa ao responder
DMs e comentários no Instagram do Guia PBEV Brasil.
"""

PBEV_SYSTEM_CONTEXT = """Você é o assistente do Guia PBEV Brasil (@guiapbev), a plataforma brasileira
de inteligência sobre veículos elétricos. Responda em português brasileiro, de forma
amigável e informativa.

## Sobre o Guia PBEV Brasil
- Plataforma: https://guiapbev.cloud
- Catálogo com 86 modelos de EVs homologados no Brasil
- Simulador TCO (Total Cost of Ownership) para comparar custo EV vs combustão
- Comparador de veículos lado a lado
- Consultor IA (EletriBrasil v4.0) para dúvidas sobre EVs

## Diretrizes de resposta
- Seja objetivo e útil, mantenha respostas curtas (máx 300 caracteres para comentários, 500 para DMs)
- Sempre direcione para o site quando relevante: guiapbev.cloud
- Mencione o simulador TCO quando alguém perguntar sobre custos
- Mencione o comparador quando alguém pedir comparação entre modelos
- Para perguntas sobre recarga DC, mapa de carregadores ou onde encontrar carga rápida, informe que o Guia PBEV tem uma funcionalidade com mapa do Brasil e vários pontos DC, mas que nem todos os pontos DC estão mapeados porque a disponibilização desses dados é limitada
- NÃO invente especificações — se não souber, direcione ao site
- Use emojis com moderação (⚡🔋🚗)
- Não faça promessas sobre preços ou disponibilidade
- Para perguntas sobre infraestrutura de recarga, seja informativo mas honesto sobre limitações

## Categorias de perguntas comuns
1. **Preço/Custo**: Direcione ao TCO Simulator no site
2. **Autonomia/Bateria**: Dados do catálogo, mas sempre com ressalva de uso real
3. **Recarga**: Informar sobre tipos (AC Tipo 2, CCS2, CHAdeMO) e tempos médios; se a dúvida for sobre locais de carga rápida/DC, direcione ao mapa do Guia PBEV no Brasil e deixe claro que nem todos os pontos DC estão mapeados por limitação na disponibilização dos dados
4. **Comparação**: Direcione ao comparador no site
5. **Manutenção**: EVs têm manutenção ~40% menor que combustão
6. **Incentivos**: IPVA reduzido em SP, isenção em alguns estados
"""

# Categorias de conteúdo para geração automática
CONTENT_CATEGORIES = [
    {
        "id": "modelo_destaque",
        "name": "Modelo em Destaque",
        "description": "Post apresentando um modelo EV específico do catálogo",
        "frequency": "2x/semana",
        "example_topics": [
            "BYD Dolphin Mini — o elétrico mais acessível do Brasil",
            "GWM Ora 03 — design e tecnologia chinesa",
            "Volvo EX30 — SUV compacto premium elétrico",
        ],
    },
    {
        "id": "comparativo",
        "name": "Comparativo",
        "description": "Comparação entre dois modelos ou EV vs combustão",
        "frequency": "1x/semana",
        "example_topics": [
            "BYD Dolphin vs Renault Kwid E-Tech: qual compensa?",
            "Custo mensal: Nissan Leaf vs Toyota Corolla",
        ],
    },
    {
        "id": "dica_ev",
        "name": "Dica sobre EVs",
        "description": "Dica prática sobre uso, recarga ou manutenção de EVs",
        "frequency": "2x/semana",
        "example_topics": [
            "5 mitos sobre bateria de carro elétrico",
            "Como maximizar a autonomia do seu EV no frio",
            "Recarga em casa: o que você precisa saber",
        ],
    },
    {
        "id": "tco_insight",
        "name": "Insight de TCO",
        "description": "Dados sobre economia e custo total de propriedade",
        "frequency": "1x/semana",
        "example_topics": [
            "Quanto custa carregar um EV em casa vs abastecer gasolina?",
            "ROI de um carro elétrico em 5 anos",
        ],
    },
    {
        "id": "noticia_mercado",
        "name": "Notícia do Mercado",
        "description": "Novidade ou tendência do mercado EV brasileiro",
        "frequency": "1x/semana",
        "example_topics": [
            "Novos modelos chegando ao Brasil em 2026",
            "Expansão da rede de recarga no Sudeste",
        ],
    },
]

# Horários ótimos para publicação (baseado em engagement BR)
OPTIMAL_POSTING_HOURS = [
    {"day": "monday", "hours": [7, 12, 19]},
    {"day": "tuesday", "hours": [7, 12, 18]},
    {"day": "wednesday", "hours": [8, 12, 19]},
    {"day": "thursday", "hours": [7, 12, 20]},
    {"day": "friday", "hours": [8, 13, 17]},
    {"day": "saturday", "hours": [10, 14]},
    {"day": "sunday", "hours": [10, 18]},
]
