"""
Flask por padrão serializa `datetime`/`date` no formato HTTP (RFC 1123,
ex: "Fri, 14 Aug 2026 16:05:00 GMT") em vez de ISO 8601. O Dart
`DateTime.parse()` só entende ISO 8601, então isso quebrava qualquer
tela do app que lesse uma data vinda da API (eventos, principalmente).

Esse provider troca só essa parte: datas viram ISO 8601 (o que o
Flutter já manda de volta pra API também), tudo o mais (UUID, bytes,
dataclass etc.) continua com o comportamento padrão do Flask.
"""

from datetime import date, datetime

from flask.json.provider import DefaultJSONProvider


class ISODateJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)
