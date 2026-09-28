"""Registry of role skills (M6)."""

from __future__ import annotations

from .base import Skill


class UnknownSkillError(KeyError):
    """Raised when a skill name is not registered."""


class SkillRegistry:
    """Look up skills by name; lookups fail closed on unknown names."""

    def __init__(self, skills: tuple[Skill, ...] = ()) -> None:
        self._skills: dict[str, Skill] = {}
        for skill in skills:
            self.register(skill)

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"skill already registered: {skill.name}")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise UnknownSkillError(name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._skills))