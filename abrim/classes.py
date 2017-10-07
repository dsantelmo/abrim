import uuid
#import sqlite3
from google.cloud import firestore



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
class FirestoreDatasore(object):
    db = None
  
    def __init__(self):
        self.connect()
        self.init()
        self.close()

    def connect(self):
        self.db = firestore.Client()

    def init(self):
        pass

    def clear(self):
        self.__delete_collection(self.db.collection('items'), 10)
        pass

    def close(self):
        pass

    def insert_item(self, item_uuid, title=None, text=None):
        try:
            item_ref = self.db.collection('items').document(item_uuid.hex)
            item_ref.set({
                'title': title,
                'text':  text,
            })
        except:
            raise Exception
        self.close()

    def save_text(self, item_uuid, text):
        if not item_uuid or not text:
            raise Exception
        else:
            item_ref = self.db.collection('items').document(item_uuid.hex)
            item_ref.update({'text':  text, })

    def read_text(self, item_uuid):
        if not item_uuid:
            raise Exception
        else:
            item_ref = self.db.collection('items').document(item_uuid.hex)
            items_get = item_ref.get().get('text')
            return items_get

    def __delete_collection(self, coll_ref, batch_size):
        docs = coll_ref.limit(10).get()
        deleted = 0

        for doc in docs:
            print(u'Deleting doc {} => {}'.format(doc.id, doc.to_dict()))
            doc.reference.delete()
            deleted = deleted + 1

        if deleted >= batch_size:
            return self.__delete_collection(coll_ref, batch_size)

class Item(object):
    datastore = None
    id = None
    _texts = []
    __shadow = None
    __datastore = None

    def __create_uuid(self):
        return uuid.uuid4()
  
    def __check_id_exists(self, id):
        return False
        # FIXME raise Exception
  
    def __init__(self, init_datastore, id=None):
        if not init_datastore:
            raise Exception
        else:
            self.__datastore = init_datastore
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
            self.__datastore.insert_item(self.id)
        self.__datastore.close()
        self.__init_datastore(self.__datastore)

    @classmethod
    def __init_datastore(cls, datastore):
        cls.__datastore = datastore

    @classmethod
    def from_existing_id(cls, id):
        return cls(id)

    #@classmethod
    #def set_text(cls, text):
    def set_text(self, text):
        self.__datastore.save_text(self.id, text)

    #@classmethod
    #def get_text(cls):
    def get_text(self):
        return self.__datastore.read_text(self.id)

if __name__ == "__main__":
    print("RUNNING AS MAIN!")  # FIXME
    my_datastore = FirestoreDatasore()
    my_datastore.clear()
    item = Item(my_datastore)
    print(item.id)
    item.set_text("test 1")
    print(item.get_text())
    item.set_text("test 2")
    print(item.get_text())
