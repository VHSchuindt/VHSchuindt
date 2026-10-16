"""Etapas 1 e 2 do monitor de passagens Cuiabá -> São Paulo.

1. Malha oficial da ANAC (API SIROS): voos diretos programados, com número do voo e avião.
2. Preços do Google Flights (biblioteca fast-flights), casados com a malha da ANAC.

Saída: viagem/dados/coleta.json
Uso:   python coletar.py
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta, date

from config import IDA, VOLTA, AEROPORTOS_SP, ICAO, CIAS

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "dados", "coleta.json")
FUSO = {"SBCY": 4, "SBGR": 3, "SBSP": 3, "SBKP": 3}  # horas atrás do UTC
IATA = {v: k for k, v in ICAO.items()}


def etapa1_anac():
    datas = IDA + VOLTA
    ini = min(datas)
    fim = max(datas) + timedelta(days=1)  # voos noturnos caem no dia seguinte em UTC
    url = ("https://sas.anac.gov.br/sas/siros_api/api/voosPeriodo"
           f"?dataReferenciaInicio={ini:%d%m%Y}&dataReferenciaFinal={fim:%d%m%Y}")
    with urllib.request.urlopen(url, timeout=300) as r:
        dados = json.loads(r.read())
    if isinstance(dados, str):
        dados = json.loads(dados)
    voos, vistos = [], set()
    for v in dados:
        o, d = v["sg_icao_origem"], v["sg_icao_destino"]
        if not ((o == "SBCY" and d in FUSO and d != "SBCY") or (d == "SBCY" and o in FUSO and o != "SBCY")):
            continue
        assentos = int(v["qt_assentos_previstos"] or 0)
        if assentos == 0:  # carga/reposicionamento, não vende
            continue
        partida = datetime.strptime(v["dt_partida_prevista_utc"], "%d/%m/%Y %H:%M") - timedelta(hours=FUSO[o])
        chegada = datetime.strptime(v["dt_chegada_prevista_utc"], "%d/%m/%Y %H:%M") - timedelta(hours=FUSO[d])
        sentido = "ida" if o == "SBCY" else "volta"
        if partida.date() not in (IDA if sentido == "ida" else VOLTA):
            continue
        cia = CIAS.get(v["sg_empresa_icao"], v["sg_empresa_icao"])
        numero = cia + v["nr_voo"].lstrip("0")
        chave = (numero, partida)
        if chave in vistos:
            continue
        vistos.add(chave)
        voos.append({"sentido": sentido, "voo": numero, "origem": IATA[o], "destino": IATA[d],
                     "partida": partida.isoformat(), "chegada": chegada.isoformat(),
                     "aviao": v["sg_equipamento_icao"], "assentos": assentos})
    return sorted(voos, key=lambda x: x["partida"])


def casar_voo(malha, sentido, origem, destino, partida):
    """Acha o número do voo na malha da ANAC pelo trecho e horário (tolerância de 20 min)."""
    melhor = None
    for v in malha:
        if v["sentido"] == sentido and v["origem"] == origem and v["destino"] == destino:
            dif = abs((datetime.fromisoformat(v["partida"]) - partida).total_seconds())
            if dif <= 20 * 60 and (melhor is None or dif < melhor[0]):
                melhor = (dif, v)
    return melhor[1] if melhor else None


def etapa2_google(malha):
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    precos, erros = [], []
    consultas = [("ida", d, "CGB", sp) for d in IDA for sp in AEROPORTOS_SP] + \
                [("volta", d, sp, "CGB") for d in VOLTA for sp in AEROPORTOS_SP]
    for sentido, dia, o, d in consultas:
        q = create_query(flights=[FlightQuery(date=dia.isoformat(), from_airport=o, to_airport=d)],
                         trip="one-way", passengers=Passengers(adults=1),
                         language="pt-BR", currency="BRL", max_stops=0)
        try:
            for f in get_flights(q, proxy=proxy):
                s = f.flights[0]
                partida = datetime(*s.departure.date, *s.departure.time)
                chegada = datetime(*s.arrival.date, *s.arrival.time)
                ref = casar_voo(malha, sentido, o, d, partida)
                precos.append({"fonte": "Google", "sentido": sentido,
                               "voo": ref["voo"] if ref else "?",
                               "cia": ",".join(f.airlines), "origem": o, "destino": d,
                               "partida": partida.isoformat(), "chegada": chegada.isoformat(),
                               "aviao": s.plane_type, "preco": f.price, "link": None,
                               "na_malha_anac": ref is not None})
        except Exception as e:
            erros.append(f"Google {sentido} {dia} {o}->{d}: {type(e).__name__}: {str(e)[:150]}")
    return precos, erros


if __name__ == "__main__":
    os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
    erros = []
    try:
        malha = etapa1_anac()
    except Exception as e:
        malha, erros = [], [f"ANAC: {type(e).__name__}: {e}"]
    print(f"Etapa 1 (ANAC): {len(malha)} voos diretos programados")
    precos, e2 = etapa2_google(malha)
    erros += e2
    print(f"Etapa 2 (Google): {len(precos)} preços")
    for e in erros:
        print("  ERRO", e)
    with open(SAIDA, "w") as f:
        json.dump({"coletado_em": datetime.now().isoformat(timespec="minutes"),
                   "malha_anac": malha, "google": precos, "erros": erros}, f, ensure_ascii=False, indent=1)
    print("Salvo em", SAIDA)
