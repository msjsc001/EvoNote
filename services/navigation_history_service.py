from __future__ import annotations

from typing import Optional, Tuple
import logging

from core.signals import GlobalSignalBus

logger = logging.getLogger(__name__)

__all__ = ["NavigationHistoryService"]

class NavigationHistoryService:
    """
    Navigation history manager with a bounded list and movable cursor.

    - Stores vault-relative page paths including extension (e.g., 'Note A.md', 'pages/Note A.md').
    - Allows duplicates in history but prevents consecutive duplicates on push.
    - All methods are defensive: exceptions are caught and logged via logging.warning without raising.
    - Emits nav_history_state_changed on the GlobalSignalBus after initialization and whenever state may change.
    """

    _items: list[str]
    _idx: int
    _maxlen: int

    def __init__(self, maxlen: int = 50) -> None:
        """
        Initialize the navigation history.

        Args:
            maxlen (int): Maximum number of items to keep in history. Defaults to 50.
                          Values less than 1 are clamped to 1.

        Side effects:
            Broadcasts an initial state via GlobalSignalBus.nav_history_state_changed.
        """
        try:
            self._items = []
            self._idx = -1  # -1 means 'no current item'
            try:
                self._maxlen = int(maxlen)
            except Exception:
                self._maxlen = 50
            if self._maxlen < 1:
                self._maxlen = 1
        except Exception as e:
            logger.warning("NavigationHistoryService.__init__: failed to initialize fields: %s", e, exc_info=True)
            # Ensure minimally valid state even on failure paths
            self._items = []
            self._idx = -1
            self._maxlen = 50
        # Always emit initial state
        self._emit_state()

    def state(self) -> tuple[bool, bool, str]:
        """
        Get current navigation state as a tuple: (can_back, can_forward, current_page or '').

        Returns:
            tuple[bool, bool, str]: Whether back/forward are available and the current page path.
        """
        try:
            can_back, can_forward, current = self._compute_state()
            return can_back, can_forward, current
        except Exception as e:
            logger.warning("NavigationHistoryService.state: error computing state: %s", e, exc_info=True)
            return False, False, ""

    def push(self, page_path: str) -> None:
        """
        Push a new page onto the history, trimming any forward segment first.

        Rules:
          - Empty strings are ignored.
          - If equal to current item, ignore (prevents consecutive duplicates).
          - If cursor not at the end, drop the forward slice and then append.
          - If size exceeds maxlen after append, drop oldest items and fix cursor.

        Side effects:
          - Emits the updated state after processing (even if ignored).
        """
        try:
            page = (page_path or "").strip()
            if not page:
                return
            current = self._items[self._idx] if 0 <= self._idx < len(self._items) else None
            if page == current:
                # Consecutive duplicate: ignore
                return

            # Remove forward history if cursor is not at the end
            if self._idx < len(self._items) - 1:
                self._items = self._items[: self._idx + 1]

            # Append and move cursor
            self._items.append(page)
            self._idx = len(self._items) - 1

            # Enforce capacity by dropping from the head
            overflow = len(self._items) - self._maxlen
            if overflow > 0:
                # Drop oldest 'overflow' items; adjust cursor accordingly
                del self._items[:overflow]
                self._idx -= overflow
        except Exception as e:
            logger.warning("NavigationHistoryService.push: error while pushing '%s': %s", page_path, e, exc_info=True)
        finally:
            # Emit state regardless of outcome
            self._emit_state()

    def back(self) -> str | None:
        """
        Move the cursor one step back if possible.

        Returns:
            str | None: The new current page path when a step back is possible; otherwise None.
        Side effects:
            Always emits the state after the call.
        """
        result: Optional[str] = None
        try:
            if self._idx > 0:
                self._idx -= 1
                if 0 <= self._idx < len(self._items):
                    result = self._items[self._idx]
        except Exception as e:
            logger.warning("NavigationHistoryService.back: error: %s", e, exc_info=True)
        finally:
            self._emit_state()
        return result

    def forward(self) -> str | None:
        """
        Move the cursor one step forward if possible.

        Returns:
            str | None: The new current page path when a step forward is possible; otherwise None.
        Side effects:
            Always emits the state after the call.
        """
        result: Optional[str] = None
        try:
            if 0 <= self._idx < len(self._items) - 1:
                self._idx += 1
                if 0 <= self._idx < len(self._items):
                    result = self._items[self._idx]
        except Exception as e:
            logger.warning("NavigationHistoryService.forward: error: %s", e, exc_info=True)
        finally:
            self._emit_state()
        return result

    def clear(self) -> None:
        """
        Clear the entire history and reset the cursor.

        Side effects:
            Emits the state after clearing.
        """
        try:
            self._items.clear()
            self._idx = -1
        except Exception as e:
            logger.warning("NavigationHistoryService.clear: error: %s", e, exc_info=True)
        finally:
            self._emit_state()

    def set_maxlen(self, n: int) -> None:
        """
        Update the maximum history length.

        Rules:
          - If n < 1: ignore.
          - When shrinking, drop from the head first and adjust the cursor.
            If dropping only from the head would remove the current item, additionally
            drop from the tail so the current item is preserved ("不破坏当前项").

        Side effects:
          - Emits the state after applying the change.
        """
        try:
            if n is None:
                return
            try:
                n_int = int(n)
            except Exception:
                return
            if n_int < 1:
                return

            old_len = len(self._items)
            idx = self._idx
            if n_int < old_len and old_len > 0:
                required = old_len - n_int
                # Prefer dropping from the head, but never past the current item
                drop_head = min(required, max(0, idx))
                # After dropping head, how many still need to be dropped
                remaining = required - drop_head
                # Apply head drop
                if drop_head > 0:
                    del self._items[:drop_head]
                    idx -= drop_head
                # Drop remaining from tail (forward) if still needed
                if remaining > 0:
                    # Compute tail slice to keep
                    keep_len = len(self._items) - remaining
                    if keep_len < 0:
                        keep_len = 0
                    self._items = self._items[:keep_len]
                # Fix cursor within bounds
                if idx >= len(self._items):
                    idx = len(self._items) - 1
                self._idx = idx

            # Finally set new capacity
            self._maxlen = n_int
        except Exception as e:
            logger.warning("NavigationHistoryService.set_maxlen: error: %s", e, exc_info=True)
        finally:
            self._emit_state()

    def _emit_state(self) -> None:
        """
        Compute and emit the current state via GlobalSignalBus.nav_history_state_changed.

        Emitted payload:
            can_back (bool), can_forward (bool), current_page (str; '' when none)
        """
        try:
            can_back, can_forward, current = self._compute_state()
            # Emit signal (no-throw best effort)
            try:
                GlobalSignalBus.nav_history_state_changed.emit(can_back, can_forward, current)
            except Exception as e:
                # Emission should never break callers
                logger.warning("NavigationHistoryService._emit_state: emit failed: %s", e, exc_info=True)
        except Exception as e:
            logger.warning("NavigationHistoryService._emit_state: compute failed: %s", e, exc_info=True)

    def _compute_state(self) -> tuple[bool, bool, str]:
        """
        Internal helper: compute (can_back, can_forward, current_page).
        """
        l = len(self._items)
        idx = self._idx
        can_back = idx > 0
        can_forward = 0 <= idx < (l - 1)
        current = self._items[idx] if 0 <= idx < l else ""
        return can_back, can_forward, current