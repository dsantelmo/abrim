import diff_match_patch
import hashlib
from contextlib import closing

import shelve
# FIXME Warning Because the shelve module is backed by pickle, it is insecure 
# to load a shelf from an untrusted source. Like with pickle, loading a shelf
# can execute arbitrary code.
import random
import string
import tempfile
import os


#tempname = os.path.join( tempfile.gettempdir(), tempfile.gettempprefix()) + \
# ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits)\
# for _ in range(5))
#
#with  closing(shelve.open(tempname)) as d:
#    if not 'client_text' in d:
#        d['client_text'] = """Good dog. OK"""

client_text   = 
client_shadow = """Bad dog. KO"""

server_text   = """Bad dog. KO"""

server_shadows = {}


diff_obj = diff_match_patch.diff_match_patch()
diff_obj.Diff_Timeout = DIFF_TIMEOUT




# client ID for the server shadows
client_id = 'client1'

print("client_text {}".format(client_text))
print("client_shadow {}".format(client_shadow))
print("server_text {}".format(server_text))
print("server_shadows[client1] {}".format(server_shadows['client1']))
print("server_shadows[client2] {}".format(server_shadows['client2']))

server_shadow


# from https://neil.fraser.name/writing/sync/
# step 1 & 2
# Client Text is diffed against Shadow. This returns a list of edits which
# have been performed on Client Text


edits = diff_obj.diff_main(client_shadow, client_text)
diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?

patches = diff_obj.patch_make(edits)
text_patches = diff_obj.patch_toText(patches)

if text_patches: # "send" if there are results
    print("step 2 results: {}".format(text_patches))
    #
    #step 3
    #
    # Client Text is copied over to Shadow. This copy must be identical to
    # the value of Client Text in step 1, so in a multi-threaded environment
    # a snapshot of the text should have been taken.
    #
    client_shadow_cksum =  hashlib.md5(client_shadow).hexdigest()
    # FIXME what happens on first sync?
    print("client_shadow_cksum {}".format(client_shadow_cksum))
    #
    client_shadow = client_text
    #
    # send text_patches, client_id and client_shadow_cksum
    #
    # steps 4 (atomic with 5, 6 & 7)
    #
    # The edits are applied to Server Text on a best-effort basis
    # Server Text is updated with the result of the patch. Steps 4 and 5
    # must be atomic, but they do not have to be blocking; they may be
    # repeated until Server Text stays still long enough.
    #
    # Client Text and Server Shadow (or symmetrically Server Text and
    # Client Shadow) must be absolutely identical after every half of the
    # synchronization
    #
    # receive text_patches and client_shadow_cksum
    #
    # first check the server shadow cheksum
    # if server_shadows[client_id] is empty ask for it
    if not client_id in server_shadows:
        print("too bad! I can't find your shadow. Please send it.")
        #clients send its shadow:
        print("Shadow received. Now you can sync!")
        server_shadows[client_id] = client_shadow
    else:
        server_shadow_cksum = hashlib.md5(
          server_shadows[client_id]).hexdigest()
        print("server_shadow_cksum {}".format(server_shadow_cksum))
        if client_shadow_cksum != server_shadow_cksum:
            #FIXME what happenson first sync?
            print("too bad! Shadows got desynced. "
                  "I'm sending back ALLserver shadow text, "
                  "use it a your client shadow")
            print(server_shadows[client_id])
            #clients updates its shadow AND text:
            print("DATALOSS on latest client text. "
              "Updating with server text")
            client_shadow = server_shadows[client_id]
            client_text = client_shadow
        else:
            print("shadows' checksums match")
            patches2 = diff_obj.patch_fromText(text_patches)
            #
            server_shadow_patch_results = diff_obj.patch_apply(
              patches2, server_shadows[client_id])
            results = server_shadow_patch_results[1]
            #
            # len(set(list)) should be 1 if all elements are the same
            if len(set(results)) == 1 and results[0]: 
                # step 5
                server_shadows[client_id] = server_shadow_patch_results[0]
                # should a break here be catastrophic ??
                #
                # step 6
                # FIXME: shouldn't this be a new set of patches generated
                # diff'ing THIS new server_shadow and server_text?
                # Another client could have changed the server text
                server_text_patch_results = diff_obj.patch_apply(
                  patches2, server_text)
                #
                #step 7
                server_text = server_text_patch_results[0]
                print("all OK")
            else:
                # I should try to patch again
                print("too bad!")
else:
    print("nothing to update")

print("client_text {}".format(client_text))
print("client_shadow {}".format(client_shadow))
print("server_text {}".format(server_text))
print("server_shadows[client1] {}".format(server_shadows['client1']))
print("server_shadows[client2] {}".format(server_shadows['client2']))

