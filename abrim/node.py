#!/usr/bin/env python

import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google
import logging
import os
from pathlib import Path


LOGGING_LEVELS = {'critical': logging.CRITICAL,
                  'error': logging.ERROR,
                  'warning': logging.WARNING,
                  'info': logging.INFO,
                  'debug': logging.DEBUG}
# FIXME http://docs.python-guide.org/en/latest/writing/logging/
# It is strongly advised that you do not add any handlers other
# than NullHandler to your library's loggers.
logging.basicConfig(level=logging.DEBUG,
              format='%(asctime)s __ %(module)-12s __ %(levelname)-8s: %(message)s',
              datefmt='%Y-%m-%d %H:%M:%S')  # ,
              # disable_existing_loggers=False)
logging.StreamHandler(sys.stdout)
log = logging.getLogger(__name__)


class AbrimConfig(object):
    def load_config(self):
        name = "Abrim"
        author = "DST"

        if sys.platform == 'darwin':
            config_folder_path = "~/Library/Application Support/{}".format(name, )
        elif sys.platform == 'win32':
            try:
                appdata = os.environ['APPDATA']
                config_folder_path = "{}/{}/{}".format(appdata, author, name, )
            except KeyError:
                log.error("I think this is a Windows OS and %APPDATA% variable is missing")
                raise
        else:
            config_folder_path = "~/.config/{}".format(name, )

        config_folder = Path(config_folder_path)
        config_file_path = config_folder / "abrim_config.ini"

        if config_file_path.exists():
            log.debug("trying to load config from {}".format(config_file_path, ))
            # create node id if it doesn't exist
            # node_id = uuid.uuid4().hex
            raise Exception  # FIXME: add configparser
        else:
            log.debug("no config file, checking environment variable")
            try:
                self.node_id = os.environ['ABRIM_NODE_ID']
            except KeyError:
                log.error("can't locate NODE_ID value")
                raise

    def __init__(self, node_id=None, db_prefix=None):
        if db_prefix:
            self.db_prefix = db_prefix

        if not node_id:
            self.load_config()
        else:
            self.node_id = node_id


def create_diff_edits(item_text2, item_shadow2):
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


def user_0_create(config, item_id):
    node_id = config.node_id
    db_prefix = config.db_prefix
    db_path = db_prefix + 'nodes'

    # create new item
    item_text = "original text"

    db = firestore.Client()
    node_ref = db.collection('db_path').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    @firestore.transactional
    def create_in_transaction(transaction1, item_ref, item_text):
        try:
            client_rev = 0
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
            log.error("Connection error to Firestore")
            return False
        log.debug("edit enqueued")
        return True

    result = create_in_transaction(transaction, item_ref, item_text)
    if result:
        log.debug('transaction ended OK')
        return True
    else:
        log.error('ERROR saving new item')
        raise Exception


def user_1_update(config, item_id):
    # the edit is queued and the user closes the screen
    # the server is currently offline so the edits stay enqueued
    # the user reopens the screen so the data has to be loaded:

    log.debug("recovering item...")

    node_id = config.node_id

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    old_item = None
    try:
        old_item = item_ref.get()
        log.debug('Document data: {}'.format(old_item.to_dict()))
    except google.cloud.exceptions.NotFound:
        log.debug('No such document!')
        raise Exception
    if not old_item:
        raise Exception
        log.info("recovered data ok")

    old_text = None
    client_rev = None
    try:
        old_text = old_item.get('text')
        client_rev = old_item.get('client_rev')
    except KeyError:
        log.error("ERROR recovering the item text")
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
    # log.debug(text_patches)

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
            log.error("Connection error to Firestore")
            return False
        log.info("edit enqueued")
        return True

    result = update_in_transaction(transaction, node_id, item_id, client_rev, new_text, text_patches)
    if result:
        log.debug('transaction 2 ended OK')
    else:
        log.error('ERROR updating item')
        raise Exception


def user_2_update(config, item_id):
    # once again the edit is queued and the user closes the screen
    # the server is currently offline so the edits stay enqueued
    # the user reopens the screen so the data has to be loaded

    log.debug("recovering item again...")

    node_id = config.node_id

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    old_item = None
    try:
        old_item = item_ref.get()
        log.debug('Document data: {}'.format(old_item.to_dict()))
    except google.cloud.exceptions.NotFound:
        log.error('No such document!')
        raise Exception
    if not old_item:
        raise Exception
    log.info("recovered data ok")

    old_text = None
    client_rev = None
    try:
        old_text = old_item.get('text')
        client_rev = old_item.get('client_rev')
    except KeyError:
        log.error("ERROR recovering the item text")
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
    # log.debug(text_patches)

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
            log.error("Connection error to Firestore")
            return False
        log.info("edit enqueued")
        return True

    result = update_in_transaction(transaction, node_id, item_id, client_rev, new_text, text_patches)
    if result:
        log.debug('transaction 3 ended OK')
    else:
        log.error('ERROR updating item')
        raise Exception

if __name__ == "__main__":

    config = AbrimConfig()

    log.debug("NODE ID: {}".format(config.node_id,))

    # item_id = uuid.uuid4().hex
    item_id = "item_1"

    try:
        user_0_create(config, item_id)
        user_1_update(config, item_id)
        user_2_update(config, item_id)

    except google.auth.exceptions.DefaultCredentialsError:
        log.warning(""" AUTH FAILED
Check https://cloud.google.com/docs/authentication/getting-started

In GCP Console, navigate to the Create service account key page.
From the Service account dropdown, select New service account.
Input a name into the form field.
From the Role dropdown, select Project > Owner.

Note: The Role field authorizes your service account to access resources. 
You can view and change this field later using Google Cloud Platform Console.
If you are developing a production application, specify more granular
permissions than Project > Owner. For more information, see granting roles to
service accounts.
Click the Create button. A JSON file that contains your key downloads to your
computer.

Unix: export GOOGLE_APPLICATION_CREDENTIALS="/home/user/Downloads/service-account-file.json"
PowerShell: $env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\username\\Downloads\\service-account-file.json"
Windows cmd: set GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\username\\Downloads\\service-account-file.json"
""")
        raise
    sys.exit(0)
