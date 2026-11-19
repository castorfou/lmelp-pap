"""Construction de la liste des émissions à partir des attestations des sources.

Vocabulaire : voir CONTEXT.md. Décisions : docs/adr/0001, 0002 et 0003.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, Literal, NamedTuple

from lmelp_pap.sources.audio_radiofrance import lire_nom_fichier


# Une attestation dans sa source (source, identifiant dans la source) : la clé
# à laquelle un arbitrage s'attache, et par laquelle il désigne une émission.
CleAttestation = tuple[str, str]
# Une émission rivale d'un rapprochement ambigu : son identifiant, et
# l'attestation qui la désigne dans un arbitrage de rapprochement.
Rivale = tuple[str, CleAttestation]
Sorte = Literal["thème", "existence", "écoute", "date", "rapprochement"]


@dataclass(frozen=True)
class Enregistrement:
    """Un fichier audio d'une émission, intégral ou extrait."""

    url: str
    type: str  # "intégral" ou "extrait"
    duree: str | None = None  # HH:MM:SS, quand une source la connaît


@dataclass(frozen=True)
class Attestation:
    """Ce qu'une source dit d'une émission, à une date donnée."""

    source: str
    source_id: str
    date: date
    themes: frozenset[str] = frozenset()
    titre: str | None = None
    description: str | None = None
    chaine: str | None = None
    heure: str | None = None
    duree: str | None = None
    animateur: str | None = None
    url: str | None = None
    enregistrements: tuple[Enregistrement, ...] = ()
    extrait: bool = False  # un fragment, qui ne décrit pas l'émission entière
    # La date de première diffusion, de publication (dans le podcast pour
    # lmelp, d'une fiche rattachée par son archive) ou de rediffusion (INA) :
    # seule une première diffusion date l'émission.
    nature_date: Literal["première diffusion", "publication", "rediffusion"] = (
        "première diffusion"
    )

    @property
    def cle(self) -> CleAttestation:
        """L'attestation dans sa source : à quoi un arbitrage s'attache."""
        return (self.source, self.source_id)


@dataclass
class Emission:
    """Une émission de la liste, construite à partir de ses attestations."""

    id: str
    date: date
    themes: frozenset[str]
    titre: str | None = None
    description: str | None = None
    chaine: str | None = None
    heure: str | None = None
    duree: str | None = None
    animateur: str | None = None
    attestations: list[Attestation] = field(default_factory=list)
    enregistrements: list[Enregistrement] = field(default_factory=list)
    # l'arbitrage appliqué : de thème, ou renvoi à l'écoute
    arbitrage: "Arbitrage | None" = None
    # l'arbitrage de date, qui se cumule avec le précédent
    arbitrage_date: "Arbitrage | None" = None
    # l'arbitrage d'existence « existe », qui se cumule avec les précédents
    arbitrage_existence: "Arbitrage | None" = None

    @property
    def a_ecouter(self) -> bool:
        """L'émission est renvoyée à l'écoute : ses doutes sont « à écouter »."""
        return self.arbitrage is not None and self.arbitrage.sorte == "écoute"


@dataclass(frozen=True)
class Arbitrage:
    """Une décision humaine qui lève un doute, attachée à une attestation.

    Un renvoi à l'écoute (sorte ``écoute``) s'enregistre et s'applique comme un
    arbitrage, mais ne lève aucun doute : il marque ceux de l'émission
    « à écouter ».

    Un arbitrage de date (sorte ``date``) fixe la date de première diffusion de
    l'émission. Il porte sur un autre point que les autres sortes : il se cumule
    avec elles au lieu de les remplacer.

    Un arbitrage de rapprochement (sorte ``rapprochement``) lève le
    rapprochement ambigu de son attestation : il la garde dans son émission
    (``cible`` vide) ou la déplace vers l'émission de l'attestation ``cible``.
    Il se cumule lui aussi avec les autres sortes.

    Un arbitrage d'existence retire l'émission (``existe`` faux, « n'existe
    pas »), ou lève ses doutes d'existence, attestation fragile et
    republication (``existe`` vrai). « Existe » se cumule avec les arbitrages de
    thème et les renvois à l'écoute ; entre « existe » et « n'existe pas », le
    plus récent l'emporte.

    Sa clé est l'attestation (source et identifiant dans la source), pas
    l'identifiant de l'émission, qui peut changer d'une construction à l'autre.
    """

    source: str
    source_id: str
    sorte: Sorte
    themes: frozenset[str] = frozenset()  # pour un arbitrage de thème
    date_retenue: date | None = None  # pour un arbitrage de date
    # pour un arbitrage de rapprochement : une attestation de l'émission cible,
    # ou None pour garder l'attestation où elle est
    cible: CleAttestation | None = None
    existe: bool = False  # pour un arbitrage d'existence : existe, ou non
    justification: str = ""
    date: datetime = datetime.min  # date de la décision

    @property
    def cle(self) -> CleAttestation:
        """L'attestation arbitrée."""
        return (self.source, self.source_id)


@dataclass(frozen=True)
class Doute:
    """Un point d'une émission que les sources ne permettent pas d'affirmer."""

    type: str
    emission_id: str
    dans_la_liste: bool
    source: str
    source_id: str
    detail: str
    a_ecouter: bool = False  # l'émission, dans la liste, est renvoyée à l'écoute
    # pour un rapprochement ambigu : chaque émission rivale, avec l'attestation
    # qui la désigne dans un arbitrage de rapprochement
    rivales: tuple[Rivale, ...] = ()


