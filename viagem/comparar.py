"""Etapa 3 do monitor: junta ANAC + Google + Kiwi, compara com a consulta anterior e gera o relatório.

Entradas: dados/coleta.json (de coletar.py) e dados/kiwi.json (salvo pela sessão do Claude a partir do conector Kiwi).
Saídas:   RELATORIO.md (última consulta), HISTORICO.md (uma linha por consulta), dados/historico.jsonl.
Imprime o resumo curto usado na notificação.
"""
import json, os
from datetime import datetime

from config import CASAMENTO, IDA, NOMES

AQUI = os.path.dirname(os.path.abspath(__file__))
D = lambda *p: os.path.join(AQUI, *p)


def carregar():
    coleta = json.load(open(D("dados", "coleta.json")))
    kiwi = json.load(open(D("dados", "kiwi.json"))) if os.path.exists(D("dados", "kiwi.json")) else []
    malha = {(v["voo"], v["partida"][:10]): v for v in coleta["malha_anac"]}
    ofertas = []
    for k in kiwi:
        ref = malha.get((k["voo"], k["partida"][:10]))
        ofertas.append({**k, "fonte": "Kiwi", "aviao": ref["aviao"] if ref else "?", "na_malha_anac": ref is not None})
    ofertas += coleta["google"]
    return coleta, ofertas


def fmt(o):
    if not o:
        return "—"
    p = datetime.fromisoformat(o["partida"])
    rota = f'{NOMES.get(o["origem"], o["origem"])} → {NOMES.get(o["destino"], o["destino"])}'
    aviso = " ⚠️ dia do casamento" if p.date() == CASAMENTO and o["sentido"] == "ida" else ""
    return f'{o["voo"]} {p:%d/%m %H:%M} {rota} — R$ {o["preco"]} ({o["fonte"]}){aviso}'


def mais_barato(ofertas, **filtros):
    c = [o for o in ofertas if all(o.get(k) == v for k, v in filtros.items())]
    return min(c, key=lambda o: (o["preco"], o["partida"])) if c else None


NIVEIS = [(500, 3, "🚨🚨🚨 ALERTA MÁXIMO — abaixo de R$ 500"),
          (600, 2, "🔴🔴 ALERTA FORTE — abaixo de R$ 600"),
          (700, 1, "🟡 Alerta — abaixo de R$ 700")]


def nivel(o):
    """0 = sem alerta; 1, 2, 3 = cada vez mais severo conforme o preço cai."""
    for teto, n, rotulo in NIVEIS:
        if o and o["preco"] < teto:
            return n, rotulo
    return 0, ""


def mesmo_voo(a, b):
    return a and b and a["voo"] == b["voo"] and a["partida"] == b["partida"]


