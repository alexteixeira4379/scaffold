from scaffold.ai.contracts import InferenceTier
from scaffold.ai.groq import GroqLLM
from scaffold.ai.memory import InMemoryLLM
from scaffold.ai.ports import LLMPort
from scaffold.config import AIProvider, Settings


def create_llm_backend(settings: Settings) -> LLMPort:
    provider = settings.ai_provider
    if provider == AIProvider.MEMORY:
        return InMemoryLLM()
    if provider == AIProvider.GROQ:
        key = settings.groq_api_key
        if not key:
            raise ValueError("groq_api_key is required when ai_provider is groq")
        models = {
            InferenceTier.BASIC: settings.groq_model_basic,
            InferenceTier.INTERMEDIATE: settings.groq_model_intermediate,
            InferenceTier.COMPLEX: settings.groq_model_complex,
            InferenceTier.THINKING: settings.groq_model_thinking,
        }
        return GroqLLM(
            api_key=key,
            base_url=settings.groq_base_url,
            models=models,
            timeout_s=settings.groq_timeout_s,
        )
    raise ValueError(f"unsupported ai_provider: {provider!r}")