def construire_liste(
    attestations: list[Attestation],
    arbitrages: Sequence[Arbitrage] = (),
) -> tuple[list[Emission], list[Doute]]:
    """Rapproche les attestations, applique les arbitrages, construit la liste
    et détecte ses doutes.

    Les doutes portent sur toutes les émissions, dans la liste ou non.
    """
    groupes: list[list[Attestation]] = []
    index: _Index = defaultdict(list)
    for a in sorted(attestations, key=lambda a: a.date):
        if a.source not in SOURCES_VERIFIEES:
            _rapprocher(a, groupes, index)
    for a in attestations:
        if a.source in SOURCES_VERIFIEES:
            fiche = [g for g in groupes if any(_meme_fiche(a, b) for b in g)]
            if fiche:
                fiche[0].append(a)
                index[a.date].append(groupes.index(fiche[0]))
            else:
                _rapprocher(a, groupes, index)
    _reunir_archives_partagees(groupes)
    _rejoindre_les_archives(groupes)

    deplacements = _deplacer(groupes, _familles(arbitrages).rapprochements)
    emissions, retirees = _arbitrer([_fusionner(g) for g in groupes], arbitrages)
    emissions.sort(key=_cle_de_tri)
    _attribuer_identifiants(emissions)
    liste = [e for e in emissions if _dans_la_liste(e)]
    gardees = {a.cle for e in emissions for a in e.attestations}
    return liste, (
        _doutes(emissions, deplacements.arbitrees)
        + [_contradiction(e, a, dans_la_liste=False) for e, a in retirees]
        + _orphelins(attestations, arbitrages)
        + [
            _cible_orpheline(a, emissions, "émission cible introuvable")
            for a in deplacements.sans_cible
        ]
        + [
            _cible_orpheline(a, emissions, "émission cible arbitrée inexistante")
            for a in deplacements.deplacees
            if a.cle not in gardees
        ]
        + _arbitrages_deplaces(deplacements.parties, arbitrages, emissions)
    )


def _arbitrages_deplaces(
    parties: dict[CleAttestation, "Arbitrage"],
    arbitrages: Sequence["Arbitrage"],
    emissions: list[Emission],
) -> list[Doute]:
    """Un doute par arbitrage de thème, d'existence, d'écoute ou de date posé
    sur une attestation déplacée : il la suit dans l'émission cible et quitte
    son ancienne émission, ce qui n'est pas tranché en silence."""
    familles = _familles(arbitrages)
    emission_de = {a.cle: e for e in emissions for a in e.attestations}
    doutes = []
    for famille in (familles.decisions, familles.dates, familles.existences):
        for cle, (_ordre, arbitrage) in sorted(_derniers(famille).items()):
            if cle not in parties:
                continue
            emission = emission_de.get(cle)
            doutes.append(
                Doute(
                    type="arbitrage déplacé",
                    emission_id=emission.id if emission else "",
                    dans_la_liste=emission is not None and _dans_la_liste(emission),
                    source=arbitrage.source,
                    source_id=arbitrage.source_id,
                    detail=f"{_decision(arbitrage)}, suit l'attestation "
                    f"déplacée vers l'émission de {_cle(parties[cle].cible)}",
                )
            )
    return doutes


@dataclass
class _Deplacements:
    """Ce que les arbitrages de rapprochement ont fait des groupes."""

    # les attestations dont l'arbitrage s'applique : leur doute est levé
    arbitrees: set[CleAttestation] = field(default_factory=set)
    # les arbitrages qui ont déplacé leur attestation
    deplacees: list["Arbitrage"] = field(default_factory=list)
    # chaque attestation partie de son groupe, avec l'arbitrage qui l'a
    # déplacée (le sien, ou celui de la fiche qu'elle suit)
    parties: dict[CleAttestation, "Arbitrage"] = field(default_factory=dict)
    # les arbitrages sans effet, faute d'attestation cible
    sans_cible: list["Arbitrage"] = field(default_factory=list)


def _deplacer(
    groupes: list[list[Attestation]], rapprochements: Sequence[Arbitrage]
) -> _Deplacements:
    """Applique le dernier arbitrage de rapprochement de chaque attestation :
    une attestation déplacée rejoint le groupe de son attestation cible, comme
    si elle y avait été rapprochée. L'attestation vérifiée rattachée à une fiche
    déplacée la suit.

    Une cible elle-même déplacée est suivie jusqu'à son groupe d'arrivée : le
    résultat ne dépend pas de l'ordre des arbitrages. Un cycle de déplacements
    laisse ses attestations en place.
    """
    initial = {a.cle: g for g in groupes for a in g}
    resultat = _Deplacements()
    derniers = {cle: a for cle, (_ordre, a) in _derniers(rapprochements).items()}
    vers: dict[CleAttestation, CleAttestation] = {}
    for cle, arbitrage in derniers.items():
        if cle not in initial:
            continue  # attestation introuvable : arbitrage orphelin
        if arbitrage.cible is not None and arbitrage.cible not in initial:
            resultat.sans_cible.append(arbitrage)
            continue
        resultat.arbitrees.add(cle)
        if arbitrage.cible is not None:
            vers[cle] = arbitrage.cible

    def arrivee(
        cle: CleAttestation, vus: frozenset[CleAttestation]
    ) -> list[Attestation]:
        """Le groupe où finit l'attestation, en suivant ses déplacements."""
        if cle in vus or cle not in vers:
            return initial[cle]
        return arrivee(vers[cle], vus | {cle})

    destinations = {cle: arrivee(cle, frozenset()) for cle in vers}
    for cle, destination in destinations.items():
        depart = initial[cle]
        if destination is depart:
            continue
        attestation = next(a for a in depart if a.cle == cle)
        # une attestation vérifiée, rattachée par sa fiche, suit la fiche
        suivantes = [
            v
            for v in depart
            if v.source in SOURCES_VERIFIEES and _meme_fiche(v, attestation)
        ]
        for a in (attestation, *suivantes):
            depart.remove(a)
            destination.append(a)
            resultat.parties[a.cle] = derniers[cle]
        resultat.deplacees.append(derniers[cle])
    groupes[:] = [g for g in groupes if g]
    return resultat


