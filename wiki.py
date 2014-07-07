#!/bin/env python

# import pdb; pdb.set_trace()
import os
import sys

import docutils.core
import re
import glob

from flask import Flask, Response, send_file, render_template_string, render_template, stream_with_context, Markup, request
from jinja2 import TemplateNotFound
### DebugToolbarExtension seems to be disfunctional? :(
## from flask_debugtoolbar import DebugToolbarExtension

wiki_base='content'
wiki_compiled='compiled'
wiki_index='index'

# wiki_tag_re=re.compile(r'(?P<pre>[^\[])\[(?P<wikiword>.*)\|?(?P<humanword>.*?)\](?P<post>[^\]])')
wiki_tag_re=re.compile(r'(?<!\[)\[(?P<wikiword>[\w/]+)\|?(?P<humanword>.*?)\](?<=\])')

dir_list_template="""
<html><body><ul>
{% for node,alias in node_list %}
<li><a href="/{{ node }}">{{ alias }}</a></li>
{% endfor %}
</ul></body></html>
"""

search_template="""
<html><body>
{% if query is defined %}
<p>Looking for '{{ query }}'</p>
{% endif %}
{% if node_list is defined %}
<ul>
{% for node,alias,hl in node_list %}
<li><a href="{{ node }}">{{ alias }}</a>
  <ul><li>{{ node }}</li><li>{{ hl }}</li></ul>
</li>
{% endfor %}
</ul>
{% endif %}
<form>
<input name="q" type="text" value="{{ query }}">
<input type="submit" >
</form>
</body></html>
"""

page_template="""<html><body>{% for l in body %}{{ l }}{% endfor %}</body></html>"""


class WikiNotImplemented(Exception):
    pass

class Wiki(object):
    def __init__(self,wiki_base_path,wiki_compiled_path,wiki_index_path):
        self.base_path=wiki_base_path
        self.compiled_path=wiki_compiled_path
        self.index_path=wiki_index_path

def ftype(fs_path):
    fn,fe=os.path.splitext(fs_path)
    if fe in ['.rst','.rest']:
        return 'rst'
    elif fe in ['.txt',]:
        return 'txt'
    elif fe in ['.htm','.html']:
        return 'html'
    elif os.path.exists(fs_path):
        return 'bin'

##### Indexer ##################
# https://pythonhosted.org/Whoosh/indexing.html
import whoosh
import whoosh.index
import whoosh.fields
import whoosh.qparser

# from whoosh import index
from whoosh.fields import Schema, ID, TEXT, STORED
from whoosh.analysis import StemmingAnalyzer

