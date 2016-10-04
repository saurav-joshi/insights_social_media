#! /usr/bin/env python
# -*- coding: utf-8 -*-

from nltk.parse.stanford import StanfordParser
from nltk.tag.stanford import StanfordNERTagger
import nltk
from nltk.tree import ParentedTree
import pandas as pd
from nltk import tokenize
import cleaner_tweets as c
from nltk.tokenize import TweetTokenizer
import cleaner_tweets
import string
import os
#english_parser = StanfordParser(os.path.join(os.path.curdir,'resources','stanford-parser.jar'),os.path.join(os.path.curdir,'resources','stanford-parser-3.4.1-models.jar'))

kw_phrases=[]
kw_unigrams=[]


def traverse_tree(t):

    try:
        t.label()
    except AttributeError:
        return
    else:

        if t.height() == 3 and (t.label() in ['NP']):
            if(len(t) == 1 and t[0].label()=='PRP'):
                None
            else:
                #print t
                #print "*******"
                #print t[0]
                count_nouns = 0
                num_children = len(t.leaves())
                prp_flag=False

                for i in range(num_children):
                    if (t[i].label() in ['NNPS','PRP','PRP$','NN','NNS','NNP','JJ','CC'] or (t[i].label()=="DT" and ' '.join(t[i].leaves()).strip().lower() in ["a","the"])):
                        count_nouns = count_nouns+1
                        if(t[i].label() in ['PRP','PRP$']):
                            prp_flag=True


                if(count_nouns==num_children):
                    if(prp_flag):
                        prp_flag=False
                        remove_phrase = t.leaves().pop(0)
                        phrase = [word for word in t.leaves() if word != remove_phrase]
                    else:
                        phrase = t.leaves()

                    phrase=' '.join(phrase).lower()

                    if len(phrase.split()) >= 2:
                        kw_phrases.append(phrase)
        elif t.height() == 2 and (t.label() in ['NNS','NN','NNPS']):
            kw_unigrams.append(' '.join(t.leaves()).lower())

        for child in t:
            traverse_tree(child)

def fetch_phrases_and_words(text_list,english_parser):
    new_list=[]
    for t in text_list:
        try:
            t.decode('ascii')
            new_list.append(t)
        except UnicodeDecodeError:
            new_list.append(''.join([i if ord(i) < 128 else ' ' for i in t]))

    i = english_parser.raw_parse_sents(new_list)
    for aa in i:
        op= aa.next()
        traverse_tree(op)
        #print op.pretty_print()

    return kw_unigrams,kw_phrases

def convert_to_ascii(text):
    text = ''.join([i if ord(i) < 128 else ' ' for i in text])
    #text = ''.join(''.join(s)[:2] for _, s in itertools.groupby(text))
    return text

if __name__ == "__main__":

    text = ["When she knows she's gonna be walking through chicken crap so she puts on your shoes even though hers are right there"]
    #fetch_phrases_and_words(text,english_parser)
    print kw_unigrams
    print kw_phrases
    #text=["I love that shirt"]

