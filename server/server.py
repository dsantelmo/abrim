#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, url_for
import diff_match_patch
import json
import pdb
import os

os.sys.path.insert(0, os.path.join(os.getcwd(), "../lib/")) 
from sync_shadow import read_shadow, write_shadow
import sync_text

se_text="server_text.txt"
se_shadow="server_shadow.txt"

app = Flask(__name__)




@app.route('/', methods=['POST',])
def __root():
    return redirect(url_for('__patch'), code=307) #307 for POST redir

@app.route('/patch/', methods=['POST',])
def __patch():
    verbosity=4
    #se_shadow_text=''
    server_text=''
    resul2=None
    doc = request.form['doc']
    #doc = 'server://' + doc
    patch_text = request.form['patch']
    payload = {'doc': doc, 'patch': "no patch",}
    #print("patch_text: %s" % (patch_text,))
    print("PATCH: %s" % patch_text)
    if not patch_text:
        payload['patch']="patch failed"
        print("PAYLOAD ERROR: %s" % payload)
        return json.dumps(payload, sort_keys=True, 
          indent=4, separators=(',', ': '))
    shadow=read_shadow(doc, None, True, verbosity=0)
    print("shadow:--->%s" % shadow)
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    patch=differ.patch_fromText(patch_text)
    resul=differ.patch_apply(patch, shadow)
    if resul[1]:
        for blah in resul:
            print ("resul %s" % blah)

        #f2.write(resul[0])
        write_shadow(doc, resul[0], True, verbosity)
        with open(se_text,'r+') as f3:
            server_text=f3.read()
            with open(se_text,'w') as f4:
                #print(srv_text)
                #6b
                resul2=differ.patch_apply(patch, server_text)# => [text2, results]
                if resul2[1]:
                    #7
                    print(resul2)
                    f4.write(resul2[0])
    else:
        payload['patch']="patch failed"
#    with open(se_shadow,'r+') as f:
#        se_shadow_text=f.read()
#        with open(se_shadow,'w') as f2:
#            #print(srv_text)
#            differ=diff_match_patch.diff_match_patch()
#            differ.Diff_Timeout=3
#            #4a
#            patch=differ.patch_fromText(patch_text)
#            #print(differ.patch_toText(patch))
#            resul=differ.patch_apply(patch, se_shadow_text)# => [text2, results]
#            if resul[1]:
#                #5
#                print(resul)
#                f2.write(resul[0])
#                #6a
#                with open(se_text,'r+') as f3:
#                    server_text=f3.read()
#                    with open(se_text,'w') as f4:
#                        #print(srv_text)
#                        #6b
#                        resul2=differ.patch_apply(patch, server_text)# => [text2, results]
#                        if resul2[1]:
#                            #7
#                            print(resul2)
#                            f4.write(resul2[0])
#            else:
#                payload['patch']="patch failed"
#    if se_shadow_text and server_text and resul2:
    if shadow and server_text and resul2:
        with open(se_shadow,'w') as f5:
            #1b
            #2
            diff=differ.diff_main(shadow, resul2[0])
            patch2=differ.patch_toText(differ.patch_make(shadow,diff))
            #print(patch2)
            #3
            f5.write(resul2[0])
            f5.flush()
            #4a
            payload['patch']=patch2
    print("PAYLOAD: %s" % payload)
    return json.dumps(payload, sort_keys=True, indent=4, separators=(',', ': '))


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
    #app.run(host='127.0.0.1')
