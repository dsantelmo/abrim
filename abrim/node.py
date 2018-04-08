#!/usr/bin/env python

import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google
import logging
import os
import zlib
import hashlib
from pathlib import Path


def get_log(full_debug=False):
    if full_debug:
        # enable debug for HTTP requests
        import http.client as http_client
        http_client.HTTPConnection.debuglevel = 1
    else:
        # disable more with
        # for key in logging.Logger.manager.loggerDict:
        #    print(key)
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('google').setLevel(logging.CRITICAL)

    LOGGING_LEVELS = {'critical': logging.CRITICAL,
                      'error': logging.ERROR,
                      'warning': logging.WARNING,
                      'info': logging.INFO,
                      'debug': logging.DEBUG}
    # FIXME http://docs.python-guide.org/en/latest/writing/logging/
    # It is strongly advised that you do not add any handlers other
    # than NullHandler to your library's loggers.
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-5s %(asctime)s - %(module)-10s %(funcName)-25s %(lineno)-5d: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')  # ,
    # disable_existing_loggers=False)
    logging.StreamHandler(sys.stdout)
    return logging.getLogger(__name__)


log = get_log(full_debug=False)


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


def create_diff_edits(text, shadow):
    log.debug("about to diff \"{}\" with \"{}\"".format(shadow,text,))
    diff_obj = diff_match_patch.diff_match_patch()
    diff_obj.Diff_Timeout = 1
    diff = diff_obj.diff_main(shadow, text)
    diff_obj.diff_cleanupSemantic(diff)  # FIXME: optional?
    patch = diff_obj.patch_make(diff)
    if patch:
        return diff_obj.patch_toText(patch)
    else:
        log.debug("no patch results...")
        return None


def get_item_ref(db, config, item_id):
    node_id = config.node_id
    try:
        db_prefix = config.db_prefix
    except AttributeError:
        db_prefix = ''
    db_path = db_prefix + 'nodes'

    # create new item
    item_text = "original text"

    node_ref = db.collection(db_path).document(node_id)
    return node_ref.collection('items').document(item_id)


@firestore.transactional
def create_in_transaction(transaction, item_ref, config):
    try:
        try:
            _ = item_ref.get(transaction=transaction)
            log.error("Tried to create the item but it's already been created")
            return False  # it shouldn't be there
        except google.api.core.exceptions.NotFound:
            pass
        transaction.set(item_ref, {
            'create_date': firestore.SERVER_TIMESTAMP
        })

        for node in config.known_nodes:
            log.debug("creating shadow for node {}".format(node))
            shadow = item_ref.collection('shadows').document('0').collection('nodes').document(node)
            transaction.set(shadow, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'shadow': None,
                'shadow_server_rev': 0
            })
            rev_ref = item_ref.collection('queue_1_to_process').document('0')
            transaction.set(rev_ref, {
                'client_rev': 0
            })
            queue_ref = rev_ref.collection('nodes').document(node)
            transaction.set(queue_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'action': 'create_item',
                'shadow': None,
                'shadow_server_rev': 0
            })
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        return False
    log.debug("edit enqueued")
    return True


def create_item(config, item_id):

    db = firestore.Client()
    item_ref = get_item_ref(db, config, item_id)

    transaction = db.transaction()

    result = create_in_transaction(transaction, item_ref, config)
    if result:
        log.debug('create_item ended OK')
        return True
    else:
        log.error('ERROR saving new item')
        raise Exception


@firestore.transactional
def update_in_transaction(transaction, item_ref, new_text):
    log.debug("recovering item...")
    client_rev, old_shadow = _get_rev_shadow(item_ref, transaction)

    if old_shadow == new_text and client_rev != -1:
        log.info("new text equals old shadow, nothing done!")
        return True

    client_rev += 1
    try:
        data = {
            'last_update_date': firestore.SERVER_TIMESTAMP,
            'text': new_text,
            'shadow': new_text,
            'client_rev': client_rev,
        }
        transaction.set(item_ref, data)
        log.debug("item saved with data: {}".format(data))

        text_patches = create_diff_edits(new_text, old_shadow)
        old_shadow_adler32 = _create_hash(old_shadow)
        shadow_adler32 = _create_hash(new_text)

        queue_ref = item_ref.collection('queue_1_to_process').document(str(client_rev))
        data = {
            'create_date': firestore.SERVER_TIMESTAMP,
            'client_rev': client_rev,
            'text_patches': text_patches,
            'old_shadow_adler32': old_shadow_adler32,
            'shadow_adler32': shadow_adler32,
        }
        transaction.set(queue_ref, data)
        log.debug("queue_1_to_process saved with data: {}".format(data))
        log.debug('About to commit transaction...')
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        return False
    log.info('New update saved')
    return True


def _create_hash(text):
    adler32 = zlib.adler32(text.encode())
    log.debug("new hash {}".format(adler32))
    # shadow_sha512 = hashlib.sha512(new_text.encode()).hexdigest()
    return adler32


def _get_rev_shadow(item_ref, transaction):
    try:
        old_item = item_ref.get(transaction=transaction)
        log.debug('Document exists, data: {}'.format(old_item.to_dict()))
        try:
            client_rev = old_item.get('client_rev')
        except KeyError:
            log.info("ERROR recovering the client_rev")
            sys.exit(0)
        try:
            old_shadow = old_item.get('shadow')
        except KeyError:
            old_shadow = ""
    except google.cloud.exceptions.NotFound:
        log.error('No such document! Creating a new one')
        client_rev = -1
        old_shadow = ""
    return client_rev, old_shadow


def update_item(config, item_id, new_text):

    if not new_text:
        new_text = ""

    db = firestore.Client()
    item_ref = get_item_ref(db, config, item_id)
    transaction = db.transaction()
    result = update_in_transaction(transaction, item_ref, new_text)
    if result:
        log.debug('update transaction ended OK')
        return True
    else:
        log.error('ERROR updating item')
        raise Exception


if __name__ == "__main__":
    node_id = "node_1"
    config = AbrimConfig("node_1")
    config.known_nodes = ['node_2', 'node_3',]

    log.debug("NODE ID: {}".format(config.node_id,))

    # item_id = uuid.uuid4().hex
    item_id = "item_1"

    try:
        # FIXME unify create_item and update_item
        #create_item(config, item_id)
        update_item(config, item_id, "a new text")
        #update_item(config, item_id, "a newer text")

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
