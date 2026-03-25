class StorageMetaData:
    def __init__(self, *args, **kwargs):
        pass


def add_annotation(*args, **kwargs):
    return "annotation-id"


def get_storage_create(*args, **kwargs):
    class DummyStorage:
        def __init__(self):
            self.annotations_storage = self
            self.storage_name = args[0] if args else ""

        def __len__(self):
            return 0

        def add_many(self, items):
            return []

        def get(self):
            return []

        def __getitem__(self, key):
            raise KeyError(key)

    return DummyStorage()
