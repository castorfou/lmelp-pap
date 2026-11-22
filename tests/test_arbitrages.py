"""La décision d'un arbitrage en clair, pour les logs (``arbitrages.decision``)."""

from datetime import date

import pytest

from lmelp_pap.arbitrages import decision
from lmelp_pap.liste import Arbitrage


@pytest.mark.parametrize(
    ("arbitrage", "attendu"),
    [
        (
            Arbitrage("ina", "1", "thème", themes=frozenset({"théâtre", "cinéma"})),
            "cinéma, théâtre",
        ),
        (Arbitrage("ina", "1", "existence", existe=True), "existe"),
        (Arbitrage("ina", "1", "existence"), "n'existe pas"),
        (
            Arbitrage("ina", "1", "date", date_retenue=date(1967, 1, 1)),
            "1967-01-01",
        ),
        (Arbitrage("ina", "1", "date"), "sans date"),
        (Arbitrage("ina", "1", "écoute"), "renvoi à l'écoute"),
        (Arbitrage("ina", "1", "rapprochement"), "ina:1 → gardée ici"),
        (
            Arbitrage("ina", "1", "rapprochement", cible=("lmelp", "x")),
            "ina:1 → lmelp:x",
        ),
    ],
)
def test_la_decision_d_un_arbitrage_en_clair(
    arbitrage: Arbitrage, attendu: str
) -> None:
    assert decision(arbitrage) == attendu


def test_la_decision_porte_sa_justification() -> None:
    arbitrage = Arbitrage("ina", "1", "écoute", justification="son coupé")

    assert decision(arbitrage) == "renvoi à l'écoute (« son coupé »)"
