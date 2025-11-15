"""Cost tracking utilities for generation operations.

Provides consistent cost tracking across all modules with itemized billing support.
Each cost type maintains a list of individual costs for transparency when multiple
operations occur (e.g., generating 3 images shows 3 separate costs).
"""

from __future__ import annotations


def append_generation_cost(
    costs: dict[str, list[float]],
    cost_type: str,
    amount: float,
) -> None:
    """Append a cost to the generation costs dictionary for itemized billing.

    This ensures consistent cost tracking across all modules. Each cost type
    maintains a list of individual costs, allowing transparency when multiple
    operations of the same type occur (e.g., multiple images generated).

    Args:
        costs: Dictionary mapping cost types to lists of costs
        cost_type: Type of cost (e.g., 'content_generation', 'image_generation')
        amount: Cost amount to append

    Example:
        >>> costs = {}
        >>> append_generation_cost(costs, "image_generation", 0.02)
        >>> append_generation_cost(costs, "image_generation", 0.02)
        >>> costs
        {'image_generation': [0.02, 0.02]}
    """
    if cost_type not in costs:
        costs[cost_type] = []
    costs[cost_type].append(amount)


def merge_generation_costs(
    target: dict[str, list[float]],
    source: dict[str, float | list[float]],
) -> None:
    """Merge costs from source into target, converting scalars to lists.

    Handles both scalar values (single cost) and list values (multiple costs)
    from the source dictionary. This is useful when integrating costs from
    subsystems that may return either format.

    Args:
        target: Target dictionary with list values (modified in place)
        source: Source dictionary with float or list[float] values

    Example:
        >>> target = {"content_generation": [0.001]}
        >>> source = {"illustrations": 0.05, "citations": [0.01, 0.01]}
        >>> merge_generation_costs(target, source)
        >>> target
        {'content_generation': [0.001], 'illustrations': [0.05], 'citations': [0.01, 0.01]}
    """
    for key, value in source.items():
        if key not in target:
            target[key] = []
        if isinstance(value, list):
            target[key].extend(value)
        else:
            target[key].append(value)


def calculate_total_cost(costs: dict[str, list[float]]) -> float:
    """Calculate total cost from itemized costs dictionary.

    Args:
        costs: Dictionary mapping cost types to lists of costs

    Returns:
        Total cost across all types and operations

    Example:
        >>> costs = {"content_generation": [0.001], "image_generation": [0.02, 0.02]}
        >>> calculate_total_cost(costs)
        0.041
    """
    total = 0.0
    for cost_list in costs.values():
        total += sum(cost_list)
    return total
