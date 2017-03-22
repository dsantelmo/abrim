import uuid

class Item(object):
    id = None
    text = None
    shadow = None

    def __create_uuid(self):
        return uuid.uuid4()
  
    def __check_id_exists(self, id):
        return True
  
    def __init__(self, id=None):
        if id:
            if isinstance(id, uuid.UUID):
                print("init desde id")
                self.id = id
            else:
                raise Exception
        else:
            print("init sin id")
            self.id = self.__create_uuid()
        print(self.id.hex)
        if self.__check_id_exists(id):
            raise Exception

    @classmethod
    def from_existing_id(cls, id):
        return cls(id)