# another client updates the server
server_text = """Good Kitty. OK"""
server_shadows['client2'] = """Good Kitty. OK"""

print("server_text {}".format(server_text))
print("server_shadows[client1] {}".format(server_shadows['client1']))
print("server_shadows[client2] {}".format(server_shadows['client2']))


# the first client asks the server for update
# so it sends its shadow checksum
client_shadow_cksum =  hashlib.md5(client_shadow).hexdigest()

# server receives the client_id and checksum and compares to the one it has,
# and then checks if the server_text is the same

# first check the server shadow cheksum
# if server_shadows[client_id] is empty ask for it
if not client_id in server_shadows:
    print("too bad! I can't find your shadow. Please send it.")
    #clients send its shadow:
    print("Shadow received. Now you can sync!")
    server_shadows[client_id] = client_shadow
else:
    server_shadow_cksum = hashlib.md5(server_shadows[client_id]).hexdigest()
    if client_shadow_cksum != server_shadow_cksum:
        print("too bad! Shadows got desynced. I'm sending back ALL server "
              "shadow text, use it a your client shadow")
        print(server_shadows[client_id])
        #clients updates its shadow AND text:
        print("DATALOSS on latest client text. Updating with server text")
        client_shadow = server_shadows[client_id]
        client_text = client_shadow
    else:
        server_text_cksum =  hashlib.md5(server_text).hexdigest()
        if server_text_cksum == client_shadow_cksum:
            print("all ok! nothing to update")
        else:
            # step 1 & 2
            print("Server text changed. " 
            "This is the patches for the new text")
            server_edits = diff_obj.diff_main(
              server_shadows[client_id], server_text)
            diff_obj.diff_cleanupSemantic(server_edits) # FIXME: optional?
            #
            server_patches = diff_obj.patch_make(server_edits)
            server_text_patches = diff_obj.patch_toText(server_patches)
            #
            print("step 2 results: {}".format(server_text_patches))
            #
            # step 3
            #
            # Text is copied over to Shadow. This copy must be identical to
            # the value of Text in step 1, so in a multi-threaded environment
            # a snapshot of the text should have been taken.
            #
            server_shadows[client_id] = server_text
            #
            # client receives the patches
            if server_text_patches:
                # steps 4 (atomic with 5, 6 & 7)
                #
                # send server_text_patches, client_id and server_shadow_cksum
                #
                # steps 4 (atomic with 5, 6 & 7)
                #
                # The edits are applied to Server Text on a best-effort
                # basis
                #
                # Server Text is updated with the result of the patch.
                # Steps 4 and 5 must be atomic, but they do not have to be 
                # blocking; they may be repeated until Server Text stays 
                # still long enough.
                #
                # Client Text and Server Shadow (or symmetrically Server
                # Text and Client Shadow) must be absolutely identical 
                # after every half of the synchronization
                #
                # receive text patches and shadow checksum
                client_shadow_cksum =  hashlib.md5(
                  client_shadow).hexdigest()
                print("client_shadow_cksum {}".format(client_shadow_cksum))
                if client_shadow_cksum != server_shadow_cksum:
                    print("too bad! Shadows got de-synced. "
                          "I'm sending back ALL client shadow text, "
                          "use it a your server shadow")
                    print(client_shadow)
                    #server updates its shadow:
                    print("DATALOSS on latest client shadow. "
                          "Updating with client shadow")
                    server_shadows[client_id] = client_shadow
                else:
                    print("shadows' checksums match")
                    server_patches2 = diff_obj.patch_fromText(
                      server_text_patches)
                    #
                    client_shadow_patch_results =  diff_obj.patch_apply(
                      server_patches2, client_shadow)
                    server_results = client_shadow_patch_results[1]
                    #
                    # len(set(list)) should be 1 if all elements are the
                    # same
                    if len(set(server_results)) == 1 and server_results[0]:
                        #all elements in the list are True
                        #step 5
                        client_shadow = client_shadow_patch_results[0]
                        # should a break here be catastrophic ??
                        #
                        #step 6
                        client_text_patch_results = diff_obj.patch_apply(
                          server_patches2, client_text)
                        #
                        #step 7
                        client_text = client_text_patch_results[0]
                        print("all OK")
                    else:
                        # I should try to patch again
                        print("too bad!")


print("client_text {}".format(client_text))
print("client_shadow {}".format(client_shadow))
print("server_text {}".format(server_text))
print("server_shadows[client1] {}".format(server_shadows['client1']))
print("server_shadows[client2] {}".format(server_shadows['client2']))
