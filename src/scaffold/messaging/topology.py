from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExchangeDefinition:
    name: str
    type: str  # "direct" | "topic" | "fanout" | "headers"
    durable: bool = True


@dataclass(frozen=True)
class QueueDefinition:
    name: str
    durable: bool = True
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BindingDefinition:
    source: str  # exchange name
    destination: str  # queue name
    routing_key: str


@dataclass
class MessagingTopology:
    exchanges: list[ExchangeDefinition] = field(default_factory=list)
    queues: list[QueueDefinition] = field(default_factory=list)
    bindings: list[BindingDefinition] = field(default_factory=list)

    def merge(self, other: "MessagingTopology") -> "MessagingTopology":
        return MessagingTopology(
            exchanges=self.exchanges + other.exchanges,
            queues=self.queues + other.queues,
            bindings=self.bindings + other.bindings,
        )
