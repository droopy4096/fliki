#!/bin/env python

import os
import sys

import docutils.core
import re
import glob

from flask import Flask, Response, send_file, render_template_string, render_template
from jinja2 import TemplateNotFound

wiki_base='content'
wiki_compiled='compiled'

# wiki_tag_re=re.compile(r'(?P<pre>[^\[])\[(?P<wikiword>.*)\|?(?P<humanword>.*?)\](?P<post>[^\]])')
wiki_tag_re=re.compile(r'(?<!\[)\[(?P<wikiword>[\w/]+)\|?(?P<humanword>.*?)\](?<=\])')

class WikiNotImplemented(Exception):
    pass

class Wiki(object):
    def __init__(self,wiki_base_path,wiki_compiled_path):
        self.base_path=wiki_base_path
        self.compiled_path=wiki_compiled_path

wiki=Wiki(wiki_base,wiki_compiled)
app = Flask(__name__)

# render_template
# render_template_string
# return render_template('hello.html', name=name)


# http://flask.pocoo.org/docs/patterns/streaming/#streaming-from-templates
def stream_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv

def stream_string_template(template_string, **context):
    app.update_template_context(context)
    t = app.jinja_env.from_string(template_string)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv

class WikiFile(object):
    def __init__(self,wiki_path,wiki):
        self.wiki=wiki
        self.path=wiki_path
    
    def getContentPath(self):
        return os.path.join(self.wiki.base_path,self.path)
    
    def getCompiledPath(self):
        return os.path.join(self.wiki.compiled_path,self.path)
    
    def compile(self):
        raise WikiNotImplemented
    
    def compiled_iterator(self):
        with open(self.getCompiledPath(),'r') as f:
            for l in f:
                yield l
    
    def render(self):
        fs_compiled_path=self.getCompiledPath()
        fs_content_path=self.getContentPath()
        if not os.path.exists(fs_compiled_path):
            app.logger.debug('force-compiling (does not exist): '+self.path)
            self.compile()
        elif os.path.getmtime(fs_compiled_path)<os.path.getmtime(fs_content_path):
            app.logger.debug('force-compiling (too old): '+self.path)
            self.compile()
        return self.compiled_iterator()
    
    
    def unwiki(self,content):
        unwiki=wiki_tag_re.sub(r'<a href="\g<wikiword>">\g<humanword></a>',content)
        return unwiki

class PlainFile(WikiFile):
    def __init__(self,wiki_path,wiki):
        super(PlainFile,self).__init__(wiki_path,wiki)
    
    def compile(self):
        fs_compiled_path=self.getCompiledPath()
        fs_content_path=self.getContentPath()
        fs_compiled_dir=os.path.dirname(fs_compiled_path)
        if not ( os.path.exists(fs_compiled_dir) and os.path.isdir(fs_compiled_dir) ):
            os.makedirs(fs_compiled_dir)
        with open(fs_content_path,'r') as f:
            with open(fs_compiled_path,'w') as compiled:
                compiled.write('<pre>')
                for l in f:
                    compiled.writelines((self.unwiki(l),))
                compiled.write('</pre>')
    
class HtmlFile(PlainFile):
    def __init__(self,wiki_path,wiki):
        super(HtmlFile,self).__init__(wiki_path,wiki)
    
    def compile(self):
        fs_compiled_path=self.getCompiledPath()
        fs_content_path=self.getContentPath()
        fs_compiled_dir=os.path.dirname(fs_compiled_path)
        if not ( os.path.exists(fs_compiled_dir) and os.path.isdir(fs_compiled_dir) ):
            os.makedirs(fs_compiled_dir)
        with open(fs_content_path,'r') as f:
            with open(fs_compiled_path,'w') as compiled:
                for l in f:
                    compiled.writelines((self.unwiki(l),))
    
class RstFile(PlainFile):
    def __init__(self,wiki_path,wiki):
        super(RstFile,self).__init__(wiki_path,wiki)
    
    def compile(self):
        fs_compiled_path=self.getCompiledPath()
        fs_content_path=self.getContentPath()
        fs_compiled_dir=os.path.dirname(fs_compiled_path)
        if not ( os.path.exists(fs_compiled_dir) and os.path.isdir(fs_compiled_dir) ):
            os.makedirs(fs_compiled_dir)
        
        node_file = open(fs_content_path, 'r')
        node_content = node_file.read(-1)
        node_file.close()
        # http://docutils.sourceforge.net/docs/howto/security.html
        heightened_security_settings = {'file_insertion_enabled': 0,
                                        'raw_enabled': 0}
        # http://docutils.sourceforge.net/docs/api/publisher.html
        parts = docutils.core.publish_parts(source=node_content, writer_name='html',
                                            settings_overrides=heightened_security_settings)
        with open(fs_compiled_path,'w') as compiled:
            compiled.write(self.unwiki(parts['html_body']))

dir_list_template="""
<ul>
{% for node,alias in node_list %}
<li><a href="/{{ node }}">{{ alias }}</a></li>
{% endfor %}
</ul>
"""

page_template="""{{ contents }}"""

def dir_listing(nodes,aliases=None):
    if aliases:
        names=aliases
    else:
        names=nodes
    node_list=zip(nodes,names)
    try:
        node_list=zip(nodes,names)
        return render_template('dirlist.html',node_list=node_list)
    except TemplateNotFound:
        return render_template_string(dir_list_template,node_list=node_list)

def listdir(fs_path,prepend=None):
    res=[]
    for s in os.listdir(fs_path):
        if prepend:
            item=os.path.join(prepend,s)
        else:
            item=s
        res.append(item)
    return res

def render_file(wiki_path):
    fs_path=os.path.join(wiki.base_path,wiki_path)
    fn,fe=os.path.splitext(fs_path)
    page=None
    content=None
    if fe in ['.rst','.rest']:
        page=RstFile(wiki_path,wiki)
    elif fe in ['.txt',]:
        page=PlainFile(wiki_path,wiki)
    elif fe in ['.htm','.html']:
        page=HtmlFile(wiki_path,wiki)
    elif os.path.exists(fs_path):
        content=send_file(fs_path)
    if page:
        return Response(page.render(),mimetype='text/html')
    elif content:
        return content

@app.route('/')
def root_page():
    return dir_listing(listdir(wiki_base))

@app.route('/<path:node_name>')
def serve_node(node_name):
    fs_full_path=os.path.join(wiki_base,node_name)
    # app.logger.debug(fs_full_path)
    res="Not Found"
    if os.path.exists(fs_full_path):
        if os.path.isdir(fs_full_path):
            nodes=listdir(fs_full_path,prepend=node_name)
            names=[os.path.basename(n) for n in nodes]
            res=dir_listing(nodes,names)
        else:
            # res=render_file(fs_full_path)
            res=render_file(node_name)
    else:
        pre_matches=glob.glob(fs_full_path+'.*')
        matches=[m[len(wiki_base)+1:] for m in pre_matches]
        if len(matches)>1:
            names=[os.path.basename(m) for m in matches]
            res=dir_listing(matches,names)
        elif matches:
            # we need full file path here, not relative to Wiki
            res=render_file(matches[0])

    return res

if __name__ == '__main__':
    app.run(debug=True,host='127.0.0.1',port=8000)
