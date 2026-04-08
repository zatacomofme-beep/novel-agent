from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class Neo4jDriverProtocol(Protocol):
    async def verify_connectivity(self) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class Neo4jSessionProtocol(Protocol):
    async def run(
        self,
        query: str,
        *,
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Neo4jResultProtocol: ...


@runtime_checkable
class Neo4jResultProtocol(Protocol):
    async def single(self) -> Neo4jRecordProtocol | None: ...
    def __aiter__(self) -> AsyncIterator[Neo4jRecordProtocol]: ...


@runtime_checkable
class Neo4jRecordProtocol(Protocol):
    def __getitem__(self, key: str) -> Any: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def keys(self) -> list[str]: ...
    def values(self) -> list[Any]: ...
    def items(self) -> list[tuple[str, Any]]: ...
    def __iter__(self) -> Any: ...


@runtime_checkable
class Neo4jPathProtocol(Protocol):
    @property
    def nodes(self) -> list[Neo4jNodeProtocol]: ...
    @property
    def relationships(self) -> list[Neo4jRelationshipProtocol]: ...


@runtime_checkable
class Neo4jNodeProtocol(Protocol):
    @property
    def id(self) -> int: ...
    def get(self, key: str, default: Any = None) -> Any: ...


@runtime_checkable
class Neo4jRelationshipProtocol(Protocol):
    @property
    def type(self) -> str: ...
    def get(self, key: str, default: Any = None) -> Any: ...