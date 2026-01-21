from .consultative import ConsultativeStrategy
from .transactional import TransactionalStrategy

__all__ = ["ConsultativeStrategy", "TransactionalStrategy"]

def get_strategy(name):
    """Factory: returns strategy instance"""
    strategies = {"consultative": ConsultativeStrategy, "transactional": TransactionalStrategy}
    if name not in strategies:
        raise ValueError(f"Unknown strategy: {name}")
    return strategies[name]()
