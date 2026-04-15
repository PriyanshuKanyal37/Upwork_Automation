from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName


class AIProviderAdapter(ABC):
    provider: ProviderName

    @abstractmethod
    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        """Generate model output for the supplied request."""

