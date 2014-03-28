fliki
=====

Flask-based, filesystem-backed miniature read-only Wiki rendering engine using reSturcturedText markup

Any modifications are done on filesystem, there is no editing capability (and none planned). However system
should pick up changes on filesystem immediately.


Requirements
============

* flask
* docutils


Usage
=====

create folder stucture::

  my_wiki/
    content/
    compiled/

and execute wiki.py from within my_wiki folder::

  $ cd my_wiki
  $ python /path/to/wiki.py

point your browser to "localhost:8000" and explore your Wiki

