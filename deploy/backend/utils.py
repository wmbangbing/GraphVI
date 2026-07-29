"""Shared utility functions."""


def primary_label(labels: list[str], ignored: str = "") -> str:
    """Return the first label that is NOT the ignored label.

    Args:
        labels: list of node labels
        ignored: label to skip (e.g. '_Embeddable'), case-sensitive
    """
    if not labels:
        return "?"
    if not ignored:
        return labels[0]
    for lbl in labels:
        if lbl != ignored:
            return lbl
    return labels[0]  # fallback: all labels are ignored