def _cible_orpheline(
    arbitrage: Arbitrage, emissions: list[Emission], raison: str
) -> Doute:
    """Un arbitrage de rapprochement dont l'émission cible a disparu, faute
    d'attestation cible ou arbitrée inexistante : c'est un doute sur l'émission
    de l'attestation arbitrée, s'il en reste une."""
    emission = next(
        (e for e in emissions if any(a.cle == arbitrage.cle for a in e.attestations)),
        None,
    )
    return Doute(
        type="arbitrage orphelin",
        emission_id=emission.id if emission else "",
        dans_la_liste=emission is not None and _dans_la_liste(emission),
        source=arbitrage.source,
        source_id=arbitrage.source_id,
        detail=f"{raison} ; {_decision(arbitrage)}",
    )


def _orphelins(
    attestations: list[Attestation], arbitrages: Sequence[Arbitrage]
) -> list[Doute]:
    """Un doute par attestation arbitrée introuvable : l'arbitrage est sans effet."""
    connues = {a.cle for a in attestations}
    return [
        Doute(
            type="arbitrage orphelin",
            emission_id="",
            dans_la_liste=False,
            source=a.source,
            source_id=a.source_id,
            detail=f"attestation introuvable ; {_decision(a)}",
        )
        for famille in _familles(arbitrages)
        for cle, (_ordre, a) in sorted(_derniers(famille).items())
        if cle not in connues
    ]


class _Familles(NamedTuple):
    """Les arbitrages par point de l'émission sur lequel ils portent."""

    dates: list["Arbitrage"]
    decisions: list["Arbitrage"]  # thème, n'existe pas, écoute
    rapprochements: list["Arbitrage"]
    existences: list["Arbitrage"]  # existe


def _familles(arbitrages: Sequence[Arbitrage]) -> _Familles:
    """Les arbitrages de date, les décisions, les arbitrages de
    rapprochement et les arbitrages « existe » : chaque famille porte sur un
    point différent, et le plus récent ne l'emporte qu'au sein d'elle.
    « Existe » et « n'existe pas » se départagent à part (``_arbitrer``)."""
    return _Familles(
        dates=[a for a in arbitrages if a.sorte == "date"],
        decisions=[
            a
            for a in arbitrages
            if a.sorte not in ("date", "rapprochement") and not a.existe
        ],
        rapprochements=[a for a in arbitrages if a.sorte == "rapprochement"],
        existences=[a for a in arbitrages if a.sorte == "existence" and a.existe],
    )


def _contradiction(
    emission: Emission, arbitrage: Arbitrage, dans_la_liste: bool
) -> Doute:
    """Un arbitrage qui contredit une source vérifiée n'est pas tranché en silence
    (ADR 0003) : il s'applique, et c'est un doute."""
    return Doute(
        type="contradiction lmelp",
        emission_id=emission.id,
        dans_la_liste=dans_la_liste,
        source=arbitrage.source,
        source_id=arbitrage.source_id,
        detail=f"vérifiée livres par lmelp, {_decision(arbitrage)}",
    )


def _contredit_lmelp(emission: Emission, arbitrage: Arbitrage) -> bool:
    """L'arbitrage dit autre chose que lmelp : émission livres, qui existe."""
    return (
        _verifiee(emission)
        and arbitrage.sorte in ("thème", "existence")
        and not arbitrage.existe
        and (arbitrage.sorte == "existence" or arbitrage.themes != {"livres"})
    )


def _decision(arbitrage: Arbitrage) -> str:
    """La décision d'un arbitrage, en clair, pour le détail d'un doute."""
    if arbitrage.sorte == "existence":
        return "arbitrée existante" if arbitrage.existe else "arbitrée inexistante"
    if arbitrage.sorte == "écoute":
        return "renvoyée à l'écoute"
    if arbitrage.sorte == "date":
        return f"date arbitrée {arbitrage.date_retenue}"
    if arbitrage.sorte == "rapprochement":
        if arbitrage.cible is None:
            return "gardée dans son émission"
        return f"déplacée vers l'émission de {_cle(arbitrage.cible)}"
    return f"arbitrée {'+'.join(sorted(arbitrage.themes))}"


def _cle(attestation: CleAttestation | None) -> str:
    """Une attestation en clair, ``source:source_id``."""
    return ":".join(attestation) if attestation else ""


def _derniers(
    arbitrages: Sequence[Arbitrage],
) -> dict[CleAttestation, tuple[int, Arbitrage]]:
    """Le plus récent arbitrage de chaque attestation, avec son rang.

    Le rang ordonne les arbitrages par date, puis par position dans la
    séquence : à date égale, le dernier l'emporte.
    """
    chronologie = sorted(arbitrages, key=lambda a: a.date)  # tri stable
    return {a.cle: (rang, a) for rang, a in enumerate(chronologie)}


