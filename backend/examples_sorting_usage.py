#!/usr/bin/env python3
"""
Example usage of the natural sorting utility.
Run this script to see the sorting utility in action.
"""

from src.utils.sorting import (
    natural_sort_key,
    sort_step_identifiers,
    is_identifier_before,
    get_next_identifier,
    get_previous_identifier,
)


def example_basic_sorting():
    """Example 1: Basic sorting of step identifiers."""
    print("=" * 60)
    print("Example 1: Basic Sorting")
    print("=" * 60)

    # Unsorted list of step identifiers
    unsorted = ["10", "1", "2", "1a", "1b", "10a", "0", "2a"]

    print(f"Unsorted: {unsorted}")
    print(f"Sorted:   {sort_step_identifiers(unsorted)}")
    print()


def example_navigation():
    """Example 2: Step navigation (next/previous)."""
    print("=" * 60)
    print("Example 2: Step Navigation")
    print("=" * 60)

    steps = ["1", "1a", "1b", "2", "10", "10a"]
    current = "1a"

    print(f"All steps: {steps}")
    print(f"Current step: {current}")

    next_step = get_next_identifier(current, steps)
    prev_step = get_previous_identifier(current, steps)

    print(f"Next step: {next_step}")
    print(f"Previous step: {prev_step}")
    print()


def example_comparison():
    """Example 3: Comparing step identifiers."""
    print("=" * 60)
    print("Example 3: Comparing Identifiers")
    print("=" * 60)

    comparisons = [
        ("1", "2"),
        ("1a", "1b"),
        ("1", "10"),
        ("10", "2"),
        ("1", "1a"),
    ]

    for id1, id2 in comparisons:
        result = is_identifier_before(id1, id2)
        print(f"Is '{id1}' before '{id2}'? {result}")
    print()


def example_progress_tracking():
    """Example 4: Progress tracking simulation."""
    print("=" * 60)
    print("Example 4: Progress Tracking")
    print("=" * 60)

    all_steps = ["1", "1a", "1b", "2", "2a", "10", "10a"]
    completed_steps = ["1", "1a", "1b", "2"]

    sorted_steps = sort_step_identifiers(all_steps)
    total = len(sorted_steps)
    completed = len([s for s in sorted_steps if s in completed_steps])
    progress = (completed / total) * 100

    print(f"Total steps: {total}")
    print(f"Completed steps: {completed}")
    print(f"Progress: {progress:.1f}%")
    print()

    # Find next uncompleted step
    for step in sorted_steps:
        if step not in completed_steps:
            print(f"Next step to complete: {step}")
            break


def example_full_walkthrough():
    """Example 5: Full walkthrough of a guide."""
    print("=" * 60)
    print("Example 5: Full Guide Walkthrough")
    print("=" * 60)

    steps = ["1", "1a", "1b", "2", "10", "10a"]
    sorted_steps = sort_step_identifiers(steps)

    print(f"Guide steps: {sorted_steps}\n")

    current = sorted_steps[0]
    step_number = 1

    while current is not None:
        print(f"Step {step_number}: {current}")

        # Check if there's a next step
        next_step = get_next_identifier(current, sorted_steps)
        if next_step:
            print(f"  -> Next: {next_step}")
        else:
            print(f"  -> [End of guide]")

        current = next_step
        step_number += 1

    print()


def example_edge_cases():
    """Example 6: Edge cases and special scenarios."""
    print("=" * 60)
    print("Example 6: Edge Cases")
    print("=" * 60)

    # Empty list
    print(f"Empty list: {sort_step_identifiers([])}")

    # Single element
    print(f"Single element: {sort_step_identifiers(['1'])}")

    # With duplicates
    print(f"With duplicates: {sort_step_identifiers(['1', '2', '1', '10'])}")

    # Large numbers
    print(f"Large numbers: {sort_step_identifiers(['1', '10', '100', '1000'])}")

    # Multiple letter suffixes
    print(f"Letter suffixes: {sort_step_identifiers(['1d', '1a', '1c', '1b'])}")

    # Invalid identifiers
    print(f"With invalid: {sort_step_identifiers(['1', 'abc', '2'])}")

    print()


def example_parse_keys():
    """Example 7: Understanding natural_sort_key."""
    print("=" * 60)
    print("Example 7: Natural Sort Keys")
    print("=" * 60)

    identifiers = ["1", "1a", "10", "10a", "2", "abc", ""]

    print("Identifier -> (numeric, letter) sort key")
    print("-" * 40)
    for identifier in identifiers:
        key = natural_sort_key(identifier)
        print(f"'{identifier:5}' -> {key}")

    print()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + " Natural Sorting Utility - Usage Examples ".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    example_basic_sorting()
    example_navigation()
    example_comparison()
    example_progress_tracking()
    example_full_walkthrough()
    example_edge_cases()
    example_parse_keys()

    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
