import sys
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


def create_diff_edits(item_text2, item_shadow2):
    diff = None
    text_patches2 = None
    if item_shadow2 is None:
        text_patches2 = None
    else:
        diff_obj = diff_match_patch.diff_match_patch()
        diff_obj.Diff_Timeout = 1
        diff = diff_obj.diff_main(item_shadow2, item_text2)
        diff_obj.diff_cleanupSemantic(diff)  # FIXME: optional?
        patch = diff_obj.patch_make(diff)
        if patch:
            text_patches2 = diff_obj.patch_toText(patch)
        else:
            text_patches2 = None
    return text_patches2


def user_0_create():
    # create node id if it doesn't exist
    # node_id = uuid.uuid4().hex
    node_id = "node_1"

    # create new item
    # item_id = uuid.uuid4().hex
    item_id = "item_1"
    item_text = "original text"
    print("node_id = " + node_id)

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    @firestore.transactional
    def create_in_transaction(transaction1, item_id, item_text):
        try:
            client_rev = 0
            node_ref = db.collection('nodes').document(node_id)
            item_ref = node_ref.collection('items').document(item_id)
            transaction1.set(item_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                # 'last_update_date': firestore.SERVER_TIMESTAMP,
                'text': item_text,
                'client_rev': client_rev,
            })
            queue_ref = item_ref.collection('queue_1_to_process').document(str(client_rev))
            transaction1.set(queue_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'client_rev': client_rev,
                'action': 'create_item'
            })
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            print("Connection error to Firestore")
            return False
        print("edit enqueued")
        return True

    result = create_in_transaction(transaction, item_id, item_text)
    if result:
        print('transaction ended OK')
    else:
        print('ERROR saving new item')
        raise Exception


def user_1_update():
    # the edit is queued and the user closes the screen
    # the server is currently offline so the edits stay enqueued
    # the user reopens the screen so the data has to be loaded:

    print("recovering item...")

    node_id = "node_1"
    item_id = "item_1"

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    old_item = None
    try:
        old_item = item_ref.get()
        print('Document data: {}'.format(old_item.to_dict()))
    except google.cloud.exceptions.NotFound:
        print('No such document!')
        raise Exception
    if not old_item:
        raise Exception
    print("recovered data ok")

    old_text = None
    client_rev = None
    try:
        old_text = old_item.get('text')
        client_rev = old_item.get('client_rev')
    except KeyError:
        print("ERROR recovering the item text")
        sys.exit(0)

    old_shadow = old_text
    try:
        old_shadow = old_item.get('shadow')
    except KeyError:
        pass

    # the user changes the text so a new set of edits has to be created and enqueued
    new_text = "new text"

    # create edits
    text_patches = create_diff_edits(new_text, old_shadow)
    # print(text_patches)

    # prepare the update of shadow and client text revision

    db = firestore.Client()

    transaction = db.transaction()

    @firestore.transactional
    def update_in_transaction(transaction1, node_id1, item_id1, client_rev1, new_text1, text_patches1):
        try:
            new_client_rev = client_rev1 + 1
            new_item_shadow = new_text1
            node_ref = db.collection('nodes').document(node_id1)
            item_ref1 = node_ref.collection('items').document(item_id1)
            transaction1.update(item_ref1, {
                'last_update_date': firestore.SERVER_TIMESTAMP,
                'text': new_text1,
                'shadow': new_item_shadow,
                'client_rev': new_client_rev,
            })
            queue_ref = item_ref.collection('queue_1_to_process').document(str(new_client_rev))
            transaction1.set(queue_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'client_rev': new_client_rev,
                'action': 'edit_item',
                'text_patches': text_patches1
            })
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            print("Connection error to Firestore")
            return False
        print("edit enqueued")
        return True

    result = update_in_transaction(transaction, node_id, item_id, client_rev, new_text, text_patches)
    if result:
        print('transaction 2 ended OK')
    else:
        print('ERROR updating item')
        raise Exception


