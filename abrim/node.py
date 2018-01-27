import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google

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
    try:
        user_0_create()
        user_1_update()
        user_2_update()

    except google.auth.exceptions.DefaultCredentialsError:
        print(""" AUTH FAILED
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
