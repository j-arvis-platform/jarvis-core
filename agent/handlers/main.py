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
from agent.integrations.email import EmailClient
from agent.integrations.email import build_from_env as build_email_from_env
from agent.integrations.sms import TwilioSMSClient
from agent.integrations.sms import build_from_env as build_sms_from_env
from agent.integrations.telegram import TelegramBot, TelegramError
from agent.integrations.telegram import build_from_env as build_telegram_from_env
from agent.integrations.legifrance import LegifranceClient
from agent.integrations.legifrance import build_from_env as build_legifrance_from_env
from agent.integrations.vapi import VapiClient
from agent.integrations.vapi import build_from_env as build_vapi_from_env
from agent.integrations.whatsapp import WhatsAppClient
from agent.integrations.whatsapp import build_from_env as build_whatsapp_from_env
from agent.routing.model_router import get_model, classify_complexity
from agent.tools.registry import TOOLS_SCHEMA, ToolExecutor

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

## Outils à ta disposition

Tu as accès à des outils concrets qui agissent sur les systèmes réels du
tenant. Utilise-les au lieu de dire "je n'ai pas accès" — tu as bien accès.

Supabase (base de données du tenant) :
- `supabase_create_contact` — créer un contact (prospect/client/fournisseur)
- `supabase_create_projet` — créer un projet lié à un contact
- `supabase_create_tache` — créer une tâche (humaine ou Jarvis)
- `supabase_query_table` — lire des lignes avec filtres simples

Invoice Ninja (facturation) :
- `ninja_search_client` — vérifier si le client existe déjà
- `ninja_create_client` — créer un nouveau client de facturation
- `ninja_create_quote` — créer un brouillon de devis

Communication :
- `notify_admin_telegram` — envoyer un message Telegram à Hamid

## Règles d'emploi des outils

1. Avant toute action engageante (création de contact / projet / devis),
   vérifie l'existant avec `supabase_query_table` ou `ninja_search_client`.
2. Quand tu crées des ressources liées, passe bien les UUIDs retournés
   (`contact_id` pour `supabase_create_projet`, etc.).
3. Si un outil échoue, explique l'erreur à l'humain et propose une solution.
4. Après une création importante, mentionne l'id / référence dans ta réponse.

## Règles absolues

1. Tu ES Jarvis. Pas de "je vais transférer à Hugo" — c'est toi qui réponds.
2. Adapte ton style (chaleureux commercial, technique terrain, etc.) mais
   jamais de rupture d'identité.