def _arbitrer(
    emissions: list[Emission], arbitrages: Sequence[Arbitrage]
) -> tuple[list[Emission], list[tuple[Emission, Arbitrage]]]:
    """Applique à chaque émission le dernier arbitrage de ses attestations, et
    le dernier arbitrage de date.

    Un arbitrage de thème remplace exactement ses thèmes ; un arbitrage
    « n'existe pas » la retire de l'ensemble des émissions, sauf si un
    arbitrage « existe » plus récent l'annule ; un arbitrage « existe » se
    cumule avec le dernier arbitrage de thème ou renvoi à l'écoute ; un renvoi
    à l'écoute lui laisse les thèmes de ses sources ; un arbitrage de date lui
    donne la date retenue. Rend les émissions gardées, et les émissions vérifiées
    retirées avec leur arbitrage.
    """
    familles = _familles(arbitrages)
    par_attestation = _derniers(familles.decisions)
    date_par_attestation = _derniers(familles.dates)
    existence_par_attestation = _derniers(
        [a for a in arbitrages if a.sorte == "existence"]
    )
    # sous un arbitrage « existe », « n'existe pas » est sans effet
    hors_existence = _derniers(
        [a for a in familles.decisions if a.sorte != "existence"]
    )
    gardees: list[Emission] = []
    retirees: list[tuple[Emission, Arbitrage]] = []
    for emission in emissions:
        dates_arbitrees = [
            date_par_attestation[a.cle]
            for a in emission.attestations
            if a.cle in date_par_attestation
        ]
        if dates_arbitrees:
            _ordre, arbitrage_date = max(dates_arbitrees, key=lambda r: r[0])
            if arbitrage_date.date_retenue is not None:
                emission.date = arbitrage_date.date_retenue
            emission.arbitrage_date = arbitrage_date
        existences = [
            existence_par_attestation[a.cle]
            for a in emission.attestations
            if a.cle in existence_par_attestation
        ]
        decisions = par_attestation
        if existences:
            _ordre, existence = max(existences, key=lambda r: r[0])
            if existence.existe:
                emission.arbitrage_existence = existence
                decisions = hors_existence
        siens = [decisions[a.cle] for a in emission.attestations if a.cle in decisions]
        if not siens:
            gardees.append(emission)
            continue
        _ordre, arbitrage = max(siens, key=lambda r: r[0])
        if arbitrage.sorte == "existence":
            if _contredit_lmelp(emission, arbitrage):
                retirees.append((emission, arbitrage))
            continue
        if arbitrage.sorte == "thème":
            emission.themes = arbitrage.themes
        emission.arbitrage = arbitrage
        gardees.append(emission)
    return gardees, retirees


