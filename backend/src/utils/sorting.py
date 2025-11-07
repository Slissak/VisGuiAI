import re


def natural_sort_key(identifier: str) -> tuple[int, str]:
    """
    Convert step identifier to sortable tuple.

    Examples:
        "0" → (0, "")
        "1" → (1, "")
        "1a" → (1, "a")
        "1b" → (1, "b")
        "10" → (10, "")
        "10a" → (10, "a")

    Args:
        identifier: Step identifier string

    Returns:
        Tuple of (numeric_part, letter_part) for sorting
    """
    match = re.match(r"^(\d+)([a-z]?)$", identifier)
    if match:
        num, letter = match.groups()
        return (int(num), letter or "")
    # Fallback for invalid identifiers
    return (999999, identifier)


def sort_step_identifiers(identifiers: list[str]) -> list[str]:
    """
    Sort step identifiers in natural order.

    Args:
        identifiers: List of step identifier strings

    Returns:
        Sorted list

    Example:
        >>> sort_step_identifiers(["2", "1a", "10", "1", "1b"])
        ["1", "1a", "1b", "2", "10"]
    """
    return sorted(identifiers, key=natural_sort_key)


def is_identifier_before(id1: str, id2: str) -> bool:
    """
    Check if id1 comes before id2 in natural order.

    Args:
        id1: First identifier
        id2: Second identifier

    Returns:
        True if id1 < id2
    """
    return natural_sort_key(id1) < natural_sort_key(id2)


def get_next_identifier(current: str, all_identifiers: list[str]) -> str | None:
    """
    Get the next identifier in sequence.

    Args:
        current: Current step identifier
        all_identifiers: All available identifiers

    Returns:
        Next identifier or None if at end
    """
    sorted_ids = sort_step_identifiers(all_identifiers)
    try:
        current_idx = sorted_ids.index(current)
        if current_idx < len(sorted_ids) - 1:
            return sorted_ids[current_idx + 1]
    except ValueError:
        pass
    return None


def get_previous_identifier(current: str, all_identifiers: list[str]) -> str | None:
    """
    Get the previous identifier in sequence.

    Args:
        current: Current step identifier
        all_identifiers: All available identifiers

    Returns:
        Previous identifier or None if at start
    """
    sorted_ids = sort_step_identifiers(all_identifiers)
    try:
        current_idx = sorted_ids.index(current)
        if current_idx > 0:
            return sorted_ids[current_idx - 1]
    except ValueError:
        pass
    return None
