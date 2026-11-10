def toggle_selection(data, selected):
    """Select every result row, or clear an already complete selection."""
    rows = list(range(len(data or [])))
    return [] if set(rows).issubset(set(selected or [])) else rows