def _doutes(
    emissions: list[Emission], arbitrees: AbstractSet[CleAttestation]
) -> list[Doute]:
    """Les doutes des émissions, dans la liste ou non : rapprochement, date
    (désaccord, jour inhabituel), collision, thème, republication, fragilité,
    absence de lmelp.

    Un arbitrage de rapprochement lève le rapprochement ambigu des attestations
    ``arbitrees``."""
    doutes: list[Doute] = []
    # la première diffusion de la dernière émission vérifiée, pas sa publication
    derniere_verifiee = max(
        (e.date for e in emissions if _verifiee(e)),
        default=None,
    )
    par_jour: _Index = defaultdict(list)
    for i, e in enumerate(emissions):
        for a in e.attestations:
            par_jour[a.date].append(i)
    for emission in emissions:
        dans_la_liste = _dans_la_liste(emission)

        def ajouter(
            type_: str,
            detail: str,
            attestation: Attestation | None = None,
            emission: Emission = emission,
            dans_la_liste: bool = dans_la_liste,
            rivales: tuple[Rivale, ...] = (),
        ) -> None:
            doutes.append(
                Doute(
                    type=type_,
                    emission_id=emission.id,
                    dans_la_liste=dans_la_liste,
                    source=attestation.source if attestation else "",
                    source_id=attestation.source_id if attestation else "",
                    detail=detail,
                    a_ecouter=dans_la_liste and emission.a_ecouter,
                    rivales=rivales,
                )
            )

        # Rapprochement et date.
        for a in emission.attestations:
            if a.source in SOURCES_VERIFIEES:
                # rattachée par sa fiche, sans ambiguïté ; sinon par la date
                if not any(_meme_fiche(a, b) for b in emission.attestations):
                    ajouter("sans fiche radiofrance", f"aucune fiche {a.url}", a)
                continue
            if a.nature_date == "publication":
                # rattachée par son archive : sa date ne la rapproche de rien
                continue
            rivales = tuple(
                (emissions[i].id, attestation_stable(emissions[i]).cle)
                for i in _proches(a.date, par_jour)
                if emissions[i] is not emission
                and _rapprochable(a, emissions[i].attestations)
            )
            if rivales and a.cle not in arbitrees:
                ajouter(
                    "rapprochement ambigu",
                    f"rapprochable aussi de {', '.join(i for i, _ in rivales)}",
                    a,
                    rivales=rivales,
                )
        # Un arbitrage de date lève les doutes de date.
        dates = sorted(set(_dates_de_diffusion(emission.attestations)))
        if (
            emission.arbitrage_date is None
            and (dates[-1] - dates[0]).days > 1
            and not _seule_au_jour_habituel(emission.date, dates)
        ):
            ajouter(
                "désaccord de date",
                ", ".join(
                    f"{a.source}:{a.date.isoformat()}"
                    for a in emission.attestations
                    if a.nature_date == "première diffusion"
                ),
            )
        habituel = jour_habituel(emission.date)
        if (
            emission.arbitrage_date is None
            and habituel is not None
            and emission.date.weekday() != habituel
        ):
            ajouter(
                "jour inhabituel",
                f"un {JOURS[emission.date.weekday()]}, "
                f"quand l'émission passe le {JOURS[habituel]}",
            )
        if emission.id != emission.date.isoformat():
            ajouter("collision", f"une autre émission le même jour : {emission.date}")

        # Une source vérifiée lève les doutes de thème et d'existence (ADR 0003).
        if _verifiee(emission):
            if emission.arbitrage and _contredit_lmelp(emission, emission.arbitrage):
                doutes.append(
                    _contradiction(emission, emission.arbitrage, dans_la_liste)
                )
            continue
        # Une émission hommage sort de la liste, mais son absence de lmelp,
        # qu'elle explique, reste tracée.
        if (
            (dans_la_liste or HOMMAGE in emission.themes)
            and derniere_verifiee
            and LMELP_COMPLET_DEPUIS <= emission.date <= derniere_verifiee
        ):
            ajouter(
                "absente de lmelp",
                f"lmelp est complet depuis le {LMELP_COMPLET_DEPUIS:%d/%m/%Y}"
                " pour les émissions littéraires",
            )
        # Un arbitrage de thème lève les doutes de thème.
        if emission.arbitrage is None or emission.arbitrage.sorte != "thème":
            if not emission.themes:
                ajouter("thème inconnu", "aucune source ne donne de thème")
            divergence = _themes_divergents(emission.attestations)
            if divergence:
                ajouter("thèmes divergents", divergence)
        # Un arbitrage « existe » lève les doutes d'existence.
        if emission.arbitrage_existence is not None:
            continue
        for a in emission.attestations:
            # une date de publication ne date pas l'émission : son fichier se
            # compare à la date de l'émission
            reference = (
                a.date if a.nature_date == "première diffusion" else (emission.date)
            )
            dates_des_fichiers = sorted(
                {
                    f.date
                    for e in a.enregistrements
                    if (f := lire_nom_fichier(e.url))
                    and abs((f.date - reference).days) > ECART_REPUBLICATION_JOURS
                }
            )
            if dates_des_fichiers:
                ajouter(
                    "republication",
                    f"daté du {a.date}, enregistrement du "
                    + ", ".join(str(jour) for jour in dates_des_fichiers),
                    a,
                )
        fragilite = _fragilite(emission.attestations)
        if fragilite:
            ajouter("attestation fragile", fragilite)
    return doutes


# L'attestation la plus stable d'une émission la désigne dans un arbitrage : la
# notice INA, sinon la fiche radiofrance.fr, sinon les autres sources dans cet ordre.
STABILITE = ("ina", "radiofrance", "lmelp", "anciennes_listes", "wayback_podcast")


def attestation_stable(emission: Emission) -> Attestation:
    """L'attestation de l'émission à laquelle attacher un arbitrage, ou par
    laquelle un arbitrage de rapprochement la désigne."""

    def rang(a: Attestation) -> tuple[int, str]:
        return (_rang(a.source, STABILITE), a.source_id)

    return min(emission.attestations, key=rang)


def _verifiee(emission: Emission) -> bool:
    """L'émission est attestée par une source vérifiée."""
    return any(a.source in SOURCES_VERIFIEES for a in emission.attestations)


def _fragilite(groupe: list[Attestation]) -> str | None:
    """Pourquoi l'existence de l'émission est fragile, ou None.

    Ni un extrait ni un fichier conservé par la Wayback Machine ne décrit une
    émission diffusée en entier : une émission qu'eux seuls attestent peut être
    une republication ou un fragment publié à part.
    """
    if all(a.extrait for a in groupe):
        return "attestée seulement par des extraits"
    if all(a.source == "wayback_podcast" for a in groupe):
        return "attestée seulement par la Wayback Machine"
    if all(a.extrait or a.source == "wayback_podcast" for a in groupe):
        return "attestée seulement par des extraits et la Wayback Machine"
    return None


def _themes_divergents(groupe: list[Attestation]) -> str | None:
    """Le détail d'une divergence de thèmes entre attestations, ou None.

    Les attestations de l'émission entière divergent si elles ne donnent pas
    les mêmes thèmes ; un extrait diverge s'il porte un thème qu'aucune ne
    donne. Des extraits aux thèmes différents (un livre, un film) décrivent
    une émission mixte, sans divergence.
    """
    avec_theme = [a for a in groupe if a.themes]
    entieres = {a.themes for a in avec_theme if not a.extrait}
    themes_entiers = frozenset().union(*entieres)
    divergent = len(entieres) > 1 or any(
        a.extrait and entieres and not a.themes <= themes_entiers for a in avec_theme
    )
    if not divergent:
        return None
    return ", ".join(
        f"{a.source}:{'+'.join(sorted(a.themes))}" + (" (extrait)" if a.extrait else "")
        for a in avec_theme
    )


