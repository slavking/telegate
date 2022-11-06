import pickle, os


class PickleDict(dict):
    def __init__(self, path=None):
        self._path = path
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                super().__init__(data)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.save()

    def __delitem__(self, key):
        super().__delitem__(key)
        self.save()

    def update(self, data):
        super().update(data)
        self.save()

    def save(self):
        if not hasattr(self, '_path'):
            return
        with open(self._path+'_', 'wb') as f:
            pickle.dump(dict(self), f)
        os.rename(self._path+'_', self._path)
