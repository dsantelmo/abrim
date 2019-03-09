Travis-CI [![Build Status](https://travis-ci.org/dsantelmo/abrim.svg?branch=master)](https://travis-ci.org/dsantelmo/abrim)

    cd .git/hooks/
    ln -s ../../git_hooks/pre-commit.sh pre-commit

### Firefox info

Firefox won't let you connect to some local port (as 6000) so you have to modify its configuration:
http://about:config
Right click -> New -> String
`network.security.ports.banned.override`
`6000`


## REST API Usage examples

### Run one node
    export PYTHONPATH=./:$PYTHONPATH
    set PYTHONPATH=%PYTHONPATH%;%cd%
    py -3 abrim/input.py -i node_1 -p 5000

### List items
    curl -X GET http://localhost:5001/items -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "content-type: application/json"

### Put new item
    curl -X PUT http://localhost:5001/items/item_1 -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "content-type: application/json" -d "{\"text\":\"item 1 ok\"}"

### Put another new item
    curl -X PUT http://localhost:5001/items/item_2 -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "content-type: application/json" -d "{\"text\":\"this is item 2\"}"

### get item
    curl -X GET http://localhost:5001//items/item_1 -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "content-type: application/json"

### Post first sync (will fail with queue_in/post_sync/404/not_shadow )
    curl -X POST http://localhost:5001/users/user_1/nodes/node_1/items/item_1/sync -H "content-type: application/json" -H "Authorization: Basic YWRtaW46c2VjcmV0" -d "{ \"rowid\": 1, \"item\": \"item_1\", \"other_node\": \"node_2\", \"n_rev\": 0, \"m_rev\": 0, \"shadow_adler32\": \"1\", \"old_shadow_adler32\": \"1\", \"edits\": \"\" }"

### Put shadow
    curl -X PUT http://localhost:5001/users/user_1/nodes/node_1/items/item_1/shadow -H "content-type: application/json" -H "Authorization: Basic YWRtaW46c2VjcmV0" -d "{\"n_rev\": 0, \"m_rev\": 0, \"shadow\": \"\" }"

### Post again first sync
    curl -X POST http://localhost:5001/users/user_1/nodes/node_1/items/item_1/sync -H "content-type: application/json" -H "Authorization: Basic YWRtaW46c2VjcmV0" -d "{ \"rowid\": 1, \"item\": \"item_1\", \"other_node\": \"node_2\", \"n_rev\": 0, \"m_rev\": 0, \"shadow_adler32\": \"1\", \"old_shadow_adler32\": \"1\", \"edits\": \"\" }"

### Post second sync (first edit)
    curl -X POST http://localhost:5001/users/user_1/nodes/node_1/items/item_1/sync -H "content-type: application/json" -H "Authorization: Basic YWRtaW46c2VjcmV0" -d "{ \"rowid\": 2, \"item\": \"item_1\", \"other_node\": \"node_2\", \"n_rev\": 1, \"m_rev\": 0, \"shadow_adler32\": \"317981617\", \"old_shadow_adler32\": \"1\", \"edits\": \"@@ -0,0 +1,10 @@\n+a new text\n\"}"

### Post third sync (second edit)
    curl -X POST http://localhost:5001/users/user_1/nodes/node_1/items/item_1/sync -H "content-type: application/json" -H "Authorization: Basic YWRtaW46c2VjcmV0" -d "{ \"rowid\": 3, \"item\": \"item_1\", \"other_node\": \"node_2\", \"n_rev\": 2, \"m_rev\": 0, \"shadow_adler32\": \"469435528\", \"old_shadow_adler32\": \"317981617\", \"edits\": \"@@ -1,10 +1,12 @@\n a new\n+er\n  text\n\"}"


# The process' internals

This program is composed of 5 components:
 * node.py starts and controls the other components

 * ui.py starts the (optional) user interface

 * input.py processes messages from the UI and other nodes

 * out.py processes a queue to send messages to the other nodes' input.py

 * patch.py processes a queue and internally applies the patches recovered from input.py

Example using 2 nodes: 5000 and 6000

1. Start and prepare the nodes

	1. Delete the .sqlite files to start from scratch.

	2. Start both nodes:

		1. Start node_2 at port 6000:

				python node.py node.py -i node_2 -p 6000

		2. Start node_1 at port 5000:

				python node.py node.py -i node_1 -p 5000

	3. Create a new node connection in node_1:

		1. Using cURL:

			1. Send:

					curl -X POST http://localhost:5001/nodes -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{ \"new_node_base_url\":\"http://localhost:6001\" }"

			2. Reply form server:

					{"api_unique_code":"queue_in/post_node/201/done","message":"<NODE_2_INTERNAL_ID>"}

		2. Using UI:

			1. Connect to http://localhost:5000/

			2. Login and create and go to nodes: http://localhost:5000/nodes

			3. Add a new node: http://localhost:6001

2. First edit
	1. Create a new item

		1. Using cURL:

			1. Send:

					curl -X PUT http://localhost:5001/items/item_id_01 -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"text\": \"all ok\"}"

			2. Reply from server:

					{"api_unique_code":"queue_in/put_text/200/ok","message":"PUT OK"}

		2. Using UI:

			1. Go to new: http://localhost:5000/new

			2. Create a new item

				* ID: item_id_01

				* TEXT: all ok

			3. Press Send

	2. With this message the input.py process does this:

		1. Saves the new item

		2. For each known node (for now only node_2):

			1. Checks if its shadow exists (it doesn't)

			2. Saves a new shadow for that node with n_rev 0 m_rev 0

			3. Creates a diff for the new shadow against ''

			4. Hashes (adler32) both '' and the new shadow

			5. Saves all that to the edits table:
				* item_id: item_id_01

				* other_node: -id-

				* n_rev: 0

				* m_rev: 0

				* edits: -edits-

				* hash: 1

				* old_shadow: -shadow-

		3. input.py finishes processing and returns 200

	3. out.py keeps checking each known node (other_node) for data in the edits table

		1. Gets the edit data and PUTs it against the node it was checking

		2. Something like this, using cURL (change other_node value):

				curl -X POST http://localhost:6001/users/user_1/nodes/node_1/items/item_id_01/sync -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"rowid\": 1, \"item\": \"item_id_01\", \"other_node\": \"<NODE_2_INTERNAL_ID>\", \"n_rev\": 0, \"m_rev\": 0, \"edits\": \"@@ -0,0 +1,6 @@\n+all ok\n\", \"hash\": \"1\"}"

		3. The other node can reply:

				{"api_unique_code":"queue_in/post_sync/404/not_shadow","message":"Shadow not found. PUT the full shadow to URL + /shadow"}

		4. That happens if other node's input.py doesn't have our shadow for that item, so this node's out.py rollbacks the current transaction and sends the shadow:

				curl -X PUT http://localhost:6001/users/user_1/nodes/node_1/items/item_id_01/shadow -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"n_rev\": 0, \"m_rev\": 0, \"shadow\": \"\"}"

		5. The other's node input.py should accept it with:

				{"api_unique_code":"queue_in/put_shadow/201/ack","message":"Sync acknowledged"}

		6. This node's out.py stops processing this entry of the queue and continue with the rest of the remote nodes.

	4. If the other node didn't have a shadow and ç1 rolled back, node_1's out.py eventually out.py finds this edit again:

		1. It tries to process it:

				curl -X POST http://localhost:6001/users/user_1/nodes/node_1/items/item_id_01/sync -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"rowid\": 1, \"item\": \"item_id_01\", \"other_node\": \"<NODE_2_INTERNAL_ID>\", \"n_rev\": 0, \"m_rev\": 0, \"edits\": \"@@ -0,0 +1,6 @@\n+all ok\n\", \"hash\": \"1\"}"

		2. The other node's input.py processes the POST again. This time it finds the shadow so enqueues the edit.

		3. Then it waits 5 seconds for the patch.py process to catch up with its queue. During that time checks every second if the edit has been processed.

	5. Hopefully patch.py finds the new entry of the queue before timeout.

		1. It tries to fuzzy patch the text with the patches.

			* If it fails it just archives the patch.

			* If the patching works it starts a transaction and checks if the local text is still the same:

				* If it is the same it applies the patch to the text and archives it.

				* If it isn't just rollbacks and does nothing.

		2. At this point the other node's input.py has 2 possible returns:

			* If patch.py doesn't apply the patch within the alloted time, it returns:

					{"queue_in/post_sync/201/ack", "Sync acknowledged. Still waiting for patch to apply}

			* If patching works before timeout, it replies:

					{"api_unique_code":"queue_in/post_sync/201/done","content":{"json":"response_all_ok_and_new_edits_for_client"},"message":"Sync done"}

	6. Now both nodes have the same text

3. Second edit

	1. Edit the text from node_1:

		1. Send the edit:

				curl -X POST http://localhost:5001/items/item_id_01 -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"text\": \"all better\"}"

		2. Reply:

				{"api_unique_code":"queue_in/post_text/200/ok","message":"PUT OK"}

	2. node_1 calculates the diff with the current node_2's shadows and enqueues the edit(s) for it.

	3. node_1's out.py finds the enqueued edit and tries to post it to node_2:

		* node_1 sends the edit:

				curl -X POST http://localhost:6001/users/user_1/nodes/node_1/items/item_id_01/sync -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"rowid\": 1, \"item\": \"item_id_01\", \"other_node\": \"0f12daaf267a4fc3a93446ee6655eb6b\", \"n_rev\": 1, \"m_rev\": 0, \"edits\": \"@@ -1,6 +1,10 @@\n all \n-ok\n+better\n\", \"hash\": \"130089524\"}"

		* node_02 should reply with ack

	4. Both nodes have the same text again

4. Third edit, now from the second node

	1. Create a node connection in node_2:

			curl -X POST http://localhost:6001/nodes -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{ \"new_node_base_url\":\"http://localhost:5001\" }"

	2. Edit the text in node_2:

			curl -X POST http://localhost:6001/items/item_id_01 -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "Content-Type: application/json" -d "{\"text\": \"all much better!\"}"


### Force problems to get recovery actions:
1. Force lost return packet: TBD