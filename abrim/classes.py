import uuid
import sqlite3



# START EXTERNAL CODE
# from http://code.activestate.com/recipes/413268/
# Created by Zoran Isailovski on Wed, 4 May 2005 (PSF)
# Licensed under the PSF License

######################################################################
##
## Feature Broker
##
######################################################################

class FeatureBroker:
   def __init__(self, allowReplace=False):
      self.providers = {}
      self.allowReplace = allowReplace
   def Provide(self, feature, provider, *args, **kwargs):
      if not self.allowReplace:
         assert not self.providers.has_key(feature), "Duplicate feature: %r" % feature
      if callable(provider):
         def call(): return provider(*args, **kwargs)
      else:
         def call(): return provider
      self.providers[feature] = call
   def __getitem__(self, feature):
      try:
         provider = self.providers[feature]
      except KeyError:
         raise KeyError("Unknown feature named %r" % feature)
      return provider()

features = FeatureBroker()

######################################################################
##
## Representation of Required Features and Feature Assertions
##
######################################################################

#
# Some basic assertions to test the suitability of injected features
#

def NoAssertion(obj): return True

def IsInstanceOf(*classes):
   def test(obj): return isinstance(obj, classes)
   return test

def HasAttributes(*attributes):
   def test(obj):
      for each in attributes:
         if not hasattr(obj, each): return False
      return True
   return test

def HasMethods(*methods):
   def test(obj):
      for each in methods:
         try:
            attr = getattr(obj, each)
         except AttributeError:
            return False
         if not callable(attr): return False
      return True
   return test

#
# An attribute descriptor to "declare" required features
#

class RequiredFeature(object):
   def __init__(self, feature, assertion=NoAssertion):
      self.feature = feature
      self.assertion = assertion
   def __get__(self, obj, T):
      return self.result # <-- will request the feature upon first call
   def __getattr__(self, name):
      assert name == 'result', "Unexpected attribute request other then 'result'"
      self.result = self.Request()
      return self.result
   def Request(self):
      obj = features[self.feature]
      assert self.assertion(obj), \
             "The value %r of %r does not match the specified criteria" \
             % (obj, self.feature)
      return obj

class Component(object):
   "Symbolic base class for components"

# END EXTERNAL CODE


# support for UUID type in SQLite
def _uuid_coverter(uuid_bytes):
    return uuid.UUID(bytes_le=uuid_bytes)

# support for UUID type in SQLite
def _uuid_adapter(uuid_obj):
    return buffer(uuid_obj.bytes_le)

# FIXME: fix this crap
class SqliteDatasore(object):
    path = None
    conn = None
  
    def __init__(self, path="delete_me.sqlite"):
        if not path:
            raise Exception
        else:
            self.path = path
        self.connect()
        self.init()
        self.close()

    def connect(self):
        # support for UUID type in SQLite
        #sqlite3.register_converter('UUID', _uuid_coverter)
        #sqlite3.register_adapter(uuid.UUID, _uuid_adapter)
        #self.conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn = sqlite3.connect(self.path)

    def init(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS items (
          uuid          TEXT    PRIMARY KEY,
          title         TEXT    ,--NOT NULL,
          text          TEXT    --NOT NULL
        );""")
        self.close()

    def clear(self):
        c = self.conn.cursor()
        c.execute("""DROP TABLE IF EXISTS items;""")
        self.conn.commit()
        self.init()
        self.close()

    def close(self):
        self.conn.commit()

    def insert(self, item_uuid, title=None, text=None):
        try:
            c = self.conn.cursor()
            c.execute("INSERT INTO items (uuid, title, text) VALUES (?, ?, ?);", (item_uuid.hex, title, text,))
        except sqlite3.IntegrityError:
            raise Exception
        self.close()


class Item(object):
    datastore = None
    id = None
    _text = None
    __shadow = None

    def __create_uuid(self):
        return uuid.uuid4()
  
    def __check_id_exists(self, id):
        return False
        # FIXME raise Exception
  
    def __init__(self, datastore, id=None):
        if not datastore:
            raise Exception

        if id:
            if isinstance(id, uuid.UUID):
                self.id = id
            else:
                raise Exception
        else:
            self.id = self.__create_uuid()

        if self.__check_id_exists(id):
            raise Exception
        else:
            datastore.insert(self.id)
        datastore.close()

    @classmethod
    def from_existing_id(cls, id):
        return cls(id)

    @classmethod
    def set_text(cls, text):
        cls._text = text

    @classmethod
    def get_text(cls):
        return cls._text

if __name__ == "__main__":
    print("RUNNING AS MAIN!")  # FIXME
    datastore = SqliteDatasore()
    datastore.clear()
    item = Item(datastore)
    print(item.id)
    item.set_text("test 1")
    print(item.get_text())
    item.set_text("test 2")
    print(item.get_text())
