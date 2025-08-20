class ResultTracker:
    def __init__(self):
        self._counters = {
            "missing": 0,
            "valid": 0,
            "errors": 0,
            "fallbacks": 0,
            "outliers": 0,
            "invalid_min_max": 0,
            "imported": 0,
            "ignored": 0,
            "imputed": 0,
            "bound_warnings": 0
        }

    def add_missing(self, amount=1): self._counters["missing"] += amount
    def add_valid(self, amount=1): self._counters["valid"] += amount
    def add_error(self, amount=1): self._counters["errors"] += amount
    def add_bound_warning(self, amount=1): self._counters["bound_warnings"] += amount
    def add_invalid_min_max(self, amount=1): self._counters["invalid_min_max"] += amount
    def add_imported(self, amount=1): self._counters["imported"] += amount
    def add_ignored(self, amount=1): self._counters["ignored"] += amount
    def add_fallback(self, amount=1): self._counters["fallbacks"] += amount
    def add_imputed(self, amount=1): self._counters["imputed"] += amount

    def get_summary(self):
        return self._counters.copy()

    def __str__(self):
        return " | ".join(f"{k}: {v}" for k, v in self._counters.items())

    def reset(self):
        for k in self._counters:
            self._counters[k] = 0