def main():
    coleta, ofertas = carregar()
    agora = datetime.now()
    ida = [o for o in ofertas if o["sentido"] == "ida"]
    ida_segura = [o for o in ida if datetime.fromisoformat(o["partida"]).date() < CASAMENTO]
    snap = {
        "quando": agora.isoformat(timespec="minutes"),
        "ida": mais_barato(ida),
        "ida_ate_vespera": mais_barato(ida_segura),
        "ida_kiwi": mais_barato(ida, fonte="Kiwi"),
        "ida_google": mais_barato(ida, fonte="Google"),
        "volta": mais_barato(ofertas, sentido="volta"),
    }
    snap["total"] = (snap["ida"]["preco"] + snap["volta"]["preco"]) if snap["ida"] and snap["volta"] else None

    hist_path = D("dados", "historico.jsonl")
    anterior = None
    if os.path.exists(hist_path):
        linhas = [l for l in open(hist_path) if l.strip()]
        anterior = json.loads(linhas[-1]) if linhas else None

    # ---- narrativa ----
    txt = []
    atual, k, g = snap["ida"], snap["ida_kiwi"], snap["ida_google"]
    if not anterior:
        txt.append(f"Primeira consulta. Ida mais barata agora: {fmt(atual)}.")
    else:
        ant = anterior["ida"]
        horas = round((agora - datetime.fromisoformat(anterior["quando"])).total_seconds() / 3600)
        if mesmo_voo(atual, ant):
            dif = atual["preco"] - ant["preco"]
            mov = "subiu" if dif > 0 else "caiu" if dif < 0 else "ficou igual"
            txt.append(f"Continua o mesmo voo mais barato: {fmt(atual)}. Há {horas}h custava R$ {ant['preco']} — {mov}"
                       + (f" R$ {abs(dif)}." if dif else "."))
        else:
            txt.append(f"O voo mais barato agora é {fmt(atual)}.")
            txt.append(f"Há {horas}h o mais barato era {fmt(ant)}.")
        mais_baratos = [o for o in (k, g) if o and o["preco"] < ant["preco"]]
        if k and g and len(mais_baratos) == 2:
            txt.append(f"Kiwi (R$ {k['preco']}) e Google (R$ {g['preco']}) estão os dois mais baratos que o anterior (R$ {ant['preco']}).")
        elif mais_baratos:
            o = mais_baratos[0]
            txt.append(f"Só o {o['fonte']} (R$ {o['preco']}) ficou mais barato que o anterior (R$ {ant['preco']}).")
        else:
            txt.append(f"Nenhuma das fontes ficou mais barata que o anterior (R$ {ant['preco']}).")
    if k and g:
        a, b = sorted((k, g), key=lambda o: o["preco"])
        txt.append(f"Agora: {a['fonte']} R$ {a['preco']} ({a['voo']}) é mais barato que {b['fonte']} R$ {b['preco']} ({b['voo']})"
                   + (f" por R$ {b['preco'] - a['preco']}." if b["preco"] != a["preco"] else " — empate."))
    if atual and datetime.fromisoformat(atual["partida"]).date() == CASAMENTO and snap["ida_ate_vespera"]:
        txt.append(f"Chegando até a véspera (mais seguro): {fmt(snap['ida_ate_vespera'])}.")
    if snap["total"]:
        t = f"Total ida + volta: R$ {snap['total']} (volta {fmt(snap['volta'])})"
        if anterior and anterior.get("total"):
            d = snap["total"] - anterior["total"]
            t += f"; antes R$ {anterior['total']} ({'+' if d > 0 else ''}{d})" if d else "; igual ao anterior"
        txt.append(t + ".")
    n, rotulo = nivel(atual)
    snap["nivel"] = n
    if n:
        cabeca = f"{rotulo}: {fmt(atual)}"
        n_ant = (anterior or {}).get("nivel", 0)
        if anterior and n > n_ant:
            cabeca += " — NOVA FAIXA, preço caiu de nível!"
        txt.insert(0, cabeca)
    resumo = "\n".join(txt)

    # ---- relatório completo ----
    r = [f"# Monitor de passagens Cuiabá → São Paulo", "",
         f"Consulta de {agora:%d/%m/%Y %H:%M} (UTC). Ida de {IDA[0]:%d/%m} até {CASAMENTO:%d/%m} (casamento). "
         "Preços por pessoa, só ida, voo direto, sem mala despachada.", "",
         "## Resumo", "", *[f"- {l}" for l in txt], "",
         "## Mais barato por dia de ida", "", "| Dia | Kiwi | Google |", "|---|---|---|"]
    for dia in IDA:
        kk = mais_barato([o for o in ida if o["partida"][:10] == dia.isoformat()], fonte="Kiwi")
        gg = mais_barato([o for o in ida if o["partida"][:10] == dia.isoformat()], fonte="Google")
        f2 = lambda o: f'R$ {o["preco"]} — {o["voo"]} {o["partida"][11:16]} → {NOMES[o["destino"]]}' if o else "—"
        r.append(f"| {dia:%d/%m}{' ⚠️' if dia == CASAMENTO else ''} | {f2(kk)} | {f2(gg)} |")
    r += ["", "## Top 10 ida (todas as fontes)", "", "| Preço | Fonte | Voo | Partida | Destino | Avião | Na malha ANAC | Link |",
          "|---|---|---|---|---|---|---|---|"]
    for o in sorted(ida, key=lambda o: o["preco"])[:10]:
        r.append(f'| R$ {o["preco"]} | {o["fonte"]} | {o["voo"]} | {o["partida"][8:10]}/{o["partida"][5:7]} {o["partida"][11:16]} | '
                 f'{NOMES[o["destino"]]} | {o.get("aviao","?")} | {"✅" if o.get("na_malha_anac") else "⚠️"} | {o["link"] or "site da cia"} |')
    r += ["", "## Top 5 volta", "", "| Preço | Fonte | Voo | Partida | Origem | Link |", "|---|---|---|---|---|---|"]
    for o in sorted([o for o in ofertas if o["sentido"] == "volta"], key=lambda o: o["preco"])[:5]:
        r.append(f'| R$ {o["preco"]} | {o["fonte"]} | {o["voo"]} | {o["partida"][8:10]}/{o["partida"][5:7]} {o["partida"][11:16]} | '
                 f'{NOMES[o["origem"]]} | {o["link"] or "site da cia"} |')
    r += ["", f"Malha ANAC: {len(coleta['malha_anac'])} voos diretos programados no período."]
    if coleta.get("erros"):
        r += ["", "Erros nesta consulta:", *[f"- {e}" for e in coleta["erros"]]]
    open(D("RELATORIO.md"), "w").write("\n".join(r) + "\n")

    hist_md = D("HISTORICO.md")
    novo = not os.path.exists(hist_md)
    with open(hist_md, "a") as f:
        if novo:
            f.write("# Histórico de preços (ida mais barata)\n\n| Quando (UTC) | Ida mais barata | Kiwi | Google | Total ida+volta |\n|---|---|---|---|---|\n")
        f.write(f"| {agora:%d/%m %H:%M} | {fmt(atual)} | R$ {k['preco'] if k else '—'} | R$ {g['preco'] if g else '—'} | R$ {snap['total']} |\n")
    with open(hist_path, "a") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    print(resumo)


if __name__ == "__main__":
    main()
