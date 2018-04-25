#!/usr/bin/env python3

"""be.py: Description."""
from flask import Flask, jsonify
from flasgger import Swagger
from flask_restful import Api, Resource
from flask import make_response
from nltk.tokenize import sent_tokenize, word_tokenize
import random
import json

app = Flask(__name__)
api = Api(app)
swagger = Swagger(app)

class Inputtext(Resource):
    def get(self, inputtext):
       """
       Takes a input sequence and assigns label with highes probability (mockup)
       ---
       parameters:
         - in: path
           name: inputtext
           type: string
           required: true
       responses:
         200:
           description: JSON-List of tokens annotated with labels and probabilities
           schema:
             id: Returntext
             properties:
               returntext:
                 type: string
                 description: JSON-List
                 default: No input text set
        """
       response = process(inputtext)
       #return {'returntext': inputtext}, 200
       return response

def process(inputtext):
    tokens = word_tokenize(inputtext)
    result = []
    for token in tokens:
        label, probability = get_prediction(token)
        dict = {'Token': token, 'Label': label, 'P': probability}
        result.append(dict)
    response = make_response(json.dumps(result))
    response.headers['content-type'] = 'application/json'
    return response

def get_prediction(token):
    label = random.choice(["Claim", "Null", "Premise", "Rebuttal"])
    probability = random.uniform(0, 1)
    return label, probability

api.add_resource(Inputtext, '/inputtext/<inputtext>')
app.run(debug=True)
