"""
Chargeur de skills J-ARVIS V2.

Un skill = un dossier avec :
  SKILL.md              frontmatter YAML + corps markdown
  templates/*.html      templates email/docs (optionnel)
  references/*.md       fiches metier (optionnel, chargees a la demande)
  examples/*.md         few-shot (optionnel)

Ce loader est volontairement minimal pour V2 : il parse le frontmatter,
expose les triggers, et fournit le corps du SKILL.md a injecter dans
le system prompt. Le matching se fait en keyword simple (regex word-
boundary, case-insensitive). On passera a de l'embedding-based skill
routing plus tard si la lib de skills depasse ~30.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

SKILL_FILENAME = "SKILL.md"


@dataclass
class Skill:
    path: Path
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    body: str = ""

    def matches(self, message: str) -> bool:
        """True si au moins un trigger matche dans le message (insensible a la casse)."""
        if not self.triggers:
            return False
        lowered = message.lower()
        for trig in self.triggers:
            pattern = r"\b" + re.escape(trig.lower()) + r"\b"
            if re.search(pattern, lowered):
                return True
        return False

    def reference(self, name: str) -> str | None:
        """Charge a la demande un fichier references/<name>.md."""
        candidate = self.path / "references" / f"{name}.md"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
        return None

    def template(self, name: str) -> str | None:
        candidate = self.path / "templates" / f"{name}.html"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
        return None


def parse_skill(skill_dir: Path) -> Skill:
    """Parse un dossier de skill et retourne un objet Skill."""
    skill_md = skill_dir / SKILL_FILENAME
    if not skill_md.is_file():
        raise FileNotFoundError(f"SKILL.md manquant dans {skill_dir}")

    raw = skill_md.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw)
    meta = yaml.safe_load(frontmatter) if frontmatter else {}

    name = meta.get("title") or meta.get("name") or skill_dir.name
    description = meta.get("description", "")
    if isinstance(description, str):
        description = description.strip()
    triggers = meta.get("triggers") or []

    return Skill(
        path=skill_dir,
        name=name,
        description=description,
        triggers=[str(t) for t in triggers],
        body=body.strip(),
    )


def _split_frontmatter(raw: str) -> tuple[str, str]:
    """Separe ---frontmatter--- + corps markdown. Tolere absence de frontmatter."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", raw
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return "", raw
    frontmatter = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    return frontmatter, body


def discover_skills(modules_root: Path) -> list[Skill]:
    """Scan modules/**/skills/** pour trouver tous les SKILL.md."""
    skills: list[Skill] = []
    if not modules_root.is_dir():
        logger.warning("modules_root introuvable : %s", modules_root)
        return skills

    for skill_md in modules_root.glob("module-*/skills/*/SKILL.md"):
        try:
            skills.append(parse_skill(skill_md.parent))
        except Exception as e:  # ne jamais faire planter la decouverte
            logger.error("echec parse skill %s : %s", skill_md.parent, e)
    return skills


def match_skills(message: str, skills: list[Skill]) -> list[Skill]:
    return [s for s in skills if s.matches(message)]


def inject_into_system_prompt(base_prompt: str, matched: list[Skill]) -> str:
    """Concatene base_prompt + le corps des skills matches."""
    if not matched:
        return base_prompt
    blocks = [base_prompt, "", "## Skills actifs pour ce message", ""]
    for sk in matched:
        blocks.append(f"### Skill : {sk.name}")
        blocks.append(sk.body)
        blocks.append("")
    return "\n".join(blocks)
