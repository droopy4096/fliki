#!/bin/env python

import os
import sys

import docutils.core
import re
import glob

from flask import Flask

wiki_base='content'
wiki_tag_re=re.compile(r'(?P<pre>[^\[])\[(?P<wikiword>.*)\|?(?P<humanword>.*?)\](?P<post>[^\]])')

app = Flask(__name__)

def dir_listing(nodes,aliases=None):
    if aliases:
        names=aliases
    else:
        names=nodes
    links=['<a href="/%s">%s</a>' % ( n,a ) for n,a in zip(nodes,names) ]
    return "<ul><li>"+"</li><li>".join(links)+"</li></ul>"

def listdir(path,prepend=None):
    res=[]
    for s in os.listdir(path):
        if prepend:
            item=os.path.join(prepend,s)
        else:
            item=s
        res.append(item)
    return res

def render_file(path):
    fn,fe=os.path.splitext(path)
    if fe in ['.rst','.rest']:
        return render_rst(path)
    elif fe in ['.txt',]:
        return render_plain(path)
    elif fe in ['.htm','.html']:
        return render_html(path)

def render_plain(path):
    res=""
    with open(path,'r') as f:
        res=f.read()
    return res

def render_html(path):
    res=""
    with open(path,'r') as f:
        res=f.read()
    return res

def render_rst(rst_file):
    node_file = open(rst_file, 'r')
    node_content = node_file.read(-1)
    node_file.close()
    # http://docutils.sourceforge.net/docs/howto/security.html
    heightened_security_settings = {'file_insertion_enabled': 0,
                                    'raw_enabled': 0}
    # http://docutils.sourceforge.net/docs/api/publisher.html
    parts = docutils.core.publish_parts(source=node_content, writer_name='html',
                                        settings_overrides=heightened_security_settings)
    wiki_content=wikify(parts['html_body'])
    # r = Response(content=common_header(parts['title']) +os.environ.get('REDIRECT_URL')+ wiki_content + common_footer())
    return wiki_content

def wikify(content):
    return wiki_tag_re.sub(r'\g<pre><a href="\g<wikiword>">\g<humanword></a>\g<post>',content)

@app.route('/')
def hello_world():
    return dir_listing(listdir(wiki_base))

@app.route('/<path:node_name>')
def serve_node(node_name):
    full_path=os.path.join(wiki_base,node_name)
    app.logger.debug(full_path)
    res="Not Found"
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            nodes=listdir(full_path,prepend=node_name)
            names=[os.path.basename(n) for n in nodes]
            res=dir_listing(nodes,names)
        else:
            res=render_file(full_path)
    else:
        pre_matches=glob.glob(full_path+'.*')
        matches=[m[len(wiki_base)+1:] for m in pre_matches]
        if len(matches)>1:
            names=[os.path.basename(m) for m in matches]
            res=dir_listing(matches,names)
        elif matches:
            res=render_file(matches[0])

    return res

if __name__ == '__main__':
    app.run(debug=True,host='127.0.0.1',port=8000)
