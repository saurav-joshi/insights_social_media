#! /usr/bin/env python

from __future__ import division
import cleaner_tweets
import pandas as pd
import collections
import re
from nltk.parse.stanford import StanfordParser
from nltk import tokenize
from nltk.corpus import stopwords
from nltk.tokenize import TweetTokenizer
import string
import logging
import multiprocessing
import os
import information_parser
import itertools
import requests
import json
import time
import csv
import sys
from datetime import datetime

startTime = datetime.now()


with open(os.path.join(os.path.curdir,'results','keywords_unigram111.csv'),"wb") as csvfile:
    writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['category','rank','keyword','affinity'])

with open(os.path.join(os.path.curdir,'results','keywords_phrases111.csv'),"wb") as csvfile:
    writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['category','rank','keyword','affinity'])

with open(os.path.join(os.path.curdir,'results','hashtags111.csv'),"wb") as csvfile:
    writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['category','rank','hashtag','affinity'])

with open(os.path.join(os.path.curdir,'results','entities111.csv'),"wb") as csvfile:
    writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['category','rank','entity','entity_type','affinity'])


#logger = logging.getLogger('apscheduler.executors.default')

logger = multiprocessing.get_logger()
hdlr = logging.FileHandler(os.path.join(os.path.curdir,'logs','myapp.log'))
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger.info("Loading Stanford models ...")

category_tweets_queue = multiprocessing.Queue()

entities_queue = multiprocessing.Queue()

unigram_queue = multiprocessing.Queue()
phrases_queue = multiprocessing.Queue()
hashtags_queue = multiprocessing.Queue()


def convert_to_ascii(text):
    text = ''.join([i if ord(i) < 128 else ' ' for i in text])
    text = ''.join(''.join(s)[:2] for _, s in itertools.groupby(text))
    return text

def find_corelation(tweets_clf_df):
    top_cat_df = tweets_clf_df.groupby("first_pred").size().reset_index().sort_values(0,ascending=False)
    with open(os.path.join(os.path.curdir,'results','corelation111.csv'),"wb") as csvfile:
        writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['primary_category','primary_cat_rank','second_category','affinity_score'])
        cat_rank=1
        for idx,row_top_cat in top_cat_df.iterrows():
            try:
                top_trending_cat = row_top_cat['first_pred']

                top_cat_tweets_df = tweets_clf_df[tweets_clf_df.first_pred == top_trending_cat]

                total_value = top_cat_tweets_df.groupby("second_pred").size().reset_index().sum()[0]

                for index,row in top_cat_tweets_df.groupby("second_pred").size().reset_index().iterrows():
                    try:
                        writer.writerow([top_trending_cat,cat_rank,row['second_pred'],100*(row[0]/total_value)])
                    except Exception as e:
                        logger.debug(e.message)
                        logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))
                cat_rank=cat_rank+1
            except Exception as e:
                logger.debug(e.message)
                logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

