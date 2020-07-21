import elasticsearch
from ssl import create_default_context
import time 
from os.path import join, dirname, realpath
import json 
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv(override=True)

cafile_path = os.getenv('SSL_CA_PATH')

index_name = "my_index"

elastic = elasticsearch.Elasticsearch(['localhost'],
                                      http_auth=('admin', 'admin'),
                                      scheme="https",
                                      port=9200,
                                      ssl_context=create_default_context(cafile=cafile_path))

def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        print('{:s} function took {:.3f} ms'.format(f.__name__, (time2-time1)*1000.0))

        return ret
    return wrap

def get_vector_by_id(id):
    return elastic.get(index_name,id)['_source']['vector']

def get_name_by_id(id):
    return elastic.get(index_name,id)['_source']['filename']

@timing
def get_knn_by_id(id,k):
    return [(hit['_source']['filename'], hit['_score']) for hit in elastic.search(body={"size": k, 
                         "query": {"knn": {"vector": {"vector": get_vector_by_id(id),
                                                      "k": k
                                                      }
                                          }
                                  }
                        })['hits']['hits']]



id = input("Id of reference document :")
k = input("Number of neighbors to search for :")

knn = get_knn_by_id(id,k)
reference = get_name_by_id(id)

print("""
Reference : {}

Neighbors : 
{}
""".format(reference, '\n'.join(["Name : {} Score : {}".format(n,s) for n,s in knn])))

