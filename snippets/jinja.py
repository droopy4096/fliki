#!/bin/env python


from jinja2 import Environment, FileSystemLoader

def getBody():
    yield "line 1"
    yield "line 2"
    yield "line 3"
    yield "line 4"
    yield "line 5"


env = Environment(loader=FileSystemLoader('templates'))

template = env.get_template('body.html')

for l in template.generate(body=getBody()):
    print l