def extract_insights():
    try:
        logger.info("Reading classified tweets ...")

        tweets_clf_df = pd.read_csv(os.path.join(os.path.curdir,'results','real_test.csv'), error_bad_lines=False)
        #tweets_clf_df = tweets_clf_df[:20]
        find_corelation(tweets_clf_df)
        top_cat_df = tweets_clf_df.groupby("first_pred").size().reset_index().sort_values(0,ascending=False)
        total_categories = top_cat_df.shape[0]
        #logger.info("total_categories: "+total_categories)
        category_rank = 1

        #pool = multiprocessing.Pool(total_categories, extract_cat_insights,(category_tweets_queue,))

        # instantiate workers
        workers = [multiprocessing.Process(target=extract_cat_insights, args=(category_tweets_queue,))
                   for i in range(total_categories)]

        # start the workers
        for w in workers:
            w.start()

        for index,row in top_cat_df.iterrows():
            try:
                top_trending_cat = row['first_pred']

                top_cat_tweets_df = tweets_clf_df[tweets_clf_df.first_pred == top_trending_cat]
                category_tweets_queue.put({'dataframe':top_cat_tweets_df,'rank':category_rank,'category':top_trending_cat})
                category_rank = category_rank + 1

                #break
            except Exception as e:
                logger.debug(e.message)
                logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

        #pool.close()
        '''
        p = multiprocessing.Pool(total_categories)
        cat_dict_list=[]
        for index,row in top_cat_df.iterrows():
            try:
                top_trending_cat = row['first_pred']

                top_cat_tweets_df = tweets_clf_df[tweets_clf_df.first_pred == top_trending_cat]
                cat_dict_list.append({'dataframe':top_cat_tweets_df,'rank':category_rank,'category':top_trending_cat})
                category_rank = category_rank + 1

                #break
            except Exception as e:
                logger.debug(e.message)
                logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

        p.imap(extract_cat_insights,cat_dict_list)
        '''
        unigram_count=0
        phrases_count=0
        hashtags_count=0
        entites_count=0

        while True:
            try:
                if unigram_count !=total_categories and not unigram_queue.empty():

                    d = unigram_queue.get(False)
                    if(d=="unigrams_done"):

                        unigram_count=unigram_count+1

                    else:
                        with open(os.path.join(os.path.curdir,'results','keywords_unigram111.csv'),"a") as csvfile:
                            if(len(d)!=0):
                                for keyword in d.get('kw_uni'):
                                    try:
                                        writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                                        writer.writerow([d.get('category'),d.get('rank'),keyword[0],100*(keyword[1]/d.get('total_tweets_cat'))])
                                    except Exception as e:
                                        logger.debug(e.message)
                                        logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))




                if phrases_count !=total_categories and not phrases_queue.empty():
                    d = phrases_queue.get(False)

                    if(d=="phrases_done"):

                        phrases_count=phrases_count+1

                    else:
                        with open(os.path.join(os.path.curdir,'results','keywords_phrases111.csv'),"a") as csvfile:
                            if(len(d)!=0):
                                for keyword in d.get('kw_phr'):
                                    try:
                                        writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                                        writer.writerow([d.get('category'),d.get('rank'),keyword[0],100*(keyword[1]/d.get('total_tweets_cat'))])
                                    except Exception as e:
                                        logger.debug(e.message)
                                        logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))




                if hashtags_count !=total_categories and not hashtags_queue.empty():
                    d = hashtags_queue.get(False)

                    if(d=="hashtags_done"):
                        hashtags_count=hashtags_count+1
                    else:
                        with open(os.path.join(os.path.curdir,'results','hashtags111.csv'),"a") as csvfile:
                            if(len(d)!=0):
                                for hashtag in d.get('hashtags'):
                                    try:
                                        writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                                        writer.writerow([d.get('category'),d.get('rank'),hashtag[0],100*(hashtag[1]/d.get('total_tweets_cat'))])
                                    except Exception as e:
                                        logger.debug(e.message)
                                        logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))


                try:
                    if entites_count !=total_categories and not entities_queue.empty():
                        org_list = {}
                        people_list = {}
                        places_list = {}
                        entities_dict= entities_queue.get(False)
                        if entities_dict == "entities_done":
                            entites_count = entites_count+1
                        else:
                            for each_sent in entities_dict['sentences']:
                                try:

                                    r= requests.get('http://localhost:9090/CLIFF-2.1.1/parse/text', params={'q': each_sent})
                                except:
                                    logger.info("Reconnecting to CLIFF server ....")
                                    time.sleep(10)
                                    r= requests.get('http://localhost:9090/CLIFF-2.1.1/parse/text', params={'q': each_sent})

                                entities = json.loads(r.content)

                                try:
                                    if entities.get('status') == 'ok':

                                        orgs = entities.get('results').get('organizations')

                                        if orgs != None:
                                            for eachOrg in orgs:
                                                try:
                                                    eachOrgName = str(eachOrg.get('name').encode('utf-8', 'ignore')).translate(
                                                        string.maketrans("", ""), string.punctuation).lower()
                                                    if not eachOrgName in org_list:
                                                        org_list[eachOrgName] = eachOrg.get('count')
                                                    else:
                                                        org_list[eachOrgName] = org_list.get(eachOrgName) + eachOrg.get('count')
                                                except Exception as e:
                                                    logger.debug(e.message)
                                                    logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))


                                        people = entities.get('results').get('people')
                                        if people != None:
                                            for eachPerson in people:
                                                try:

                                                    eachPersonName = str(eachPerson.get('name').encode('utf-8', 'ignore')).translate(
                                                        string.maketrans("", ""), string.punctuation).lower()
                                                    if not eachPersonName in people_list:
                                                        people_list[eachPersonName] = eachPerson.get('count')
                                                    else:
                                                        people_list[eachPersonName] = people_list.get(eachPersonName) + eachPerson.get('count')
                                                except Exception as e:
                                                    logger.debug(e.message)
                                                    logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))


                                        locations = entities.get('results').get('places')
                                        if locations != None:
                                            places = locations.get('mentions')
                                            if places != None:
                                                for eachPlace in places:
                                                    try:
                                                        eachPlaceName = str(eachPlace.get('name').encode('utf-8', 'ignore')).translate(
                                                            string.maketrans("", ""), string.punctuation).lower()
                                                        if not eachPlaceName in places_list:
                                                            places_list[eachPlaceName] = 1
                                                        else:
                                                            places_list[eachPlaceName] = places_list.get(eachPlaceName) + 1
                                                    except Exception as e:
                                                        logger.debug(e.message)
                                                        logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

                                except Exception as e:
                                    logger.debug(e.message)
                                    logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))


                            organizations = dict(collections.Counter(org_list).most_common(
                        50))
                            places = dict(collections.Counter(places_list).most_common(
                        50))
                            people = dict(collections.Counter(people_list).most_common(
                        50))

                            with open(os.path.join(os.path.curdir,'results','entities111.csv'),"a") as csvfile:
                                writer = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)


                                for key in organizations.keys():
                                    try:
                                        writer.writerow([entities_dict.get('category'),entities_dict.get('subcategory'),entities_dict.get('rank'),key,'organizations',100*(organizations.get(key)/entities_dict.get('total_tweets_cat'))])
                                    except:
                                        None
                                for key in places.keys():
                                    try:
                                        writer.writerow([entities_dict.get('category'),entities_dict.get('subcategory'),entities_dict.get('rank'),key,'places',100*(places.get(key)/entities_dict.get('total_tweets_cat'))])
                                    except:
                                        None

                                for key in people.keys():
                                    try:
                                        writer.writerow([entities_dict.get('category'),entities_dict.get('subcategory'),entities_dict.get('rank'),key,'people',100*(people.get(key)/entities_dict.get('total_tweets_cat'))])
                                    except:
                                        None
                except Exception as e:
                    logger.debug(e.message)
                    logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

                #if unigram_count == phrases_count == hashtags_count == entites_count == total_categories:
                if unigram_count == phrases_count == hashtags_count == total_categories:
                    break

            except Exception as e:

                logger.debug(e.message)
                logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))
                break

        #call_cliff(total_categories)

        #pool.join()
        # join on the workers

        for w in workers:
            w.join()

        logger.info("Writing extracted keywords,entities etc to csv files")

        logger.info("twitter insights ran successfully !!!")
    except Exception as e:
        logger.debug(e.message)
        logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