class WikiIndexer(object):
    def __init__(self, index_path):
        self.index_path=index_path
    
    def get_schema(self):
        schema = Schema(path=ID(stored=True),
                name=ID(stored=True),
                # time=DATETIME(stored=True),
                time=STORED,
                content=TEXT(analyzer=StemmingAnalyzer()))
        return schema
        # return whoosh.fields.Schema(path=whoosh.fields.ID(unique=True, stored=True), content=whoosh.fields.TEXT)

    def _add_doc(self, writer, path):
        if not (ftype(path) in ['txt','html','rst']):
            return
        fileobj = open(path, "rb")
        content = fileobj.read()
        fileobj.close()
        modtime = os.path.getmtime(path)
        fname = os.path.basename( path )
        app.logger.debug(" | ".join((path,fname)))
        writer.add_document(path=unicode(path), content=unicode(content), time=modtime, name=unicode(fname) )

    def index(self, my_docs, clean=False):
        if clean:
            self.rebuild(my_docs)
        else:
            self.update(my_docs)

    def update(self, my_docs):
        """ 
            @my_docs - iterable storing file paths 
        """
        ix = index.open_dir(self.index_path)

        # The set of all paths in the index
        indexed_paths = set()
        # The set of all paths we need to re-index
        to_index = set()

        with ix.searcher() as searcher:
          writer = ix.writer()

          # Loop over the stored fields in the index
          for fields in searcher.all_stored_fields():
            indexed_path = fields['path']
            indexed_paths.add(indexed_path)

            if not os.path.exists(indexed_path):
              # This file was deleted since it was indexed
              writer.delete_by_term('path', indexed_path)

            else:
              # Check if this file was changed since it
              # was indexed
              indexed_time = fields['time']
              mtime = os.path.getmtime(indexed_path)
              if mtime > indexed_time:
                # The file has changed, delete it and add it to the list of
                # files to reindex
                writer.delete_by_term('path', indexed_path)
                to_index.add(indexed_path)

          # Loop over the files in the filesystem
          # Assume we have a function that gathers the filenames of the
          # documents to be indexed
          for path in my_docs:
            if path in to_index or path not in indexed_paths:
              # This is either a file that's changed, or a new file
              # that wasn't indexed before. So index it!
              self._add_doc(writer, path)

          writer.commit()

    def rebuild(self, my_docs):
        """remove old index and create new one from scratch
            @my_docs - iterable storing file paths 
        """
        # Always create the index from scratch
        ix = whoosh.index.create_in(self.index_path, schema=self.get_schema())
        writer = ix.writer()
        
        # Assume we have a function that gathers the filenames of the
        # documents to be indexed
        for path in my_docs:
            self._add_doc(writer, path)

        writer.commit()

    def search(self,query,path=None,limit=25):
        ix = whoosh.index.open_dir(wiki.index_path)
        qp = whoosh.qparser.QueryParser('content',schema=ix.schema)
        q=qp.parse(query)
        params={'limit':limit, 'scored':True}
        if path:
            # we've got to limit results only to specified path
            params['filter'] = query.Term("path", path)

        with ix.searcher() as searcher:
            results=searcher.search(q, **params)
            # results.fragmeter=whoosh.highlight.SentenceFragmenter()
            results.fragmeter=whoosh.highlight.ContextFragmenter()
            hl=whoosh.highlight.Highlighter(fragmenter=results.fragmenter)
            results.highlighter=hl
            res=[]
            for r in results:
                row={}
                for k in r.keys():
                    row[k]=r[k]
                # row['highlights']=r.highlights('content')
                with open(r["path"]) as fileobj:
                    filecontents = fileobj.read()
                    
                    row['highlights']=r.highlights("content", top=2, text=unicode(filecontents))
                res.append( row )
        # app.logger.debug( str(results) )
        return res

# End of Indexer
#################

wiki=Wiki(wiki_base,wiki_compiled,wiki_index)
idx=WikiIndexer(wiki.index_path)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'EmbUd/dielMWkrPlY0Dy9szv6X0fvKgX4vCfBaDJOFAmdx6pZDx6A'

### Needed by DebugToolbarExtension
## app.config['DEBUG_TB_TEMPLATE_EDITOR_ENABLED']=True
## toolbar = DebugToolbarExtension(app)

# http://flask.pocoo.org/docs/patterns/streaming/#streaming-from-templates
def stream_template(template_name, **context):
    app.update_template_context(context)
    app.logger.debug(str(context))
    t = app.jinja_env.get_template(template_name)
    # rv = t.stream(context)
    rv = t.generate(context)
    # rv.enable_buffering(5)
    return rv

def stream_string_template(template_string, **context):
    app.update_template_context(context)
    t = app.jinja_env.from_string(template_string)
    rv = t.stream(context)
    # rv = t.render(context)
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
                # Disable autoescaping of returned code by
                # jinja 
                yield Markup(l)
    
    def render(self,template=None,**context):
        """
        @template - template file name
        """
        fs_compiled_path=self.getCompiledPath()
        fs_content_path=self.getContentPath()
        if not os.path.exists(fs_compiled_path):
            app.logger.debug('force-compiling (does not exist): '+self.path)
            self.compile()
        elif os.path.getmtime(fs_compiled_path)<os.path.getmtime(fs_content_path):
            app.logger.debug('force-compiling (too old): '+self.path)
            self.compile()
        if template:
            try:
                return stream_template(template,body=self.compiled_iterator(),**context)
            except TemplateNotFound:
                # ok, not found template, fine, fallback to default
                pass
        return stream_string_template(page_template,body=self.compiled_iterator(),**context)
        # return self.compiled_iterator()
    
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

