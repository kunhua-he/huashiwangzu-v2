"""Context injectors: lightweight, replaceable stages that add prompt-level guidance.

Each injector follows the same contract:
    inject(messages, diagnosis, **kwargs) -> (messages, diagnosis)

This makes them independently testable and easy to reorder.
"""
