from flask_frozen import Freezer
from wiki import app,wiki_base

import os

freezer = Freezer(app)

@freezer.register_generator
def serve_node():
    for root, dirs, files in os.walk(wiki_base, topdown=False):
        # for name in files+dirs:
        for name in files:
            full_path=os.path.join(root,name)
            wiki_path='/'+full_path[len(wiki_base)+1:]
            yield {'node_name': wiki_path }

if __name__ == '__main__':
    freezer.freeze()