ECART_MAX_JOURS = 3
# Un enregistrement daté à plus de trois jours de son attestation signale une
# émission remise en ligne plus tard (republication), pas un simple décalage.
ECART_REPUBLICATION_JOURS = 3

# Sources dont chaque attestation a été vérifiée à la main (ADR 0003) : elles se
# rattachent à l'émission par leur fiche radiofrance.fr, et leur thème fait foi.
SOURCES_VERIFIEES = frozenset({"lmelp"})
# lmelp est complet depuis cette date : une émission de la liste qui n'y figure
# pas, jusqu'à sa dernière émission, est un doute.
LMELP_COMPLET_DEPUIS = date(2017, 1, 1)
# Le thème d'une émission sans critique nouvelle, consacrée au Masque ou à l'un
# de ses critiques : il ne se cumule avec aucun autre et sort l'émission de la liste.
HOMMAGE = "hommage"

# Pour chaque champ, les sources par ordre de priorité décroissante (issue #2).
PRIORITES: dict[str, tuple[str, ...]] = {
    "date": ("radiofrance", "ina", "anciennes_listes", "wayback_podcast"),
    "titre": ("radiofrance", "ina"),
    "description": ("radiofrance", "ina"),
    "chaine": ("ina", "radiofrance"),
    "heure": ("ina", "radiofrance"),
    "duree": ("ina", "radiofrance"),
    "animateur": ("radiofrance", "ina"),
}

# Mandats connus à l'année près (Wikipédia). Les années de transition (1970,
# 1989, 2023) sont absentes : l'animateur n'y est pas déduit.
MANDATS: tuple[tuple[int, int, str], ...] = (
    (1955, 1969, "Michel Polac, François-Régis Bastide"),
    (1971, 1981, "François-Régis Bastide"),
    (1982, 1988, "Pierre Bouteiller"),
    (1990, 2022, "Jérôme Garcin"),
    (2024, 9999, "Rebecca Manzoni"),
)


# Le jour de la semaine où l'émission passe habituellement (lundi = 0), par
# période. Les années de changement (1957, 1964-1965) n'en ont pas.
JOURS_DE_DIFFUSION: tuple[tuple[int, int, int], ...] = (
    (1955, 1956, 6),  # dimanche
    (1958, 1963, 3),  # jeudi
    (1966, 9999, 6),  # dimanche
)
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def jour_habituel(jour: date) -> int | None:
    """Le jour de diffusion de la période (lundi = 0), ou None en transition."""
    for debut, fin, jour_semaine in JOURS_DE_DIFFUSION:
        if debut <= jour.year <= fin:
            return jour_semaine
    return None


def au_jour_habituel(jour: date) -> bool:
    """La date tombe le jour de diffusion habituel de sa période."""
    return jour.weekday() == jour_habituel(jour)


def dates_candidates(emission: Emission) -> dict[date, list[str]]:
    """Les dates de première diffusion que donnent les sources de l'émission,
    dans l'ordre, chacune avec ses sources : les choix d'un arbitrage de date."""
    sources: defaultdict[date, set[str]] = defaultdict(set)
    for a in _datantes(emission.attestations):
        sources[a.date].add(a.source)
    return {jour: sorted(sources[jour]) for jour in sorted(sources)}


def _seule_au_jour_habituel(retenue: date, dates: list[date]) -> bool:
    """La date retenue est la seule des sources à tomber le jour habituel : le
    désaccord de date vient d'attestations voisines (rediffusions, publications)."""
    return [d for d in dates if au_jour_habituel(d)] == [retenue]


def animateur_du(jour: date) -> str | None:
    """L'animateur déduit de la date, ou None pour une année de transition."""
    for debut, fin, animateur in MANDATS:
        if debut <= jour.year <= fin:
            return animateur
    return None


# Champs qu'un extrait ne renseigne jamais : il ne couvre qu'un fragment.
_JAMAIS_D_UN_EXTRAIT = {"duree"}
# Une archive au moins aussi longue que 90 % de la diffusion (durée INA) est
# l'émission entière, pas un extrait.
_PART_MIN_ENTIERE = 0.9


def _valeur(champ: str, groupe: list[Attestation]) -> Any:
    """La valeur du champ dans la source la plus prioritaire qui le renseigne.

    Une attestation de l'émission entière passe avant un extrait.
    """
    ordre = PRIORITES[champ]
    candidats = [a for a in groupe if not (a.extrait and champ in _JAMAIS_D_UN_EXTRAIT)]
    if champ == "date" and any(a.nature_date == "première diffusion" for a in groupe):
        candidats = [a for a in candidats if a.nature_date == "première diffusion"]

    for a in sorted(candidats, key=lambda a: (a.extrait, _rang(a.source, ordre))):
        valeur = getattr(a, champ)
        if valeur:
            return valeur
    return None


def _rang(source: str, ordre: tuple[str, ...]) -> int:
    """Le rang de la source dans l'ordre de priorité ; inconnue, elle passe après."""
    return ordre.index(source) if source in ordre else len(ordre)


def _dans_la_liste(emission: Emission) -> bool:
    """Thème incluant les livres, ou inconnu (ADR 0002)."""
    return not emission.themes or "livres" in emission.themes


def _cle_de_tri(emission: Emission) -> tuple[date, bool, list[str], str]:
    """Ordre déterministe, indépendant de l'ordre d'arrivée des attestations.

    À date égale, une émission de la liste passe avant une émission écartée :
    elle garde ainsi la date seule comme identifiant.
    """
    return (
        emission.date,
        not _dans_la_liste(emission),
        sorted(emission.themes),
        min(f"{a.source}:{a.source_id}" for a in emission.attestations),
    )


