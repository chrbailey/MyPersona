"""
LLM client for AI-powered analysis.

Uses Claude for deep reasoning about discourse patterns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
import logging
import json

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    usage: dict
    raw_response: Optional[dict] = None


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
    ) -> dict:
        """Generate a JSON response from the LLM."""
        pass


class ClaudeClient(LLMClient):
    """
    Client for Anthropic's Claude API.

    Used for:
    - Deep sentiment and tone analysis
    - Event classification reasoning
    - Absence detection reasoning
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from Claude."""
        await self._ensure_session()

        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system:
            payload["system"] = system

        for attempt in range(self.max_retries):
            try:
                async with self._session.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                ) as response:
                    if response.status == 429:
                        # Rate limited
                        import asyncio
                        await asyncio.sleep(2 ** attempt)
                        continue

                    response.raise_for_status()
                    data = await response.json()

                    return LLMResponse(
                        content=data["content"][0]["text"],
                        model=data["model"],
                        usage=data.get("usage", {}),
                        raw_response=data,
                    )

            except aiohttp.ClientError as e:
                logger.error(f"Claude API error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise

        raise Exception("Max retries exceeded")

    async def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
    ) -> dict:
        """Generate a JSON response from Claude."""
        json_instruction = "\n\nRespond with valid JSON only. No other text."

        if schema:
            json_instruction += f"\n\nJSON Schema:\n{json.dumps(schema, indent=2)}"

        full_prompt = prompt + json_instruction

        response = await self.generate(
            prompt=full_prompt,
            system=system,
            temperature=0.3,  # Lower temp for structured output
        )

        try:
            # Extract JSON from response
            content = response.content.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response.content}")
            return {}


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self):
        self.responses: list[str] = []
        self.call_count = 0

    def set_response(self, response: str) -> None:
        """Set the next response."""
        self.responses.append(response)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Return mock response."""
        self.call_count += 1

        if self.responses:
            content = self.responses.pop(0)
        else:
            content = "Mock response"

        return LLMResponse(
            content=content,
            model="mock",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

    async def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
    ) -> dict:
        """Return mock JSON response."""
        self.call_count += 1

        if self.responses:
            return json.loads(self.responses.pop(0))

        return {"mock": True}