def dir_listing(nodes,aliases=None,title=None):
    if aliases:
        names=aliases
    else:
        names=nodes
    node_list=zip(nodes,names)
    try:
        node_list=zip(nodes,names)
        return render_template('dirlist.html',node_list=node_list,page_title=title)
    except TemplateNotFound:
        return render_template_string(dir_list_template,node_list=node_list,page_title=title)

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
    ft=ftype(fs_path)
    ## fn,fe=os.path.splitext(fs_path)
    page=None
    content=None
    template_name='page.html'
    if ft == 'rst':
        page=RstFile(wiki_path,wiki)
    elif ft == 'txt':
        page=PlainFile(wiki_path,wiki)
    elif ft == 'html':
        page=HtmlFile(wiki_path,wiki)
    elif os.path.exists(fs_path):
        content=send_file(fs_path)
    if page:
        # we don't want to be rude and disable ALL autoescaping
        ## app.jinja_env.autoescape=False
        return Response(stream_with_context(page.render(template_name,page_title=wiki_path)),mimetype='text/html')
        ## app.jinja_env.autoescape=True
    elif content:
        return content

def file_match(full_path,regex):
    """http://stackoverflow.com/questions/7012921/recursive-grep-using-python"""
    ## kind of like grep... probably worthless 
    ## with real indexing
    with open(full_path,'r') as f:
        for line in f:
            if regex.search(line):
                return True
            
    return False

def do_search(path, regex_str,regex_flags=re.I):
    """http://stackoverflow.com/questions/7012921/recursive-grep-using-python"""
    regObj = re.compile(regex_str,regex_flags)
    res = []
    l=len(wiki.base_path)
    fs_search_path=os.path.join(wiki.base_path,path)
    app.logger.debug( ' | '.join((wiki.base_path, path, fs_search_path)))
    for root, dirs, fnames in os.walk(fs_search_path):
        for fname in fnames:
            app.logger.debug( fname)
            file_path=os.path.join(root,fname)
            if file_match(file_path,regObj):
                node_path=file_path[l:]
                app.logger.debug( ' | '.join((node_path, fname)))
                res.append((node_path,fname))
                # res.append((root, fname))
    return res

def all_docs():
    """Generator walking through all documents"""
    fs_search_path=wiki.base_path
    for root, dirs, fnames in os.walk(fs_search_path):
        for fname in fnames:
            file_path=os.path.join(root,fname)
            yield file_path

@app.route('/reindex')
def reindex():
    idx.rebuild(all_docs())
    return "done"

@app.route('/')
def root_page():
    return dir_listing(listdir(wiki_base),title="/")

@app.route('/search',methods=['GET',])
@app.route('/<path:base>/search',methods=['GET',])
def search_page(base=''):
    q=request.args.get('q',None)
    params={}
    if q:
        params['query']=q
        if base:
            results=idx.search(q,path=base)
        else:
            results=idx.search(q)
        node_list=[]
        wiki_path_len=len(wiki.base_path)
        for r in results:
            try:
                app.logger.debug(str(r))
                r['path']=r['path'][wiki_path_len:]
                node_list.append((r['path'],r['name'],r['highlights']))
            except:
                app.logger.debug('Failed executing "%s"' % ( str(r) ))

        params['node_list']=node_list
        # params['node_list']=do_search(base,q)
    else:
        pass
    try:
        return render_template('search.html', **params)
    except TemplateNotFound:
        return render_template_string(search_template, **params)

@app.route('/<path:node_name>')
def serve_node(node_name):
    fs_full_path=os.path.join(wiki_base,node_name)
    # app.logger.debug(fs_full_path)
    res="Not Found"
    if os.path.exists(fs_full_path):
        if os.path.isdir(fs_full_path):
            nodes=listdir(fs_full_path,prepend=node_name)
            names=[os.path.basename(n) for n in nodes]
            res=dir_listing(nodes,names,title=node_name)
        else:
            # res=render_file(fs_full_path)
            res=render_file(node_name)
    else:
        pre_matches=glob.glob(fs_full_path+'.*')
        matches=[m[len(wiki_base)+1:] for m in pre_matches]
        if len(matches)>1:
            names=[os.path.basename(m) for m in matches]
            res=dir_listing(matches,names,title=node_name)
        elif matches:
            # we need full file path here, not relative to Wiki
            res=render_file(matches[0])

    return res

if __name__ == '__main__':
    app.run(debug=True,use_debugger=True,host='127.0.0.1',port=8000)
