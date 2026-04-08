from __future__ import annotations


class NovelAgentError(Exception):
    pass


class ExternalServiceError(NovelAgentError):
    def __init__(self, service: str, message: str, *, original: Exception | None = None) -> None:
        self.service = service
        self.original = original
        super().__init__(f"[{service}] {message}")


class DatabaseError(NovelAgentError):
    pass


class LLMProviderError(ExternalServiceError):
    def __init__(self, provider: str, message: str, *, original: Exception | None = None) -> None:
        super().__init__(service=f"llm:{provider}", message=message, original=original)
        self.provider = provider


class CacheServiceError(ExternalServiceError):
    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(service="cache", message=message, original=original)


class GraphDatabaseError(ExternalServiceError):
    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(service="neo4j", message=message, original=original)


class ConfigError(NovelAgentError):
    pass


class ValidationError(NovelAgentError):
    pass


class RateLimitExceededError(ExternalServiceError):
    def __init__(self, service: str, message: str = "Rate limit exceeded") -> None:
        super().__init__(service=service, message=message)
