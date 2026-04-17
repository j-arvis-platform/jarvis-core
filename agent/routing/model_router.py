"""Routage intelligent des modèles Claude selon complexité.

Règle : économiser les tokens en utilisant le bon modèle pour chaque tâche.
- FAST (Haiku) : classification, extraction, queries simples
- STANDARD (Sonnet) : rédaction emails, devis, rapports
- COMPLEX (Opus) : décisions stratégiques, analyses multi-sources
"""

from enum import Enum


class Complexity(Enum):
    FAST = "fast"
    STANDARD = "standard"
    COMPLEX = "complex"


MODEL_MAP = {
    Complexity.FAST: "claude-haiku-4-5-20251001",
    Complexity.STANDARD: "claude-sonnet-4-6",
    Complexity.COMPLEX: "claude-opus-4-6",
}

# Mots-clés pour classification automatique
FAST_KEYWORDS = [
    "classe", "trie", "catégorise", "extrait", "quel type",
    "oui ou non", "vrai ou faux", "résume en 1 ligne",
]

COMPLEX_KEYWORDS = [
    "stratégie", "analyse complète", "décision", "compare et recommande",
    "plan d'action", "audit", "évalue les risques", "négocie",
]


def classify_complexity(message: str) -> Complexity:
    """Détermine la complexité d'un message pour choisir le modèle."""
    msg_lower = message.lower()

    if any(kw in msg_lower for kw in COMPLEX_KEYWORDS):
        return Complexity.COMPLEX

    if any(kw in msg_lower for kw in FAST_KEYWORDS):
        return Complexity.FAST

    return Complexity.STANDARD


def get_model(message: str) -> str:
    """Retourne l'ID du modèle Claude adapté au message."""
    complexity = classify_complexity(message)
    return MODEL_MAP[complexity]
