def get_storage(*args, **kwargs):
    class DummyStorage:
        def get_storage_create(self, name, parent_id=None):
            return self

        def __len__(self):
            return 0

        def add_many(self, items):
            return []

        def get(self):
            return []

        def __getitem__(self, key):
            raise KeyError(key)

    return DummyStorage()


def match_storage(*args, **kwargs):
    return []


def get_unprocessed_entries(*args, **kwargs):
    return []


def get_multi_unprocessed_entries(*args, **kwargs):
    return []


def get_unprocessed_annotations(*args, **kwargs):
    return []


def process_new_entries_for_events(*args, **kwargs):
    pass


def rr_server_running(*args, **kwargs):
    return False


def can_run_bulk_commands(*args, **kwargs):
    return False


def reset_scanning_data(*args, **kwargs):
    pass
