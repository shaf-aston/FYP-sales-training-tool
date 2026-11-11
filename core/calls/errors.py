"""Why a call could not be read. The route turns each code into words (backend/messages.py)."""

CALL_UNREADABLE = "CALL_UNREADABLE"   # no format found speaker turns in it
CALL_TOO_LONG = "CALL_TOO_LONG"       # over limits.max_chars
CALL_TOO_SHORT = "CALL_TOO_SHORT"     # fewer than limits.min_turns turns or min_speakers speakers
UNKNOWN_SPEAKER = "UNKNOWN_SPEAKER"   # the learner named a rep who does not speak in the call


class CallError(ValueError):
    """A transcript the reader refuses, with one of the codes above."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
