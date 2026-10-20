"""Conservative, deterministic report checks; not a substitute for human semantic review."""

import re


def source_timing_review(spec, post):
    notes = []
    close_exit = re.search(
        r"\b(?:exit|sell)\s+(?:at|on)\s+(?:the\s+)?(?:next\s+day.s\s+|next\s+session.s\s+|next\s+)?(?:market\s+)?close\b",
        post.body,
        re.I,
    )
    if close_exit:
        notes.append(
            dict(
                rule="exit",
                effective_label="declared assumption",
                detail="The source specifies a close exit. This engine fills at the next open after a completed-bar exit signal, so exit timing is an interpretation rather than exact reproduction, regardless of the model's original evidence label.",
            )
        )
    return notes
