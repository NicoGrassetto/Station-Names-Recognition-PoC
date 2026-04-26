"""State interface and concrete state implementations.

Each state is bound to a ``.prompty`` file via the ``prompt_name`` class
attribute. Call :meth:`State.load_prompt` to resolve the system prompt text
through the existing :mod:`prompts` loader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Optional

from prompts import load_prompt


class State(ABC):
    """Abstract base class defining the State interface."""

    #: Name of the ``.prompty`` file (without extension) backing this state.
    prompt_name: ClassVar[str]

    def load_prompt(self) -> str:
        """Return the system prompt text associated with this state."""
        return load_prompt(self.prompt_name)

    @abstractmethod
    def cancel(self) -> Optional["State"]:
        """Cancel the current state and return the next state (if any)."""

    @abstractmethod
    def confirm(self) -> Optional["State"]:
        """Confirm the current state and return the next state (if any)."""


class LanguageSelectionState(State):
    prompt_name = "language_selection"

    def cancel(self) -> Optional[State]:
        return EndState()

    def confirm(self) -> Optional[State]:
        return ProductSelectionState()


class ProductSelectionState(State):
    prompt_name = "product_selection"

    def cancel(self) -> Optional[State]:
        return LanguageSelectionState()

    def confirm(self) -> Optional[State]:
        return DestinationSelectionState()


class DestinationSelectionState(State):
    prompt_name = "destination_selection"

    def cancel(self) -> Optional[State]:
        return ProductSelectionState()

    def confirm(self) -> Optional[State]:
        return DetailsSelectionState()


class DetailsSelectionState(State):
    prompt_name = "details_selection"

    def cancel(self) -> Optional[State]:
        return DestinationSelectionState()

    def confirm(self) -> Optional[State]:
        return ConfirmationState()


class ConfirmationState(State):
    prompt_name = "confirmation"

    def cancel(self) -> Optional[State]:
        return DetailsSelectionState()

    def confirm(self) -> Optional[State]:
        return EndState()


class EndState(State):
    prompt_name = "end"

    def cancel(self) -> Optional[State]:
        return None

    def confirm(self) -> Optional[State]:
        return None
