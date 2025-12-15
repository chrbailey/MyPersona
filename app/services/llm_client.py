import httpx
from typing import Optional

from app.config import settings


class LLMClient:
    """
    Async LLM client using httpx.
    Supports OpenAI OR Anthropic based on configuration.
    No SDK magic - direct HTTP calls.
    """

    def __init__(self):
        self.provider = settings.llm_provider
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    async def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        """Make a call to OpenAI API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _call_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        """Make a call to Anthropic API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        """
        Make an LLM call using the configured provider.

        Args:
            system_prompt: System message
            user_prompt: User message
            max_tokens: Maximum tokens in response

        Returns:
            Response text from LLM

        Raises:
            httpx.HTTPStatusError: On API errors
        """
        if self.provider == "openai":
            return await self._call_openai(system_prompt, user_prompt, max_tokens)
        else:
            return await self._call_anthropic(system_prompt, user_prompt, max_tokens)

    async def micro_call(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Make a micro LLM call (for context extraction).
        Uses configured max tokens for micro calls (≤300 per spec).
        """
        return await self.call(
            system_prompt,
            user_prompt,
            settings.micro_call_max_tokens,
        )

    async def primary_call(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Make the primary LLM call (for main response).
        Uses configured max tokens for primary calls.
        """
        return await self.call(
            system_prompt,
            user_prompt,
            settings.primary_call_max_tokens,
        )

    def get_model_name(self) -> str:
        """Return the model name being used."""
        if self.provider == "openai":
            return settings.openai_model
        else:
            return settings.anthropic_model


# Singleton instance
llm_client = LLMClient()
