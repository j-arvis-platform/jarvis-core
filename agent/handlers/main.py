"""Jarvis Principal V2 — 1 agent, N personas narratives, M skills.

C'est LE point d'entrée unique. Pas de multi-agents.
Les personas (Léa, Claire, Hugo...) sont une couche UX dans le prompt système.
Le routage de modèle (Haiku/Sonnet/Opus) est automatique selon complexité.
"""

import os
import json
import logging
from datetime import datetime, timezone

from anthropic import Anthropic
from dotenv import load_dotenv

from agent.core.config import load_tenant_config, load_personas
from agent.core.supabase_client import get_supabase, insert_row, query_table
from agent.integrations.telegram import TelegramBot, TelegramError, build_from_env
from agent.routing.model_router import get_model, classify_complexity

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("jarvis")

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Tu es Jarvis, l'assistant IA d'une entreprise française.

## Identité
Tu es UN SEUL agent. Tu utilises des personas narratives pour adapter ton style
selon le domaine de la question, mais tu restes toujours Jarvis.

## Personas narratives (style, pas entités)
{personas_block}

## Règles absolues
1. Tu ES Jarvis. Pas de "je vais transférer à Hugo" — c'est toi qui réponds.
2. Si un client demande "passer à Hugo", tu réponds naturellement en mode compta.
3. Adapte ton style (chaleureux pour commercial, technique pour terrain, etc.)
   mais JAMAIS de rupture d'identité.
4. Langue : français, sauf si le contexte exige l'anglais.
5. Si tu ne sais pas, dis-le. Ne fabrique jamais de données.
6. Pour toute action engageante (devis, email client, publication), demande
   validation à l'humain via la file humaine.

## Données entreprise
{tenant_block}

## Date du jour
{today}
"""


def build_system_prompt(tenant_id: str) -> str:
    """Construit le prompt système avec les données du tenant."""
    try:
        config = load_tenant_config(tenant_id)
        personas = load_personas(tenant_id)
    except FileNotFoundError:
        config = {}
        personas = {}

    # Bloc personas
    if personas and "personas" in personas:
        lines = []
        for p in personas["personas"]:
            lines.append(f"- **{p['nom']}** ({p['domaine']}) : {p['style']}")
        personas_block = "\n".join(lines)
    else:
        personas_block = (
            "- **Léa** (commercial) : chaleureuse, pédagogue, relances douces\n"
            "- **Claire** (admin client) : posée, méthodique, rassurante\n"
            "- **Hugo** (compta) : précis, chiffres exacts, conformité\n"
            "- **Sofia** (admin entreprise) : rigoureuse, deadlines, URSSAF\n"
            "- **Adam** (terrain) : direct, technique, solutions concrètes\n"
            "- **Yasmine** (marketing) : créative, tendances, engagement\n"
            "- **Noah** (RH) : bienveillant, droit du travail, discret\n"
            "- **Elias** (juridique) : fantôme, précis, références légales"
        )

    # Bloc tenant
    tenant = config.get("tenant", {})
    tenant_block = (
        f"- Entreprise : {tenant.get('name', 'Non configuré')}\n"
        f"- SIRET : {tenant.get('siret', 'N/A')}\n"
        f"- TVA : {tenant.get('tva', 'N/A')}\n"
        f"- Zone : {tenant.get('zone_intervention', 'N/A')}\n"
        f"- Certifications : {', '.join(tenant.get('certifications', []))}"
    )

    today = datetime.now(timezone.utc).strftime("%A %d %B %Y")

    return SYSTEM_PROMPT.format(
        personas_block=personas_block,
        tenant_block=tenant_block,
        today=today,
    )


class JarvisAgent:
    """Agent Jarvis V2 — point d'entrée unique."""

    def __init__(self, tenant_id: str = "elexity34"):
        self.tenant_id = tenant_id
        self.system_prompt = build_system_prompt(tenant_id)
        self.conversation: list[dict] = []
        self._telegram: TelegramBot | None = None
        logger.info(f"Jarvis initialisé pour tenant: {tenant_id}")

    @property
    def telegram(self) -> TelegramBot:
        """Lazy-init du wrapper Telegram (si TELEGRAM_BOT_TOKEN_JARVIS défini)."""
        if self._telegram is None:
            self._telegram = build_from_env()
        return self._telegram

    def notify_admin(self, message: str, parse_mode: str | None = "HTML") -> dict:
        """Envoie une notification Telegram à l'admin (Hamid).

        Blocking wrapper autour de l'API async de TelegramBot.
        Swallow-and-log en cas d'erreur pour ne pas casser le flow agent.
        """
        import asyncio

        try:
            return asyncio.run(
                self.telegram.send_message(message, parse_mode=parse_mode)
            )
        except TelegramError as e:
            logger.error(f"notify_admin: échec Telegram — {e}")
            return {}
        except Exception as e:
            logger.error(f"notify_admin: erreur inattendue — {e}")
            return {}

    def respond(self, user_message: str) -> str:
        """Traite un message utilisateur et retourne la réponse de Jarvis."""
        model = get_model(user_message)
        complexity = classify_complexity(user_message)
        logger.info(f"Message reçu — complexité: {complexity.value}, modèle: {model}")

        self.conversation.append({"role": "user", "content": user_message})

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.conversation,
        )

        assistant_message = response.content[0].text
        self.conversation.append({"role": "assistant", "content": assistant_message})

        logger.info(
            f"Réponse générée — {response.usage.input_tokens} in / "
            f"{response.usage.output_tokens} out tokens"
        )

        return assistant_message

    def add_to_human_queue(self, context: dict, proposition: str,
                           urgence: str = "normale") -> dict:
        """Ajoute une décision à la file humaine Supabase."""
        row = {
            "contexte": json.dumps(context, ensure_ascii=False),
            "proposition": proposition,
            "urgence": urgence,
            "decision": "pending",
        }
        result = insert_row("file_humaine", row, self.tenant_id)
        logger.info(f"File humaine: nouvelle entrée ({urgence}) — {proposition[:80]}")
        return result.data[0] if result.data else {}

    def get_pending_tasks(self) -> list:
        """Récupère les tâches en attente depuis Supabase."""
        result = query_table("taches", {"statut": "todo"}, self.tenant_id)
        return result.data if result.data else []

    def reset_conversation(self):
        """Remet à zéro l'historique de conversation."""
        self.conversation = []
        logger.info("Conversation réinitialisée")


def main():
    """Point d'entrée CLI pour test rapide."""
    tenant_id = os.environ.get("JARVIS_TENANT_ID", "elexity34")
    jarvis = JarvisAgent(tenant_id=tenant_id)

    print("=" * 60)
    print(f"  J-ARVIS V2 — Tenant: {tenant_id}")
    print(f"  Tapez 'quit' pour quitter, 'reset' pour réinitialiser")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n[Vous] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Au revoir.")
            break
        if user_input.lower() == "reset":
            jarvis.reset_conversation()
            print("[Conversation réinitialisée]")
            continue

        reply = jarvis.respond(user_input)
        print(f"\n[Jarvis] {reply}")


if __name__ == "__main__":
    main()
