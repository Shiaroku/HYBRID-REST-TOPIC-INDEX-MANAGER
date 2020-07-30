import elasticsearch
from ssl import create_default_context
import time 
from os.path import join, dirname, realpath
import json 
import numpy as np
import os
from dotenv import load_dotenv
import requests


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


def id_query(id,k):
    knn = get_knn_by_id(id,k)
    reference = get_name_by_id(id)
    return """\nReference : {} \n\nNeighbors : \n\n{}""".format(os.path.basename(reference), '\n'.join(["Name : {} Score : {}".format(os.path.basename(n),s) for n,s in knn]))

token = requests.request("POST", "http://127.0.0.1:8000/api/v1/auth/", data = {'username': os.getenv('DJANGO_USER'), 'password': os.getenv('DJANGO_PWD')}).json()['access']

def vectoREST(text, url = "http://127.0.0.1:8000/api/v1/vectors/fr/", token = token):
    payload = {'content': text}
    headers = {'Authorization': 'Bearer {}'.format(token)}
    response = requests.request("POST", url, headers=headers, data = payload)
    return list(response.json()['dense_vector'].values())

def smart_query(text,k):
    vector = vectoREST(text) 
    knn = [(hit['_source']['filename'], hit['_score']) for hit in elastic.search(body={"size": k, 
                         "query": {"knn": {"vector": {"vector": vector,
                                                      "k": k
                                                      }
                                          }
                                  }
                        })['hits']['hits']]
    return """\nText : {} \n\nNeighbors : \n\n{}""".format(text, '\n'.join(["Name : {} Score : {}".format(os.path.basename(n),s) for n,s in knn]))


keep_going = True

while keep_going:
    id = input("Id of reference document : ")
    k = input("Number of neighbors to search for : ")
    print(id_query(id,k))
    keep_going = (input("Would you like to run another query ? (y/n): " ).lower()!="n")

keep_going = True

while keep_going:
    smart_text = input("Smart query : ")
    k = input("Number of neighbors to search for : ")
    print(smart_query(smart_text,k))
    keep_going = (input("Would you like to run another query ? (y/n): " ).lower()!="n")


