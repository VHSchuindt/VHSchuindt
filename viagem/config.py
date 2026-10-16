"""Parâmetros da viagem. Edite aqui para mudar datas ou aeroportos."""
from datetime import date, timedelta

CASAMENTO = date(2027, 1, 9)
# Ida: de 5/jan até o dia do casamento (data limite)
IDA = [date(2027, 1, 5) + timedelta(days=i) for i in range((CASAMENTO - date(2027, 1, 5)).days + 1)]
# Volta: depois do casamento (ainda não definida; usada só para o total ida + volta)
VOLTA = [date(2027, 1, 10), date(2027, 1, 11)]

AEROPORTOS_SP = ["GRU", "VCP", "CGH"]
ICAO = {"CGB": "SBCY", "GRU": "SBGR", "CGH": "SBSP", "VCP": "SBKP"}
CIAS = {"GLO": "G3", "AZU": "AD", "TAM": "LA"}
NOMES = {"GRU": "Guarulhos", "VCP": "Campinas", "CGH": "Congonhas", "CGB": "Cuiabá"}