def _attribuer_identifiants(liste: list[Emission]) -> None:
    """La date de première diffusion, suffixée en cas de collision (ADR 0001)."""
    vus: dict[str, int] = {}
    for emission in liste:
        base = emission.date.isoformat()
        rang = vus.get(base, 0)
        vus[base] = rang + 1
        emission.id = base if rang == 0 else f"{base}-{chr(ord('a') + rang)}"


def _secondes(duree: str) -> int:
    """``HH:MM:SS`` en secondes."""
    h, m, s = (int(x) for x in duree.split(":"))
    return h * 3600 + m * 60 + s


def _archives_entieres(groupe: list[Attestation]) -> list[Attestation]:
    """Les extraits d'archive qui couvrent en fait toute la diffusion INA.

    Ils redeviennent des attestations de l'émission entière, et leurs
    enregistrements des intégraux : la règle de type par archive (ITEMA)
    étend ce changement aux fichiers des autres sources.
    """
    diffusion = max(
        (_secondes(a.duree) for a in groupe if a.source == "ina" and a.duree),
        default=None,
    )
    if diffusion is None:
        return groupe
    seuil = _PART_MIN_ENTIERE * diffusion
    entieres = {
        _itema(e.url)
        for a in groupe
        if a.extrait and a.duree and _secondes(a.duree) >= seuil
        for e in a.enregistrements
        if _archive(e.url)
    } - {None}
    if not entieres:
        return groupe

    def entiere(a: Attestation) -> Attestation:
        if not any(_itema(e.url) in entieres for e in a.enregistrements):
            return a
        return replace(
            a,
            extrait=False,
            enregistrements=tuple(
                replace(e, type="intégral") if _itema(e.url) in entieres else e
                for e in a.enregistrements
            ),
        )

    return [entiere(a) for a in groupe]


def _fusionner(groupe: list[Attestation]) -> Emission:
    """L'émission d'un groupe d'attestations rapprochées, champ par champ."""
    groupe = _archives_entieres(groupe)
    jour: date = _valeur("date", groupe)
    return Emission(
        id=jour.isoformat(),
        date=jour,
        themes=_themes(groupe),
        titre=_valeur("titre", groupe),
        description=_valeur("description", groupe),
        chaine=_valeur("chaine", groupe),
        heure=_valeur("heure", groupe),
        duree=_valeur("duree", groupe),
        animateur=_valeur("animateur", groupe) or animateur_du(jour),
        attestations=groupe,
        enregistrements=_enregistrements(groupe),
    )


def _archive(url: str) -> bool:
    """Un fichier d'une série d'archives : lettre ``E`` du code de publication."""
    return re.search(r"\d{4}F4007E\d+", url) is not None


def _itema(url: str) -> str | None:
    """L'identifiant d'archive Radio France d'un fichier audio, s'il y figure."""
    m = re.search(r"ITEMA_\d+", url)
    return m.group(0) if m else None


def _segment(url: str) -> str | None:
    """L'archive (ITEMA) et le segment (``2025F4007S0215``) d'un fichier audio.

    Une même archive couvre parfois l'émission entière et ses extraits : seul
    le segment les distingue. Il est le même pour tous les encodages du fichier.
    """
    m = re.search(r"ITEMA_\d+(-\d{4}F\d+[A-Z]\d+)?", url)
    return m.group(0) if m else None


def _enregistrements(groupe: list[Attestation]) -> list[Enregistrement]:
    """Les enregistrements de toutes les sources, typés par segment d'archive.

    Une source qui sait qu'un segment est un extrait (radiofrance.fr connaît
    la durée) l'emporte sur une autre qui ne voit que le nom du fichier. La
    durée d'un fichier vaut pour ses autres encodages (``-22.mp3``, ``-27.m4a``).
    """
    tous = [e for a in groupe for e in a.enregistrements]
    extraits = {_segment(e.url) for e in tous if e.type == "extrait"} - {None}
    durees: dict[str, str] = {}
    for e in tous:
        if e.duree:
            durees.setdefault(_fichier(e.url), e.duree)
    return list(
        dict.fromkeys(
            replace(
                e,
                type="extrait" if _segment(e.url) in extraits else e.type,
                duree=e.duree or durees.get(_fichier(e.url)),
            )
            for e in tous
        )
    )


def _fichier(url: str) -> str:
    """Le nom d'un fichier audio sans son suffixe d'encodage (``-27.m4a``) :
    le même pour tous ses encodages."""
    nom = url.rsplit("/", 1)[-1]
    return re.sub(r"(-\d+)?\.\w+$", "", nom)


def _themes(groupe: list[Attestation]) -> frozenset[str]:
    """Les thèmes de toutes les attestations, extraits compris.

    Ceux d'une source vérifiée font foi, sans cumul avec les autres.
    """
    verifiees = [a for a in groupe if a.source in SOURCES_VERIFIEES]
    return frozenset().union(*(a.themes for a in verifiees or groupe))


# Les positions des groupes (ou des émissions) par date de leurs attestations.
_Index = defaultdict[date, list[int]]


