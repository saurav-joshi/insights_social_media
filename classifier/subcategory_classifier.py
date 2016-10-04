#! /usr/bin/env python
import MySQLdb
import pandas as pd
from nltk.tokenize import TweetTokenizer
import cleaner_tweets
import re
import string
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk import word_tokenize
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.cross_validation import cross_val_score
from sklearn.linear_model import SGDClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import VotingClassifier
from sklearn.ensemble import RandomForestRegressor
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesClassifier
from sklearn import metrics
import pickle
import os


def clean_str(string):

    string = re.sub(r"[^A-Za-z0-9(),!?\'\`<>]", " ", string)
    string = re.sub(r"\'s", " \'s", string)
    string = re.sub(r"\'ve", " \'ve", string)
    string = re.sub(r"n\'t", " n\'t", string)
    string = re.sub(r"\'re", " \'re", string)
    string = re.sub(r"\'d", " \'d", string)
    string = re.sub(r"\'ll", " \'ll", string)
    string = re.sub(r",", " , ", string)
    string = re.sub(r"!", " ! ", string)
    string = re.sub(r"\(", " \( ", string)
    string = re.sub(r"\)", " \) ", string)
    string = re.sub(r"\?", " \? ", string)
    string = re.sub(r"\s{2,}", " ", string)
    return string.strip()

class LemmaTokenizer(object):
    def __init__(self):
        self.wnl = WordNetLemmatizer()
    def __call__(self, doc):
        return [self.wnl.lemmatize(t) for t in word_tokenize(doc)]

def tokenize(text):
    txt = "".join([ch for ch in text if ch not in string.punctuation])
    wnl = WordNetLemmatizer()
    return [wnl.lemmatize(t) for t in word_tokenize(txt)]


vectorizer = CountVectorizer(stop_words=stopwords.words('english'),ngram_range=(1, 2),tokenizer=tokenize,max_features=40000)
tfidf_transformer = TfidfTransformer(norm='l2')


mysql_cn= MySQLdb.connect(host='127.0.0.1',
                port=3306,user='root', passwd='root123',
                db='audiences_twitter')

df = pd.read_sql("select distinct label from tweets_clean where label='Fashion';", con=mysql_cn)

categories = df.get('label').tolist()

for category in categories:

    #df = pd.read_sql("select text,sublabel from tweets_clean where label='"+category+"' order by RAND();", con=mysql_cn)
    df = pd.read_sql("select text,sublabel from tweets_clean where label='Fashion' order by RAND();", con=mysql_cn)

    tknzr = TweetTokenizer(reduce_len=True)
    x_text = [cleaner_tweets.clean(' '.join(tknzr.tokenize(text.decode('utf-8','ignore')))).replace('<hashtag>', '').replace('<allcaps>', '') for text in df['text'].tolist()]

    X=[text.encode('utf-8').translate(string.maketrans("",""), string.punctuation) for text in x_text]

    lookup_categories = pd.get_dummies(df['sublabel'].unique().tolist())
    y = np.array([list(lookup_categories.get(eachCat)) for eachCat in df['sublabel'].tolist()])


    term_freq_matrix = vectorizer.fit_transform(X)
    tf_idf_matrix = tfidf_transformer.fit_transform(term_freq_matrix)

    #SGDClassifier
    sgd_clf = SGDClassifier(loss='squared_hinge', penalty='l2',alpha=1e-3, n_iter=5, random_state=42,shuffle=True)
    sgd_clf.fit(tf_idf_matrix, df['sublabel'].tolist())

    scores = cross_val_score(sgd_clf, tf_idf_matrix, df['sublabel'].tolist(),cv=10)
    print category
    print scores
    print("Accuracy: %0.2f (+/- %0.2f)" % (scores.mean(), scores.std() * 2))
    print "------------------"

    '''
    test_df = pd.read_sql("select text,sublabel from `tweets_raw` where label='Travel' order by RAND()", con=mysql_cn)
    test = [cleaner_tweets.clean(' '.join(tknzr.tokenize(text.decode('utf-8','ignore')))).replace('<hashtag>', '').replace('<allcaps>', '') for text in test_df['text'].tolist()]
    test_y = test_df['sublabel'].tolist()

    test=[text.encode('utf-8').translate(string.maketrans("",""), string.punctuation) for text in test]


    X_new_counts = vectorizer.transform(test)
    X_new_tfidf = tfidf_transformer.transform(X_new_counts)
    test_pred = sgd_clf.predict(X_new_tfidf)

    report = metrics.classification_report(test_y, test_pred)
    print report
    '''

    f = open(os.path.join(os.path.curdir,'resources',category.lower()+'_vocab.pickle'), 'wb')
    pickle.dump(vectorizer, f)
    f.close()

    f = open(os.path.join(os.path.curdir,'resources',category.lower()+'_tfidf.pickle'), 'wb')
    pickle.dump(tfidf_transformer, f)
    f.close()

    f = open(os.path.join(os.path.curdir,'resources',category.lower()+'_classifier.pickle'), 'wb')
    pickle.dump(sgd_clf, f)
    f.close()

    '''
    with open("travel_report.txt","wb") as f:
        f.write(report)
    '''
