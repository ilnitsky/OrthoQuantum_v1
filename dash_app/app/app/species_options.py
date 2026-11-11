"""Promote common reference species only when present in the selected tree."""
COMMON_TAXIDS = (9606, 10090, 7955, 7227, 6239, 10116, 9031, 8364,
                 9913, 9615, 9598, 4932, 4896, 3702)


def preferred_species(options):
    priority = {taxid: index for index, taxid in enumerate(COMMON_TAXIDS)}
    def order(option):
        try:
            rank = priority.get(int(option['value']), len(priority))
        except (ValueError, TypeError):
            rank = len(priority)
        return rank, str(option['label']).casefold()
    return sorted(options, key=order)
