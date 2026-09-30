"""LLM provider abstraction. Nothing outside this module imports an SDK directly."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, TextBlock, query
from claude_agent_sdk.types import StreamEvent


@dataclass
class TokenUsage:
    """Running token/cost total, summed straight from the SDK's own `ResultMessage.model_usage` (no estimation)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.cost_usd += other.cost_usd


def _usage_of(msg: ResultMessage) -> TokenUsage:
    u = TokenUsage()
    for model_usage in (msg.model_usage or {}).values():
        u.input_tokens += model_usage.get("inputTokens", 0)
        u.output_tokens += model_usage.get("outputTokens", 0)
        u.cache_read_tokens += model_usage.get("cacheReadInputTokens", 0)
        u.cache_creation_tokens += model_usage.get("cacheCreationInputTokens", 0)
        u.cost_usd += model_usage.get("costUSD", 0.0)
    if not msg.model_usage and msg.total_cost_usd:
        u.cost_usd = msg.total_cost_usd
    return u


class ChatSession(Protocol):
    usage: TokenUsage  # running total for the whole conversation this session holds
    async def start(self) -> None: ...
    def send(self, text: str) -> AsyncIterator[str]: ...
    async def interrupt(self) -> None: ...
    async def close(self) -> None: ...


async def complete_once(system_prompt: str, prompt: str, model: str) -> tuple[str, TokenUsage]:
    """One-shot completion through the local Claude Code login (no conversation, no tools). Used for background judging."""
    text = ""
    usage = TokenUsage()
    async for msg in query(
        prompt=prompt,
        options=ClaudeAgentOptions(model=model, system_prompt=system_prompt, tools=[], setting_sources=[], max_turns=1),
    ):
        if isinstance(msg, AssistantMessage):
            text += "".join(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage):
            usage = _usage_of(msg)
            if msg.is_error:
                raise RuntimeError(f"Claude error: {msg.subtype}")
    return text, usage


class ClaudeCodeChatSession:
    """Long-lived chat backed by the local Claude Code CLI and the user's existing login.

    The CLI process stays warm for the whole conversation, so only the first turn
    pays the startup cost (~3s); later turns stream the first token in ~1.5s.
    """

    def __init__(self, system_prompt: str, model: str):
        self._client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                system_prompt=system_prompt,
                tools=[],  # pure conversation: no file/bash/web access
                setting_sources=[],  # don't load the user's CLAUDE.md or settings
                include_partial_messages=True,
                max_turns=1,
            )
        )
        self._in_flight = False
        self.usage = TokenUsage()

    async def start(self) -> None:
        await self._client.connect()

    async def send(self, text: str) -> AsyncIterator[str]:
        self._in_flight = True
        await self._client.query(text)
        async for msg in self._client.receive_response():
            if isinstance(msg, StreamEvent):
                event = msg.event
                if event.get("type") == "content_block_delta" and event["delta"].get("type") == "text_delta":
                    yield event["delta"]["text"]
            elif isinstance(msg, ResultMessage):
                self._in_flight = False
                self.usage.add(_usage_of(msg))
                if msg.is_error:
                    raise RuntimeError(f"Claude error: {msg.subtype}")

    async def interrupt(self) -> None:
        """Stop a reply that was abandoned mid-stream (barge-in).

        The leftover messages of that reply must be drained here, otherwise the next
        turn's receive_response() would read the stale result and end early.
        """
        if not self._in_flight:
            return
        await self._client.interrupt()
        async for _ in self._client.receive_response():
            pass
        self._in_flight = False

    async def close(self) -> None:
        await self._client.disconnect()


def create_chat_session(provider: str, system_prompt: str, model: str) -> ChatSession:
    if provider == "claude_code":
        return ClaudeCodeChatSession(system_prompt, model)
    raise ValueError(f"Unknown LLM provider: {provider}")