def user_2_update():
    # once again the edit is queued and the user closes the screen
    # the server is currently offline so the edits stay enqueued
    # the user reopens the screen so the data has to be loaded

    print("recovering item again...")

    node_id = "node_1"
    item_id = "item_1"

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    old_item = None
    try:
        old_item = item_ref.get()
        print('Document data: {}'.format(old_item.to_dict()))
    except google.cloud.exceptions.NotFound:
        print('No such document!')
        raise Exception
    if not old_item:
        raise Exception
    print("recovered data ok")

    old_text = None
    client_rev = None
    try:
        old_text = old_item.get('text')
        client_rev = old_item.get('client_rev')
    except KeyError:
        print("ERROR recovering the item text")
        sys.exit(0)

    old_shadow = old_text
    try:
        old_shadow = old_item.get('shadow')
    except KeyError:
        pass

    # the user changes the text so a new set of edits has to be created and enqueued
    new_text = "really new text"

    # create edits
    text_patches = create_diff_edits(new_text, old_shadow)
    # print(text_patches)

    # prepare the update of shadow and client text revision

    db = firestore.Client()

    transaction = db.transaction()

    @firestore.transactional
    def update_in_transaction(transaction1, node_id1, item_id1, client_rev1, new_text1, text_patches1):
        try:
            new_client_rev = client_rev1 + 1
            new_item_shadow = new_text1
            node_ref = db.collection('nodes').document(node_id1)
            item_ref1 = node_ref.collection('items').document(item_id1)
            transaction1.update(item_ref1, {
                'last_update_date': firestore.SERVER_TIMESTAMP,
                'text': new_text1,
                'shadow': new_item_shadow,
                'client_rev': new_client_rev,
            })
            queue_ref = item_ref.collection('queue_1_to_process').document(str(new_client_rev))
            transaction1.set(queue_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'client_rev': new_client_rev,
                'action': 'edit_item',
                'text_patches': text_patches1
            })
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            print("Connection error to Firestore")
            return False
        print("edit enqueued")
        return True

    result = update_in_transaction(transaction, node_id, item_id, client_rev, new_text, text_patches)
    if result:
        print('transaction 3 ended OK')
    else:
        print('ERROR updating item')
        raise Exception


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

    # user_0_create()
    # user_1_update()
    # user_2_update()

    #
    # end UI client part, start the queue part
    #

    # read the queues

    node_id = "node_1"
    item_id = "item_1"

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)
    # queue = item_ref.collection('queue').where('status', '==', 'recorded_in_queue').order_by('client_rev').get()
    queue = item_ref.collection('queue_1_to_process').order_by('client_rev').limit(1).get()

    for queue_instance in queue:
        print("processing item {} queue {}".format(item_id, queue_instance.id,))
        # print("contents {}".format(queue_instance.to_dict()))

        break
    else:
        raise Exception

    # transaction = db.transaction()
    #
    # @firestore.transactional
    # def send_queue1(transaction1, node_id1, item_id1, client_rev1, new_text1, text_patches1):
    #     try:
    #         new_client_rev = client_rev1 + 1
    #         new_item_shadow = new_text1
    #         node_ref = db.collection('nodes').document(node_id1)
    #         item_ref1 = node_ref.collection('items').document(item_id1)
    #         transaction1.update(item_ref1, {
    #             'last_update_date': firestore.SERVER_TIMESTAMP,
    #             'text': new_text1,
    #             'shadow': new_item_shadow,
    #             'client_rev': new_client_rev,
    #         })
    #         queue_ref = item_ref.collection('queue_1_to_process').document(str(new_client_rev))
    #         transaction1.set(queue_ref, {
    #             'create_date': firestore.SERVER_TIMESTAMP,
    #             'client_rev': new_client_rev,
    #             'action': 'edit_item',
    #             'text_patches': text_patches1
    #         })
    #     except (grpc._channel._Rendezvous,
    #             google.auth.exceptions.TransportError,
    #             google.gax.errors.GaxError,
    #             ):
    #         print("Connection error to Firestore")
    #         return False
    #     print("edit enqueued")
    #     return True
    #
    # result = update_in_transaction(transaction, node_id, item_id, client_rev, new_text, text_patches)

    sys.exit(0)
