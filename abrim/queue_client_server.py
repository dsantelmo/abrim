import multiprocessing
import time
from random import randint
import sys
from google.cloud import firestore
import grpc
import google

def test_proc(lock):
    for i in range(randint(1, 11)):
        lock.acquire()
        print(".", end='')
        sys.stdout.flush()
        lock.release()
        time.sleep(1) # do work instead


def user_3_process_queue(lock):
    #
    # end UI client part, start the queue part
    #

    # read the queues

    node_id = "node_1"
    item_id = "item_1"

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    @firestore.transactional
    def send_queue1(transaction, item_ref):
        try:
            queue = item_ref.collection('queue_1_to_process').order_by('client_rev').limit(1).get()

            for queue_snapshot in queue:
                queue_1_ref = item_ref.collection('queue_1_to_process').document(str(queue_snapshot.id))
                lock.acquire()
                print("processing item {} queue_1_to_process item {}".format(item_id, queue_1_ref.id, ))
                lock.release()

                # NOW SENT THE QUEUE ITEM TO THE SERVER

                queue_2_ref = item_ref.collection('queue_2_sent').document(str(queue_1_ref.id))
                transaction.set(queue_2_ref, {
                    'create_date': firestore.SERVER_TIMESTAMP,
                    'client_rev': queue_1_ref.id,
                    'action': 'processed_item',
                })

                transaction.delete(queue_1_ref)
                break
            else:
                lock.acquire()
                print("queue query got no results")
                lock.release()
                return False
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            lock.acquire()
            print("Connection error to Firestore")
            lock.release()
            raise Exception
        lock.acquire()
        print("queue 1 sent!")
        lock.release()
        return True

    result = send_queue1(transaction, item_ref)

    lock.acquire()
    if result:
        print("one entry from queue 1 was correctly processed")
    else:
        print("no entries in queue 1. Nothing done!")
    lock.release()


if __name__ == '__main__':
    while True:
        lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=user_3_process_queue, args=(lock,))
        p_name = p.name
        print(p_name + " starting up")
        p.start()
        # Wait for x seconds or until process finishes
        p.join(20)
        if p.is_alive():
            print(p_name + " timeouts")
            p.terminate()
            p.join()
        else:
            print(p_name + " finished ok")
        # even if the process finishes right now wait a bit
        time.sleep(1)