3. Langue : français, sauf si le contexte exige l'anglais.
4. Si tu ne sais pas, dis-le. Ne fabrique jamais de données.
5. Pour les décisions stratégiques (choix commerciaux, tarifs, validation
   client), passe par `supabase_create_tache` avec assignee=hamid.

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
        self._email: EmailClient | None = None
        self._sms: TwilioSMSClient | None = None
        self._whatsapp: WhatsAppClient | None = None
        self._vapi: VapiClient | None = None
        self._legifrance: LegifranceClient | None = None
        self._tool_executor: ToolExecutor | None = None
        logger.info(f"Jarvis initialisé pour tenant: {tenant_id}")

    @property
    def tool_executor(self) -> ToolExecutor:
        if self._tool_executor is None:
            self._tool_executor = ToolExecutor()
        return self._tool_executor

    @property
    def telegram(self) -> TelegramBot:
        """Lazy-init du wrapper Telegram (si TELEGRAM_BOT_TOKEN_JARVIS défini)."""
        if self._telegram is None:
            self._telegram = build_telegram_from_env()
        return self._telegram

    @property
    def email(self) -> EmailClient:
        """Lazy-init du wrapper Email SMTP (si SMTP_* définis)."""
        if self._email is None:
            self._email = build_email_from_env()
        return self._email

    def send_email(self, to, subject: str, body_html: str,
                   body_text: str | None = None, **kwargs) -> dict:
        """Envoie un email transactionnel. Blocking wrapper autour de l'API async.

        V1 anti-spam rule : max 1 email par client par 24h — à appliquer au
        niveau skill (pas ici), via table Supabase `rate_limit_email` à venir.
        """
        import asyncio

        try:
            return asyncio.run(
                self.email.send_email(
                    to=to, subject=subject, body_html=body_html,
                    body_text=body_text, **kwargs,
                )
            )
        except Exception as e:
            logger.error(f"send_email: échec SMTP — {e}")
            return {}

    @property
    def sms(self) -> TwilioSMSClient:
        """Lazy-init du wrapper Twilio SMS (si TWILIO_* définis)."""
        if self._sms is None:
            self._sms = build_sms_from_env()
        return self._sms

    def send_sms(self, to_number: str, body: str,
                 urgence: bool = False) -> dict:
        """Envoie un SMS. Blocking wrapper autour de l'API async.

        V1 anti-spam rule : max 1 SMS/numéro/24h (bypass si urgence=True) —
        à cabler via Supabase `rate_limit_sms` post go-live.
        """
        import asyncio

        try:
            return asyncio.run(
                self.sms.send_sms(to_number=to_number, body=body,
                                  urgence=urgence)
            )
        except Exception as e:
            logger.error(f"send_sms: échec Twilio — {e}")
            return {}

    @property
    def whatsapp(self) -> WhatsAppClient:
        """Lazy-init du wrapper WhatsApp Business (si WHATSAPP_* définis)."""
        if self._whatsapp is None:
            self._whatsapp = build_whatsapp_from_env()
        return self._whatsapp

    def send_whatsapp(self, to_number: str, body: str) -> dict:
        """Envoie un message WhatsApp texte. Blocking wrapper.

        Requiert fenêtre 24h conversationnelle ouverte côté destinataire.
        Pour envoi hors fenêtre : utiliser send_whatsapp_template().
        """
        import asyncio

        try:
            return asyncio.run(
                self.whatsapp.send_text_message(to_number=to_number, body=body)
            )
        except Exception as e:
            logger.error(f"send_whatsapp: échec Meta — {e}")
            return {}

    def send_whatsapp_template(self, to_number: str, template_name: str,
                               language_code: str = "fr",
                               components: list | None = None) -> dict:
        """Envoie un message template WhatsApp pré-approuvé par Meta.

        Utiliser hors fenêtre 24h (notifications proactives).
        """
        import asyncio

        try:
            return asyncio.run(
                self.whatsapp.send_template_message(
                    to_number=to_number, template_name=template_name,
                    language_code=language_code, components=components,
                )
            )
        except Exception as e:
            logger.error(f"send_whatsapp_template: échec Meta — {e}")
            return {}

    @property
    def vapi(self) -> VapiClient:
        """Lazy-init du client Vapi (si VAPI_API_KEY défini)."""
        if self._vapi is None:
            self._vapi = build_vapi_from_env()
        return self._vapi

    @property
    def legifrance(self) -> LegifranceClient:
        """Lazy-init du client PISTE Legifrance/JudiLibre."""
        if self._legifrance is None:
            self._legifrance = build_legifrance_from_env()
        return self._legifrance

    def initiate_vapi_call(self, customer_number: str,
                           assistant_id: str | None = None,
                           phone_number_id: str | None = None,
                           metadata: dict | None = None) -> dict:
        """Initie un appel sortant Vapi. Blocking wrapper.

        Si assistant_id ou phone_number_id non passés, on tire depuis l'env
        (VAPI_ASSISTANT_ID_AXEL, VAPI_PHONE_NUMBER_ID).
        """
        import asyncio

        assistant_id = assistant_id or os.environ.get("VAPI_ASSISTANT_ID_AXEL")
        phone_number_id = phone_number_id or os.environ.get("VAPI_PHONE_NUMBER_ID")
        if not assistant_id:
            logger.error("initiate_vapi_call: VAPI_ASSISTANT_ID_AXEL manquant")
            return {}

        try:
            return asyncio.run(
                self.vapi.create_outbound_call(
                    assistant_id=assistant_id,
                    customer_number=customer_number,
                    phone_number_id=phone_number_id,
                    metadata=metadata,
                )
            )
        except Exception as e:
            logger.error(f"initiate_vapi_call: échec Vapi — {e}")
            return {}

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

    def respond(self, user_message: str, max_tool_rounds: int = 8,
                use_tools: bool = True) -> str:
        """Traite un message utilisateur et retourne la réponse de Jarvis.

        Boucle agentic : Claude peut appeler des tools (Supabase, Invoice Ninja,
        Telegram...) et reçoit les résultats avant de formuler sa réponse finale.
        """
        model = get_model(user_message)
        complexity = classify_complexity(user_message)
        logger.info(f"Message reçu — complexité: {complexity.value}, modèle: {model}, tools={use_tools}")

        self.conversation.append({"role": "user", "content": user_message})

        total_in = 0
        total_out = 0
        rounds = 0
        final_text = ""

        while True:
            rounds += 1
            kwargs = dict(
                model=model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=self.conversation,
            )
            if use_tools:
                kwargs["tools"] = TOOLS_SCHEMA

            response = client.messages.create(**kwargs)
            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens

            # Parse response blocks
            tool_results = []
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
                elif block.type == "tool_use":
                    name = block.name
                    tool_input = block.input or {}
                    tool_id = block.id
                    logger.info(f"tool_use name={name} input={json.dumps(tool_input, ensure_ascii=False)[:160]}")
                    result = self.tool_executor.execute(name, tool_input)
                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                    is_err = isinstance(result, dict) and "error" in result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_str[:4000],
                        **({"is_error": True} if is_err else {}),
                    })

            if response.stop_reason != "tool_use" or not tool_results:
                # Cloture : on enregistre la reponse finale
                self.conversation.append({"role": "assistant",
                                           "content": response.content})
                break

            # Relance avec les resultats
            self.conversation.append({"role": "assistant",
                                       "content": response.content})
            self.conversation.append({"role": "user",
                                       "content": tool_results})

            if rounds >= max_tool_rounds:
                logger.warning("respond: max_tool_rounds atteint (%d)",
                               max_tool_rounds)
                final_text += "\n\n(limite de rounds outils atteinte)"
                break

        logger.info(
            f"Réponse générée — {rounds} rounds, {total_in} in / {total_out} out tokens"
        )
        return final_text or "(pas de réponse textuelle)"

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
