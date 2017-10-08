import uuid
#import sqlite3
import diff_match_patch
from google.cloud import firestore
import grpc
import google



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
class FirestoreDatastore(object):
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
                'create_date': firestore.SERVER_TIMESTAMP,
                'last_update_date': firestore.SERVER_TIMESTAMP,
                'title': title,
                'text':  text,
                'shadows': {
                    'create_date': firestore.SERVER_TIMESTAMP,
                    'text': None,
                    'client_rev': None,
                    'server_rev': None,
                },
                'edits': {
                    'create_date': firestore.SERVER_TIMESTAMP,
                    'client_rev': None,
                    'server_rev': None,
                },
            })
        except:
            raise Exception
        self.close()

    def save_text(self, item_uuid, text):
        if not item_uuid or not text:
            raise Exception
        else:
            item_ref = self.db.collection('items').document(item_uuid.hex)
            item_ref.update({
                'last_update_date': firestore.SERVER_TIMESTAMP,
                'text':  text,
                'shadow': {
                    'text': None,
                    'client_rev': None,
                    'server_rev': None,
                },
            }, firestore.CreateIfMissingOption(True))


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
    id = None
    __text = None
    __shadow = None
    __datastore = None

    def __create_uuid(self):
        return uuid.uuid4()
  
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
    def set_text(self, new_text):
        self.__text = text
        self.__datastore.save_text(self.id, text)

    #@classmethod
    #def get_text(cls):
    def get_text(self):
        return self.__datastore.read_text(self.id)


if __name__ == "__main__":
    print("RUNNING AS MAIN!")  # FIXME
    # my_datastore = FirestoreDatastore()
    # my_datastore.clear()
    # item = Item(my_datastore)
    # print(item.id)
    # item.set_text("test 1")
    # print(item.get_text())
    # item.set_text("test 2")
    # print(item.get_text())

    # create node id if it doesn't exist
    node_id = uuid.uuid4()

    # create new item
    item_text = "original text"
    item_shadow = None
    client_rev = 0

    if not item_text:
        raise Exception

    # create ID
    item_id = uuid.uuid4()

    # create edits
    diff = None
    if item_shadow is None:
        text_patches = None
    else:
        diff_obj = diff_match_patch.diff_match_patch()
        diff_obj.Diff_Timeout = 1
        diff = diff_obj.diff_main(item_shadow, item_text)
        diff_obj.diff_cleanupSemantic(diff)  # FIXME: optional?
        patch = diff_obj.patch_make(diff)
        if patch:
            text_patches = diff_obj.patch_toText(patch)
        else:
            text_patches = None

    print(text_patches)

    # prepare the update of shadow and client text revision
    new_client_rev = client_rev + 1
    new_item_shadow = item_text

    # enqueue edits and save new item to datastore
    db = firestore.Client()
    item_ref = db.collection('nodes').document(node_id.hex).collection('items').document(item_id.hex)
    try:
        item_ref.set({
            #'create_date': firestore.SERVER_TIMESTAMP,
            'last_update_date': firestore.SERVER_TIMESTAMP,
            'text': item_text,
            'shadow_text': new_item_shadow,
            'client_rev': new_client_rev,
            'edits_queue': {
                'create_date': firestore.SERVER_TIMESTAMP,
                'client_rev': client_rev,
                'patches': text_patches,
            },
        })
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        print("Connection error to Firestore")
        raise Exception
    print("edit enqueued")

    # the edit is queued and the user closes the screen
    # the server is currently offline so the edits stay enqueued
    # the user reopens the screen so the data has to be loaded:

    old_text = None
    shadow_text = None
    client_rev = None
    if not item_id:
        raise Exception
    else:
        item_ref = db.collection('nodes').document(node_id.hex).collection('items').document(item_id.hex)
        try:
            old_item = item_ref.get()
            print('Document data: {}'.format(old_item.to_dict()))

            # the user changes some text so a new edit has to be created and enqueued
            if not old_item.exists:
                raise Exception
            else:
                try:
                    old_text = old_item.get("text")
                    shadow_text = old_item.get("shadow_text")
                    client_rev = old_item.get("client_rev")
                except KeyError:
                    raise Exception
        except google.cloud.exceptions.NotFound:
            print('No such document!')
            raise Exception

    print("recovered data ok")

    # the user changes the text so a new set of edits has to be created and enqueued
    new_text = "new text"

    if not new_text:
        raise Exception

    # create edits
    diff = None
    if shadow_text is None:
        text_patches = None
    else:
        diff_obj = diff_match_patch.diff_match_patch()
        diff_obj.Diff_Timeout = 1
        diff = diff_obj.diff_main(shadow_text, new_text)
        diff_obj.diff_cleanupSemantic(diff)  # FIXME: optional?
        patch = diff_obj.patch_make(diff)
        if patch:
            text_patches = diff_obj.patch_toText(patch)
        else:
            text_patches = None

    print(text_patches)

    # prepare the update of shadow and client text revision
    new_client_rev = client_rev + 1
    new_item_shadow = new_text
    