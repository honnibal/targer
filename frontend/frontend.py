#!/usr/bin/env python3

"""be.py: Description."""
from flask import Flask, request
from flasgger import Swagger, LazyString, LazyJSONEncoder
from flask_restful import Api
import json
import sys

"""Front-End"""
from flask import render_template
from json import JSONDecodeError
import requests
from elasticsearch import Elasticsearch
import re
import json

"""Spacy"""
import spacy

nlp = spacy.load('xx')
#path = "/argsearch/"
path = "./"


class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask(__name__)
app.json_encoder = LazyJSONEncoder

ES_SERVER = {"host": "es", "port": 9200}
INDEX_NAME = 'arguments'
es = Elasticsearch(hosts=[ES_SERVER])

reversed = True

if (reversed):
    app.wsgi_app = ReverseProxied(app.wsgi_app)
    template2 = dict(swaggerUiPrefix=LazyString(lambda: request.environ.get('HTTP_X_SCRIPT_NAME', '')))
    swagger = Swagger(app, template=template2)
else:
    swagger = Swagger(app)

api = Api(app)


class Sender:
    def send(self, text, classifier):

        if classifier == "WD":
            url = "http://backend:6000/classifyWD"
        elif classifier == "WD_dep":
            url = "http://backend:6000/classifyWD_dep"
        elif classifier == "ES":
            url = "http://backend:6000/classifyES"
        elif classifier == "ES_dep":
            url = "http://backend:6000/classifyES_dep"
        elif classifier == "IBM":
            url = "http://backend:6000/classifyIBM"
        elif classifier == "Combo":
            url = "http://backend:6000/classifyCombo"
        elif classifier == "NEWPE":
            url = "http://backend:6000/classifyNewPE"
        elif classifier == "NEWWD":
            url = "http://backend:6000/classifyNewWD"

        try:
            r = requests.post(url, data=text.encode("utf-8"))
            return r.json()
        except JSONDecodeError:
            print("!!!!", len(text), text)
            pass


sender = Sender()


@app.route('/')
def index():
    if request.url[-1] != '/':
        return redirect(request.url + '/')
    return render_template('displacy.html', title="Argument Entity Visualizer", page="index", path=path)


@app.route('/search_text', methods=['POST'])
def search_text():
    text = request.form.get('username')
    where_to_seach = request.form.getlist('where[]') # List like ['premise', 'claim', 'named_entity', 'text']
    return search_in_es(text, where_to_seach)


@app.route('/label_text', methods=['POST'])
def background_process_arg():
    text = request.form.get('username')

    data = []

    # Arg-Mining Tags
    classifier = request.form.get('classifier')
    doc = sender.send(text, classifier)
    currentPos = 0
    for sentence in doc:
        for token in sentence:
            start = text.find(token["token"], currentPos)
            end = start + len(token["token"])
            currentPos = end
            currentWord = {}
            currentWord['start'] = start
            currentWord['end'] = end
            currentWord['type'] = token["label"]
            data.append(currentWord)

    data = do_label_arg(data)

    doc = nlp(text)
    for ent in doc.ents:
        entry = {'start': ent.start_char, 'end': ent.end_char, 'type': ent.label_}
        data.append(entry)

    return json.dumps(data)


def do_label_arg(marks):
    # print("marks:" + str(marks))
    marks_new = []
    for i, item in enumerate(marks):
        # for (var i = 0; i < marks.length; i++):
        if i > 0 and i + 1 < len(marks):
            # Start Label
            if marks[i]['type'][0] == "P" and marks[i - 1]['type'][0] != marks[i]['type'][0]:
                mark = {'type': "PREMISE", 'start': marks[i]['start']}
                marks_new.append(mark)
            elif marks[i]['type'][0] == "C" and marks[i - 1]['type'][0] != marks[i]['type'][0]:
                mark = {'type': "CLAIM", 'start': marks[i]['start']}
                marks_new.append(mark)
                # End Label
            if marks[i]['type'][0] == "P" or marks[i]['type'][0] == "C":
                if marks[i]['type'][0] != marks[i + 1]['type'][0]:
                    mark = marks_new.pop()
                    mark['end'] = marks[i]['end']
                    marks_new.append(mark)
        elif i == 0 and i + 1 < len(marks):
            # Start Label
            if marks[i]['type'][0] == "P":
                mark = {'type': "PREMISE", 'start': marks[i]['start']}
                marks_new.append(mark)
            elif (marks[i]['type'][0] == "C"):
                mark = {'type': "CLAIM", 'start': marks[i]['start']}
                marks_new.append(mark)
            # End Label
            if marks[i]['type'][0] == "P" or marks[i]['type'][0] == "C":
                if marks[i]['type'][0] != marks[i + 1]['type'][0]:
                    mark = marks_new.pop()
                    mark['end'] = marks[i]['end']
                    marks_new.append(mark)
        elif i == 0 and i + 1 == len(marks):
            # End Label
            if marks[i]['type'][0] == "P" or marks[i]['type'][0] == "C":
                mark['end'] = marks[i]['end']
                marks_new.append(mark)
    return marks_new


SEARCH_KEY_PREMISE = 'premise'
SEARCH_KEY_CLAIM = 'claim'
SEARCH_KEY_ENTITY = 'named_entity'
SEARCH_KEY_TEXT = 'text'