def _proches(jour: date, index: _Index) -> list[int]:
    """Les positions, dans l'ordre, de ce qui a une attestation à moins de
    ECART_MAX_JOURS jours : les seuls candidats possibles d'un rapprochement.

    Indexer toutes les dates d'attestation, et pas seulement celles de
    diffusion, donne un sur-ensemble des candidats : ``_rapprochable`` tranche.
    """
    return sorted(
        {
            i
            for ecart in range(-ECART_MAX_JOURS, ECART_MAX_JOURS + 1)
            for i in index.get(jour + timedelta(days=ecart), ())
        }
    )


def _rapprocher(
    a: Attestation, groupes: list[list[Attestation]], index: _Index
) -> None:
    """Ajoute l'attestation au groupe le plus proche, ou en crée un."""
    candidats = [i for i in _proches(a.date, index) if _rapprochable(a, groupes[i])]
    if candidats:
        position = min(candidats, key=lambda i: _ecart(a, groupes[i]))
        groupes[position].append(a)
    else:
        position = len(groupes)
        groupes.append([a])
    index[a.date].append(position)


def _reunir_archives_partagees(groupes: list[list[Attestation]]) -> None:
    """Réunit les groupes du même jour dont des enregistrements partagent une
    archive (ITEMA) : ils sont une seule émission.

    Une fiche par livre étiquetée d'un thème incompatible avec l'émission n'a
    pas pu y être rapprochée ; son archive la rattache. À des dates
    différentes, une archive partagée signale une rediffusion : les groupes
    restent distincts.
    """
    parent = list(range(len(groupes)))

    def racine(i: int) -> int:
        while parent[i] != i:
            i = parent[i]
        return i

    premier: dict[tuple[date, str], int] = {}
    for i, groupe in enumerate(groupes):
        for jour in _dates_de_diffusion(groupe):
            for a in groupe:
                for e in a.enregistrements:
                    if (itema := _itema(e.url)) is None:
                        continue
                    j = premier.setdefault((jour, itema), i)
                    parent[max(racine(i), racine(j))] = min(racine(i), racine(j))
    for i in range(len(groupes)):
        if (r := racine(i)) != i:
            groupes[r].extend(groupes[i])
            groupes[i] = []
    groupes[:] = [g for g in groupes if g]


def _rejoindre_les_archives(groupes: list[list[Attestation]]) -> None:
    """Déplace vers son émission une attestation dont l'enregistrement est
    l'archive (ITEMA) d'une autre émission, datée du jour de ce fichier.

    Le fichier est daté à plus de ECART_REPUBLICATION_JOURS jours de
    l'attestation : la date de la source est fausse, ou celle d'une remise en
    ligne. Dans l'émission qu'elle rejoint, cette date devient une date de
    publication, qui ne date pas l'émission.

    Une fiche qu'une source vérifiée rattache à son émission y reste (ADR
    0003). Une émission dont toutes les attestations partiraient n'est pas
    fusionnée avec une autre : une émission qui republie l'archive d'une autre
    reste distincte (voir ``_reunir_archives_partagees``).
    """
    jours = [_valeur("date", groupe) for groupe in groupes]
    par_archive: defaultdict[str, set[int]] = defaultdict(set)
    for i, groupe in enumerate(groupes):
        for a in groupe:
            for e in a.enregistrements:
                if (itema := _itema(e.url)) is not None:
                    par_archive[itema].add(i)

    def cibles(a: Attestation, i: int) -> set[int]:
        if any(_meme_fiche(b, a) for b in groupes[i] if b.source in SOURCES_VERIFIEES):
            return set()
        return {
            j
            for e in a.enregistrements
            if (f := lire_nom_fichier(e.url))
            and abs((f.date - a.date).days) > ECART_REPUBLICATION_JOURS
            and (itema := _itema(e.url)) is not None
            for j in par_archive[itema]
            if j != i and jours[j] == f.date
        }

    departs: list[tuple[int, Attestation, int]] = []
    for i, groupe in enumerate(groupes):
        partantes = [(a, c) for a in groupe if len(c := cibles(a, i)) == 1]
        if len(partantes) < len(groupe):
            departs += [(i, a, min(c)) for a, c in partantes]
    for i, a, j in departs:
        groupes[i].remove(a)
        groupes[j].append(replace(a, nature_date="publication"))


def _meme_fiche(verifiee: Attestation, b: Attestation) -> bool:
    """``b`` est la fiche radiofrance.fr de l'attestation vérifiée (même URL)."""
    return b.source not in SOURCES_VERIFIEES and b.url == verifiee.url


def _datantes(groupe: list[Attestation]) -> list[Attestation]:
    """Les attestations qui datent la première diffusion, à défaut toutes."""
    diffusion = [a for a in groupe if a.nature_date == "première diffusion"]
    return diffusion or groupe


def _dates_de_diffusion(groupe: list[Attestation]) -> list[date]:
    """Les dates de première diffusion du groupe, à défaut ses autres dates."""
    return [a.date for a in _datantes(groupe)]


def _ecart(a: Attestation, groupe: list[Attestation]) -> int:
    """L'écart en jours entre l'attestation et la date la plus proche du groupe."""
    return min(abs((a.date - jour).days) for jour in _dates_de_diffusion(groupe))


def _rapprochable(a: Attestation, groupe: list[Attestation]) -> bool:
    """Même date, ou écart d'au plus 3 jours avec des thèmes compatibles."""
    if _ecart(a, groupe) > ECART_MAX_JOURS:
        return False
    themes = _themes(groupe)
    return not a.themes or not themes or bool(a.themes & themes)
