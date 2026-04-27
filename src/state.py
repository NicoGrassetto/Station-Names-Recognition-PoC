"""Booking flow finite-state automaton.

Each state owns its system prompt (a ``.prompty`` file in :mod:`prompts`)
and knows its successors via :meth:`State.confirm` and :meth:`State.cancel`.

The states are pure: they hold no per-session data. The runtime instance
attached to a connection lives on :class:`src.session.Session.state` and
the collected slot values live on :class:`src.booking.BookingSession`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar, Optional

from prompts import load_prompt

logger = logging.getLogger("state")


class State(ABC):
    #: Name of the ``.prompty`` file (without extension) backing this state.
    prompt_name: ClassVar[str]

    @property
    def name(self) -> str:
        return type(self).__name__

    def load_prompt(self) -> str:
        return load_prompt(self.prompt_name)

    @abstractmethod
    def cancel(self) -> Optional["State"]: ...

    @abstractmethod
    def confirm(self) -> Optional["State"]: ...


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
    """Capture the destination station via Azure Custom Speech (NOT Whisper).

    While in this state the WebSocket handler is expected to:
      * keep buffering the inbound PCM16 audio on ``Session.audio_buffer``;
      * when the user signals end-of-speech (``stop`` control message),
        run :func:`src.speech.transcribe_destination_audio` over the buffer
        and assign the result to ``Session.booking.arrival_station``.
    """

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
