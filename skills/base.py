"""
Base Skill interface + registry.

Every skill is a self-contained class with:
  - name        : unique identifier
  - description : plain-English description the LLM uses to decide when to call it
  - parameters  : JSON-schema describing the arguments (same shape Claude/OpenAI
                  tool-use expects)
  - execute()   : the actual Python code that runs when the skill is invoked

Drop a new file in skills/, define a class inheriting from Skill, and register
an instance in skills/__init__.py (or auto-discover, see registry.autodiscover()).
Nothing else in the codebase needs to change.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class Skill(ABC):
    name: str
    description: str
    # JSON schema for parameters, e.g.:
    # {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Run the skill and return a plain-text result to hand back to the LLM
        (or to speak/print directly to the user)."""
        raise NotImplementedError

    def to_tool_schema(self) -> dict:
        """Anthropic tool-use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai_tool_schema(self) -> dict:
        """OpenAI-compatible tool format (used by Groq, OpenAI, and most others)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class SkillRegistry:
    _skills: dict[str, Skill] = field(default_factory=dict)

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def tool_schemas(self) -> list[dict]:
        return [s.to_tool_schema() for s in self._skills.values()]

    def openai_tool_schemas(self) -> list[dict]:
        return [s.to_openai_tool_schema() for s in self._skills.values()]

    def run(self, name: str, **kwargs) -> str:
        if name not in self._skills:
            return f"Error: no skill named '{name}' is registered."
        try:
            return self._skills[name].execute(**kwargs)
        except Exception as e:  # noqa: BLE001 - we want to feed errors back to the LLM, not crash the loop
            return f"Error running skill '{name}': {e}"


registry = SkillRegistry()
