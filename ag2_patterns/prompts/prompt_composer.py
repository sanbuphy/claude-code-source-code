"""
Prompt Composer — Dynamic system prompt assembly for AG2 agents.

Extracted from Claude Code's prompt composition system:
- src/utils/systemPrompt.ts — buildEffectiveSystemPrompt() with priority hierarchy
- src/constants/systemPromptSections.ts — Cached section system
- src/memdir/memdir.ts — Memory prompt injection

Patterns implemented:
1. Priority-based prompt assembly (override > agent > custom > default)
2. Cached prompt sections with invalidation
3. Conditional section injection based on state
4. Memory/context injection into system prompts
5. AG2 system_message generator for dynamic prompts
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from ag2_patterns.prompts.templates import (
    CODE_QUALITY_SECTION,
    EXECUTION_SECTION,
    IDENTITY_SECTION,
    SAFETY_SECTION,
    TOOL_USAGE_SECTION,
    render_template,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt section with caching (from src/constants/systemPromptSections.ts)
# ---------------------------------------------------------------------------

@dataclass
class PromptSection:
    """A named, cacheable section of a system prompt.

    Source: src/constants/systemPromptSections.ts — systemPromptSection()

    Sections are computed lazily and cached until explicitly invalidated.
    This mirrors Claude Code's approach where system prompt sections are
    memoized for prompt cache stability.
    """
    name: str
    compute: Callable[[], str]
    cacheable: bool = True
    _cache: str | None = field(default=None, repr=False)

    def resolve(self) -> str:
        """Resolve the section content, using cache if available."""
        if self.cacheable and self._cache is not None:
            return self._cache
        content = self.compute()
        if self.cacheable:
            self._cache = content
        return content

    def invalidate(self) -> None:
        """Clear the cached content."""
        self._cache = None


# ---------------------------------------------------------------------------
# Prompt Composer
# ---------------------------------------------------------------------------

class PromptComposer:
    """Compose system prompts dynamically from sections and context.

    Source: src/utils/systemPrompt.ts — buildEffectiveSystemPrompt()

    Claude Code uses a priority hierarchy for system prompts:
    1. Override prompt (loop mode) — REPLACES all
    2. Coordinator prompt (coordinator mode)
    3. Agent prompt (sub-agent definition)
    4. Custom prompt (--system-prompt flag)
    5. Default prompt (base sections)
    6. Append prompt (always added at end)

    This class implements the same pattern for AG2 agents, allowing
    dynamic system prompt construction based on agent role, task state,
    and available tools.

    Example::

        composer = PromptComposer()

        # Add sections
        composer.add_section("identity", lambda: "You are a coding assistant.")
        composer.add_section("tools", lambda: format_tools(registry))
        composer.add_section("memory", lambda: load_memory(), cacheable=False)

        # Get composed prompt
        system_message = composer.compose()

        # Use with AG2
        agent = AssistantAgent("coder", system_message=system_message, ...)
    """

    def __init__(self) -> None:
        self._sections: list[PromptSection] = []
        self._override: str | None = None
        self._prepend: str | None = None
        self._append: str | None = None
        self._context: dict[str, Any] = {}

    def add_section(
        self,
        name: str,
        compute: Callable[[], str] | str,
        cacheable: bool = True,
        position: int | None = None,
    ) -> "PromptComposer":
        """Add a named section to the prompt.

        Args:
            name: Section identifier (for cache invalidation).
            compute: String or callable that returns the section text.
            cacheable: Whether to cache the result.
            position: Insert position (None = append at end).
        """
        if isinstance(compute, str):
            text = compute
            compute = lambda _t=text: _t

        section = PromptSection(name=name, compute=compute, cacheable=cacheable)

        if position is not None:
            self._sections.insert(position, section)
        else:
            self._sections.append(section)
        return self

    def set_override(self, prompt: str | None) -> "PromptComposer":
        """Set an override prompt that replaces all sections.

        Source: src/utils/systemPrompt.ts — override system prompt (loop mode)
        """
        self._override = prompt
        return self

    def set_prepend(self, text: str | None) -> "PromptComposer":
        """Set text prepended before all sections."""
        self._prepend = text
        return self

    def set_append(self, text: str | None) -> "PromptComposer":
        """Set text appended after all sections.

        Source: src/utils/systemPrompt.ts — appendSystemPrompt
        """
        self._append = text
        return self

    def set_context(self, key: str, value: Any) -> "PromptComposer":
        """Set context variable available to sections."""
        self._context[key] = value
        return self

    def compose(self) -> str:
        """Compose the final system prompt.

        Source: src/utils/systemPrompt.ts — buildEffectiveSystemPrompt()

        Priority:
        1. If override is set, return it (+ append)
        2. Otherwise, resolve all sections in order
        3. Prepend and append are added around the sections
        """
        if self._override:
            parts = [self._override]
            if self._append:
                parts.append(self._append)
            return "\n\n".join(parts)

        parts: list[str] = []

        if self._prepend:
            parts.append(self._prepend)

        for section in self._sections:
            content = section.resolve()
            if content and content.strip():
                parts.append(content)

        if self._append:
            parts.append(self._append)

        return "\n\n".join(parts)

    def invalidate(self, section_name: str | None = None) -> None:
        """Invalidate cached sections.

        Source: src/constants/systemPromptSections.ts — clearSystemPromptSections()

        Args:
            section_name: Specific section to invalidate, or None for all.
        """
        for section in self._sections:
            if section_name is None or section.name == section_name:
                section.invalidate()

    def get_section(self, name: str) -> PromptSection | None:
        """Look up a section by name."""
        for section in self._sections:
            if section.name == name:
                return section
        return None

    @property
    def section_names(self) -> list[str]:
        """List all section names."""
        return [s.name for s in self._sections]

    def fingerprint(self) -> str:
        """Generate a hash fingerprint of the composed prompt.

        Useful for detecting when the prompt has changed (cache invalidation).
        """
        composed = self.compose()
        return hashlib.md5(composed.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Pre-built composers for common AG2 agent roles
# ---------------------------------------------------------------------------

def create_default_composer(
    tools_description: str = "",
    working_directory: str = "",
    custom_instructions: str = "",
) -> PromptComposer:
    """Create a composer with Claude Code's default prompt structure.

    Source: src/utils/systemPrompt.ts — default system prompt assembly
    """
    composer = PromptComposer()

    composer.add_section("identity", IDENTITY_SECTION)
    composer.add_section("code_quality", CODE_QUALITY_SECTION)
    composer.add_section("safety", SAFETY_SECTION)
    composer.add_section("execution", EXECUTION_SECTION)

    if tools_description:
        composer.add_section(
            "tools",
            lambda: render_template(TOOL_USAGE_SECTION, tool_list=tools_description),
        )

    if working_directory:
        composer.add_section(
            "environment",
            f"## Environment\n\n- Working directory: {working_directory}",
        )

    if custom_instructions:
        composer.set_append(f"## Custom Instructions\n\n{custom_instructions}")

    return composer


def create_agent_composer(
    role: str,
    role_prompt: str,
    tools_description: str = "",
    is_proactive: bool = False,
) -> PromptComposer:
    """Create a composer for a specialized agent role.

    Source: src/utils/systemPrompt.ts — agent system prompt handling

    When `is_proactive=True`, the role prompt is appended to the default
    prompt (the agent adds domain-specific instructions on top of defaults).
    When `is_proactive=False`, the role prompt replaces the default.

    Args:
        role: Agent role name.
        role_prompt: The role-specific instructions.
        tools_description: Available tools description.
        is_proactive: Whether to append to (True) or replace (False) default.
    """
    if is_proactive:
        # Proactive: append role instructions to default prompt
        composer = create_default_composer(tools_description=tools_description)
        composer.add_section(f"role_{role}", role_prompt)
    else:
        # Non-proactive: role prompt replaces default
        composer = PromptComposer()
        composer.add_section(f"role_{role}", role_prompt)
        if tools_description:
            composer.add_section(
                "tools",
                lambda: render_template(TOOL_USAGE_SECTION, tool_list=tools_description),
            )

    return composer


# ---------------------------------------------------------------------------
# AG2 Integration: Dynamic system_message generator
# ---------------------------------------------------------------------------

def create_dynamic_system_message(
    composer: PromptComposer,
) -> Callable[[], str]:
    """Create a callable that generates the current system message.

    Use this with AG2 agents that support dynamic system messages,
    or call it before each agent turn to update the system_message.

    Example::

        composer = create_default_composer(tools_description="...")
        get_system_msg = create_dynamic_system_message(composer)

        # Update agent's system message before each turn
        agent.update_system_message(get_system_msg())
    """
    return composer.compose


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Create default composer
    composer = create_default_composer(
        tools_description="- read_file: Read files\n- bash: Run commands",
        working_directory="/home/user/project",
        custom_instructions="Always use Python 3.12+ features.",
    )

    prompt = composer.compose()
    print(f"=== Default Composer ({len(prompt)} chars) ===")
    print(prompt[:500] + "...\n")
    print(f"Sections: {composer.section_names}")
    print(f"Fingerprint: {composer.fingerprint()}")

    # Test invalidation
    old_fp = composer.fingerprint()
    composer.invalidate("identity")
    new_fp = composer.fingerprint()
    print(f"\nAfter invalidation: fingerprint changed = {old_fp != new_fp}")

    # Create agent-specific composer
    print("\n=== Planner Agent (non-proactive) ===")
    planner = create_agent_composer(
        role="planner",
        role_prompt="You are a software architect. Plan, don't code.",
        is_proactive=False,
    )
    print(planner.compose()[:300] + "...")

    # Test override
    print("\n=== Override Mode ===")
    composer.set_override("You are in loop mode. Just check the status.")
    print(composer.compose())
    composer.set_override(None)

    # Dynamic system message
    get_msg = create_dynamic_system_message(composer)
    print(f"\nDynamic message length: {len(get_msg())} chars")