def get_search_field(path, field, query):
    return {"nested": {
                "path": path,
                "query": {
                    "bool": {
                        "must": [{"match": {
                            field: {"query": query}}}]
                    }
                }
           }}

number_of_sentences_around = 3

def search_in_es(query, where_to_seach):
    docs = []

    search_query = query[:100]

    highlight_field = ""
    search_elements = []
    for search_category in where_to_seach:
        if search_category == SEARCH_KEY_TEXT:
            search_elements.append(get_search_field("sentences", "sentences.text", search_query))
            highlight_field = "sentences.text"
        if search_category == SEARCH_KEY_PREMISE:
            search_elements.append(get_search_field("sentences", "sentences.premise", search_query))
            highlight_field = "sentences.premise"
        if search_category == SEARCH_KEY_CLAIM:
            search_elements.append(get_search_field("sentences", "sentences.claim", search_query))
            highlight_field = "sentences.claim"
        if search_category == SEARCH_KEY_ENTITY:
            search_elements.append(get_search_field("sentences.entities", "sentences.entities.text", search_query))
            highlight_field = "sentences.entities.text"


    if len(search_elements) == 0:
        search_elements.append(get_search_field("sentences", "sentences.text", search_query))
        highlight_field = "sentences.text"

    res = es.search(index=INDEX_NAME, request_timeout=60, body={"from": 0, "size": 25,

                                            "query": {
                                                "bool": {
                                                    "should": search_elements
                                                }
                                            },
                                            "highlight": {
                                                "pre_tags": [""],
                                                "post_tags": [""],
                                                "fields": {
                                                    highlight_field: {
                                                        "type": "plain",
                                                        "fragment_size": 125,
                                                        "number_of_fragments": 1,
                                                        "fragmenter": "simple"
                                                    }
                                                }
                                            }})

    query_words = search_query.strip().split()
    print("Got %d Hits:" % res['hits']['total'])
    for hit in res['hits']['hits']:
        try:
            doc = {}
            text_full = ""

            arguments_positions = []
            entity_positions = []
            query_search_positions = []

            top_match = hit["highlight"][highlight_field][0]
            sentences = hit["_source"]["sentences"]

            x = [x for x in sentences if top_match in x["text"]][0]

            index_with_top_match = sentences.index(x)

            # finding for sentences indexes to show
            if len(sentences) < 7:
                min_pos = 0
                max_pos = len(sentences) - 1
            elif index_with_top_match < number_of_sentences_around:
                min_pos = 0
                max_pos = number_of_sentences_around * 2
            elif index_with_top_match > (len(sentences) - (number_of_sentences_around * 2 + 2)):
                min_pos = (len(sentences) - (number_of_sentences_around * 2 + 2))
                max_pos = (len(sentences) - 1)
            else:
                min_pos = index_with_top_match - number_of_sentences_around
                max_pos = index_with_top_match + number_of_sentences_around

            for sentence_index in range(min_pos, max_pos):

                sentence = sentences[sentence_index]

                offset = len(text_full)
                sentence_text_adjusted = adjust_punctuation(sentence['text'])
                text_full += sentence_text_adjusted + " "

                # finding positions for claims
                if SEARCH_KEY_CLAIM in where_to_seach:
                    for claim in sentence["claim"]:
                        claim_adjusted = adjust_punctuation(claim)
                        start_pos = sentence_text_adjusted.find(claim_adjusted)
                        end_pos = start_pos + len(claim_adjusted)
                        arguments_positions.append({"type": "claim", "start": offset + start_pos, "end": offset + end_pos})

                # finding positions for premises
                if SEARCH_KEY_PREMISE in where_to_seach:
                    for premise in sentence["premise"]:
                        premise_adjusted = adjust_punctuation(premise)
                        start_pos = sentence_text_adjusted.find(premise_adjusted)
                        end_pos = start_pos + len(premise_adjusted)
                        arguments_positions.append({"type": "premise", "start": offset + start_pos, "end": offset + end_pos})

                # finding positions for entities
                if SEARCH_KEY_ENTITY in where_to_seach:
                    for entity in sentence["entities"]:
                        if entity["class"].upper() == "ORGANIZATION": type = "ORG"
                        elif entity["class"].upper() == "LOCATION": type = "LOC"
                        else: type = entity["class"]
                        text = adjust_punctuation(entity["text"])
                        start_pos = sentence_text_adjusted.find(text)
                        end_pos = start_pos + len(text)
                        entity_positions.append({"type": type, "start": offset + start_pos, "end": offset + end_pos})

            #finding positions for search query instances
            for word in query_words:
                for match in set(re.findall(word, text_full, re.IGNORECASE)):
                    positions = [{"type": "search", "start": m.start(), "end": m.end()} for m in re.finditer(match, text_full)]
                    query_search_positions.extend(positions)


            doc["text_with_hit"] = adjust_punctuation(hit["highlight"][highlight_field][0])
            doc["text_full"] = text_full
            doc["query_positions"] = query_search_positions
            doc["arguments_positions"] = arguments_positions
            doc["entity_positions"] = entity_positions
            doc["url"] = hit["_source"]["url"]
            docs.append(doc)
        except:
            print("Unexpected error:", sys.exc_info()[0])

    return json.dumps(docs)

def adjust_punctuation(text):
    return re.sub(r'\s([?.!,:;\'"](?:\s|$))', r'\1', text)

if __name__ == "__main__":
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=6001, debug=False)
