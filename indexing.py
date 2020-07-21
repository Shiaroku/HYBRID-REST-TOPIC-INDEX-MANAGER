from elasticsearch import Elasticsearch
from ssl import create_default_context
from os import path
import io
from tqdm.auto import tqdm
import numpy as np
from elasticsearch.client.ingest import IngestClient
import requests
import json
import base64
import os
from dotenv import load_dotenv

load_dotenv(override=True)

cafile_path = os.getenv('SSL_CA_PATH')

token = requests.request("POST", "http://127.0.0.1:8000/api/v1/auth/", data = {'username': os.getenv('DJANGO_USER'),
'password': os.getenv('DJANGO_PWD')}).json()['access']

index_name = "my_index"

mappings = {
  "settings": {
    "index": {
      "knn": True
    }
  },
  "mappings": {
    "properties": {
      "filename": {
        "type": "keyword"
      },
      "vector": {
        "type": "knn_vector",
        "dimension": 512
      }
    }
  }
}

es_client = Elasticsearch(
        ['localhost'],
        http_auth=('admin', 'admin'),
        scheme="https",
        port=9200,
        ssl_context=create_default_context(cafile=cafile_path)
        )

p = IngestClient(es_client).put_pipeline(id='ingest_processor', body={
    "description" : "Extract attachment information",
    "processors" : [
        {
                        "attachment" : {
                            "field" : "data",
                            "target_field" : "attachment",
                            "properties" : ["content", "content_type"]
                        },
                        "remove" : {
                            "field" : "data"
                        },
                        "langdetect" : {
                            "if" : "ctx.attachment.content != null",
                            "field" : "attachment.content",
                            "target_field": "lang"
                        },
                        "set" : {
                            "if" : "ctx.lang != null && ctx.lang == \"fr\"",
                            "field" : "content_fr",
                            "value" : "{{attachment.content}}"
                        }
                    }, {
                        "set" : {
                            "if" : "ctx.lang != null && ctx.lang == \"de\"",
                            "field" : "content_de",
                            "value" : "{{attachment.content}}"
                        }
                    }, {
                        "set" : {
                            "if" : "ctx.lang != null && ctx.lang == \"it\"",
                            "field" : "content_it",
                            "value" : "{{attachment.content}}"
                        }
                    }, {
                        "set" : {
                            "if" : "ctx.lang != null && ctx.lang == \"en\"",
                            "field" : "content_en",
                            "value" : "{{attachment.content}}"
                        }
                    }, {
                        "set" : {
                            "if" : "ctx.attachment?.content != null && ctx.content_fr == null && ctx.content_de == null && ctx.content_it == null && ctx.content_en == null",
                            "field" : "content",
                            "value" : "{{attachment.content}}"
                        }
                    }, {
                        "set" : {
                            "if" : "ctx.attachment?.content_type != null",
                            "field" : "type",
                            "value" : "{{attachment.content_type}}"
                        },
                        "remove" : {
                            "field" : "attachment"
                        }
                        
                    }
    ]
})


def create_index(index_name, mappings):
    es_client.indices.create(index=index_name, body=mappings)

def vectoREST(text, url = "http://127.0.0.1:8000/api/v1/vectors/fr/", token = token):
    payload = {'content': text}
    headers = {'Authorization': 'Bearer {}'.format(token)}
    response = requests.request("POST", url, headers=headers, data = payload)
    return list(response.json()['dense_vector'].values())

def open64(filepath):
    with open(filepath, "rb") as f:
        encoded_string = base64.b64encode(f.read())
    return encoded_string


def index_file(filepath, index, id):
    es_client.create(index=index_name, id=id, body= {"data" : open64(filepath)}, pipeline="ingest_processor")
    response = es_client.get(index=index_name, id=id)['_source']
    if not 'lang' in response:
        return
    else:
        lang = response['lang']
    if lang in ["en","fr","de","it"]:
        content = response["content_{}".format(lang)]
    else:
        content = response["content"]
    vector = vectoREST(content)
    es_client.update(index=index_name, id=id, body=
    {
        "script" : {
            "source": """
            ctx._source.vector = params.vector;
            ctx._source.filename = params.filename;
            """,
            "lang": "painless",
            "params" : {
                "vector" : vector,
                "filename" : filepath
            }
        }
    })

def index_directory(dir_path):
    for i, f  in enumerate(tqdm(os.listdir(dir_path))):
        index_file(os.path.join(dir_path, f), index_name, i)


es_client.indices.delete(index=index_name, ignore=[400, 404])
create_index(index_name, mappings)
index_directory(os.path.join(os.path.dirname(__file__),"Gutenberg/txt/"))


