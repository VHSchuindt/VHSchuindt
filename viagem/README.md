# Monitor de passagens Cuiabá → São Paulo (casamento 9/jan/2027)

Roda a cada 5 horas como tarefa agendada do Claude Code. Cada execução tem 3 etapas:

1. **Malha da ANAC** (`coletar.py`): API SIROS, voos diretos programados de 5/jan até o dia do casamento (e voltas 10–11/jan), com número do voo, avião e assentos.
2. **Preços** — Google Flights via [fast-flights](https://github.com/AWeirdDev/flights) (`coletar.py`) e Kiwi.com via conector do Claude (salvo em `dados/kiwi.json`).
3. **Comparação** (`comparar.py`): mais barato agora × mais barato da consulta anterior, Kiwi × Google, total ida + volta.
4. **Alertas** por faixa de preço da ida (por pessoa): 🟡 abaixo de R$ 700, 🔴🔴 abaixo de R$ 600, 🚨🚨🚨 abaixo de R$ 500. Quando cai de faixa, o alerta avisa "NOVA FAIXA".

Resultados:
- [`RELATORIO.md`](RELATORIO.md) — última consulta completa
- [`HISTORICO.md`](HISTORICO.md) — uma linha por consulta

Datas e aeroportos ficam em `config.py`.