def extract_cat_insights(category_tweets_queue):
    try:
        english_parser = StanfordParser(os.path.join(os.path.curdir,'resources','stanford-parser.jar'),os.path.join(os.path.curdir,'resources','stanford-parser-3.4.1-models.jar'))
        cat_details = category_tweets_queue.get(True)
        #logger.info(cat_details['category']+" started . . . .")
        #print os.getpid()+" - "+cat_details['category']
        clean_tweets_list = []
        raw_tweets = []

        unigrams={}
        phrases={}
        hashtags={}
        entites={}

        for tweet in cat_details['dataframe']['tweet']:
            try:
                tweet = convert_to_ascii(tweet)
                tknzr = TweetTokenizer(reduce_len=True)
                tweet = ' '.join(tknzr.tokenize(tweet))
                raw_tweets.append(tweet)
                sentences = [
                    cleaner_tweets.clean(sent).replace('<hashtag>', '').replace('<allcaps>', '') for
                    sent in tokenize.sent_tokenize(tweet)]
            except Exception as e:
                    logger.debug(e.message)
                    logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))
            for each_sent in sentences:
                try:
                    clean_tweets_list.append(each_sent.encode('utf-8').translate(string.maketrans("",""), string.punctuation))
                except Exception as e:
                    logger.debug(e.message)
                    logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

        total_tweets_cat = len(raw_tweets)
        raw_tweets_doc = ' '.join(raw_tweets)

        try:
            entites['category'] = cat_details['category']
            entites['rank']=cat_details['rank']
            entites['total_tweets_cat'] = total_tweets_cat
            entites['sentences'] = clean_tweets_list
            entities_queue.put(entites)
            entities_queue.put("entities_done")
        except Exception as e:
                entites = {}
                entities_queue.put(entites)
                entities_queue.put("entities_done")
                logger.debug(e.message)
                logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))


        try:
            hashtags['category'] = cat_details['category']
            hashtags['rank']=cat_details['rank']
            hashtags['hashtags'] = collections.Counter(re.findall(r"#(\w+)", raw_tweets_doc.lower())).most_common(50)
            hashtags['total_tweets_cat'] = total_tweets_cat
        except Exception as e:
                hashtags={}
                logger.debug(e.message)
                logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))

        try:
            kw_unigrams, kw_phrases = information_parser.fetch_phrases_and_words(clean_tweets_list, english_parser)
            keywords_uni = [eachWord.encode('utf-8').translate(string.maketrans("", ""), string.punctuation).lower() for eachWord in kw_unigrams if eachWord not in stopwords.words('english')]
            kw_uni = collections.Counter(keywords_uni).most_common(50)
            unigrams['category'] = cat_details['category']
            unigrams['rank']=cat_details['rank']
            unigrams['kw_uni'] = kw_uni
            unigrams['total_tweets_cat'] = total_tweets_cat

        except Exception as e:
            logger.debug(e.message)
            logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))
            unigrams={}


        try:
            keywords_phr = [eachWord.encode('utf-8').translate(string.maketrans("", ""), string.punctuation).lower() for eachWord in kw_phrases if eachWord not in stopwords.words('english')]
            kw_phr = collections.Counter(keywords_phr).most_common(50)
            phrases['category'] = cat_details['category']
            phrases['rank']=cat_details['rank']
            phrases['kw_phr'] = kw_phr
            phrases['total_tweets_cat'] = total_tweets_cat
        except Exception as e:
            logger.debug(e.message)
            logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))
            phrases={}

        #print kw_uni
        #print kw_phr
        unigram_queue.put(unigrams)
        unigram_queue.put("unigrams_done")
        phrases_queue.put(phrases)
        phrases_queue.put("phrases_done")
        hashtags_queue.put(hashtags)
        hashtags_queue.put("hashtags_done")

        logger.info(cat_details['category']+" completed !!!!")
    except Exception as e:
            logger.debug(e.message)
            logger.debug('Error on line {} in file {}'.format(sys.exc_info()[-1].tb_lineno,sys.exc_info()[-1].tb_frame.f_code.co_filename))


if __name__ == "__main__":
    extract_insights()
    logger.info("Execution time: "+str((datetime.now() - startTime)))
