from app.application.ai.contracts import ProviderName
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.providers.base import AIProviderAdapter
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter
from app.infrastructure.ai.providers.openai_provider import OpenAIProviderAdapter


def build_provider_adapter(provider: ProviderName) -> AIProviderAdapter:
    if provider == ProviderName.OPENAI:
        return OpenAIProviderAdapter()
    if provider == ProviderName.ANTHROPIC:
        return AnthropicProviderAdapter()
    raise AIException(
        code=AIErrorCode.INVALID_ROUTE_CONFIG,
        message="Provider adapter is not implemented",
        details={"provider": provider.value},
    )
