"""Fábrica de modelos de chat do LangChain para os provedores suportados."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_ollama import ChatOllama

from ..config import Settings, settings

_MODEL_OVERRIDE: BaseChatModel | None = None
_MODEL_OVERRIDES: dict[str, BaseChatModel] = {}


def set_model_override(model: BaseChatModel | None) -> None:
    """Define um modelo substituto global para execução em testes."""
    global _MODEL_OVERRIDE
    _MODEL_OVERRIDE = model


def set_provider_override(provider: str, model: BaseChatModel | None) -> None:
    """Define um modelo substituto para um provedor específico em testes."""
    normalized = provider.strip().lower()
    if model is None:
        _MODEL_OVERRIDES.pop(normalized, None)
    else:
        _MODEL_OVERRIDES[normalized] = model


def clear_model_overrides() -> None:
    """Remove todos os overrides de modelos para testes."""
    global _MODEL_OVERRIDE
    _MODEL_OVERRIDE = None
    _MODEL_OVERRIDES.clear()


def is_provider_configured(
    provider: str,
    settings_obj: Settings | None = None,
) -> bool:
    """Indica se as credenciais e parâmetros do provedor estão configurados."""
    normalized = provider.strip().lower()
    if normalized in _MODEL_OVERRIDES:
        return True
    if _MODEL_OVERRIDE is not None:
        return True
    current = settings_obj or settings
    if normalized == "gemini":
        return bool(current.gemini_api_key)
    if normalized == "hf":
        return bool(current.hf_token and current.hf_model)
    if normalized == "local":
        return bool(current.ollama_model and current.ollama_base_url)
    if normalized == "offline":
        return True
    return False


def get_provider_model_name(
    provider: str,
    settings_obj: Settings | None = None,
) -> str:
    """Retorna o nome do modelo associado ao provedor para composição de cache."""
    current = settings_obj or settings
    normalized = provider.strip().lower()
    if normalized == "gemini":
        return current.gemini_model
    if normalized == "hf":
        return current.hf_model
    if normalized == "local":
        return current.ollama_model
    return "offline"


def get_provider_timeout(
    provider: str,
    settings_obj: Settings | None = None,
) -> float:
    """Retorna o timeout em segundos configurado para o provedor."""
    current = settings_obj or settings
    normalized = provider.strip().lower()
    if normalized == "local":
        return float(current.ollama_timeout)
    if normalized == "gemini":
        return 60.0
    if normalized == "hf":
        return 60.0
    return 10.0


def build_chat_model(
    provider: str,
    settings_obj: Settings | None = None,
) -> BaseChatModel:
    """Devolve uma instância de BaseChatModel configurada para o provedor."""
    normalized = provider.strip().lower()
    if normalized in _MODEL_OVERRIDES:
        return _MODEL_OVERRIDES[normalized]
    if _MODEL_OVERRIDE is not None:
        return _MODEL_OVERRIDE

    current = settings_obj or settings

    if normalized == "gemini":
        if not current.gemini_api_key:
            raise ValueError("Chave de API do Gemini não configurada.")
        return ChatGoogleGenerativeAI(
            model=current.gemini_model,
            google_api_key=current.gemini_api_key,
        )

    if normalized == "hf":
        if not current.hf_token or not current.hf_model:
            raise ValueError("Token ou modelo do Hugging Face não configurado.")
        endpoint = HuggingFaceEndpoint(
            repo_id=current.hf_model,
            huggingfacehub_api_token=current.hf_token,
        )
        return ChatHuggingFace(llm=endpoint)

    if normalized == "local":
        if not current.ollama_model:
            raise ValueError("Modelo do Ollama não configurado.")
        return ChatOllama(
            model=current.ollama_model,
            base_url=current.ollama_base_url,
            num_ctx=current.ollama_num_ctx,
            reasoning=current.ollama_think,
            timeout=current.ollama_timeout,
        )

    raise ValueError(f"Provedor desconhecido: {provider}")
