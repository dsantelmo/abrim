import uuid

class DatastoreProvider(object):
    path = None
  
    def __init__(self, path=None, ram=None):
        if path:
            raise Exception
        elif ram:
            raise Exception
        else:
            raise Exception

    @classmethod
    def from_path(cls, path):
        return cls(path, None)
       
    @classmethod
    def from_ram(cls):
        return cls(None, True)


class ItemDatastore(object):
    datastore_provider = None
   
    def __init__(self, datastore_provider):
        pass


class Item(object):
    id = None
    text = None
    shadow = None

    def __create_uuid(self):
        return uuid.uuid4()
  
    def __check_id_exists(self, id):
        raise Exception
  
    def __init__(self, id=None):
        if id:
            if isinstance(id, uuid.UUID):
                self.id = id
            else:
                raise Exception
        else:
            self.id = self.__create_uuid()
        if self.__check_id_exists(id):
            raise Exception

    @classmethod
    def from_existing_id(cls, id):
        return cls(id)


