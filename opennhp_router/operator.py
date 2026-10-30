"""Load the operator file. Three settings only: window, identities, resource map."""

from dataclasses import dataclass, field
import tomllib


@dataclass
class Forward:
    public_host: str
    public_port: int
    backend_host: str
    backend_port: int
    protocol: str


@dataclass
class Resource:
    name: str
    forwards: list[Forward] = field(default_factory=list)


@dataclass
class Identity:
    pubkey: str


@dataclass
class OperatorConfig:
    window_seconds: int
    identities: list[Identity]
    resources: list[Resource]


def load_operator_text(text: str) -> OperatorConfig:
    data = tomllib.loads(text)
    identities = [Identity(pubkey=item["pubkey"]) for item in data.get("identities", [])]
    resources = []
    for item in data.get("resources", []):
        forwards = [
            Forward(
                public_host=fwd["public_host"],
                public_port=int(fwd["public_port"]),
                backend_host=fwd["backend_host"],
                backend_port=int(fwd["backend_port"]),
                protocol=fwd["protocol"],
            )
            for fwd in item.get("forwards", [])
        ]
        resources.append(Resource(name=item["name"], forwards=forwards))
    return OperatorConfig(
        window_seconds=int(data["window_seconds"]),
        identities=identities,
        resources=resources,
    )


def load_operator_path(path) -> OperatorConfig:
    with open(path, "rb") as handle:
        return load_operator_text(handle.read().decode("utf-8"))
