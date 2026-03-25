class MultiDict(dict):
    def add(self, key, value):
        if key in self:
            existing = self[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                self[key] = [existing, value]
        else:
            self[key] = value
