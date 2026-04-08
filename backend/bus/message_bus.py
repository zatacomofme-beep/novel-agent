from __future__ import annotations

from collections import defaultdict, deque
from typing import Callable

from bus.events import BusEvent
from bus.protocol import AgentMessage


Subscriber = Callable[[AgentMessage], None]


class InMemoryMessageBus:
    def __init__(self, max_events: int = 10000) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._events: deque[BusEvent] = deque(maxlen=max_events)

    def subscribe(self, recipient: str, subscriber: Subscriber) -> None:
        self._subscribers[recipient].append(subscriber)

    def publish(self, message: AgentMessage) -> None:
        self._events.append(
            BusEvent(
                event_type=message.message_type.value,
                payload={
                    "message_id": message.message_id,
                    "sender": message.sender,
                    "recipients": message.recipients,
                    "subject": message.subject,
                },
            )
        )
        for recipient in message.recipients:
            for subscriber in self._subscribers.get(recipient, []):
                subscriber(message)

    def events(self) -> list[BusEvent]:
        return list(self._events)

    @property
    def event_count(self) -> int:
        return len(self._events)


message_bus = InMemoryMessageBus()
