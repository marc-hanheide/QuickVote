#!/usr/bin/env python

from pymongo import MongoClient
from pprint import pprint
import config
client = MongoClient(config.mongo_host, config.mongo_port)


class Reporter:

    def __init__(self, domain):
        self.qv_db = client['QuickVote']
        self.answers = self.qv_db['answers']
        self.questions = self.qv_db['questions']
        self.domain = domain

    def get_stats(self, answers, question):
        results = {}
        sorted_keys = []

        total_submissions = 0.0
        total_correct_submissions = 0.0
        tp = 0.0
        tn = 0.0
        fp = 0.0
        fn = 0.0

        for answer in answers:

            correct = True
            for opt in question['options']:
                if opt not in results:
                    results[opt] = 0
                if opt in answer:
                    results[opt] += 1
                    if opt in question['correct']:
                        tp += 1
                    else:
                        fp += 1
                        correct = False
                else:
                    if opt in question['correct']:
                        correct = False
                        fn += 1
                    else:
                        tn += 1

            total_correct_submissions += 1 if correct else 0
            total_submissions += 1

        sorted_keys = results.keys()
        sorted_keys.sort()

        try:
            sensitivity = tp / (tp + fn)
        except:
            sensitivity = 1

        try:
            specificity = tn / (tn + fp)
        except:
            specificity = 1
        try:
            accuracy = (tp + tn) / (tp + tn + fp + fn)
        except:
            accuracy = 1
        try:
            corrects_ratio = float(total_correct_submissions) / total_submissions
        except:
            corrects_ratio = 1

        return [total_submissions, total_correct_submissions, sensitivity, specificity, accuracy, corrects_ratio]

    def get_qids(self):
        res = {}
        qids = self.answers.find({'domain': self.domain}).distinct('uuid')
        for q in qids:
            question = self.questions.find_one({'domain': self.domain, 'uuid': q})
            res[q] = question['question']
        return res

    def get_user_stats(self, valid_qids):
        res = {}
        ip_res = {}
        qids = self.answers.find({'domain': self.domain, 'uuid': {'$in': valid_qids}}).distinct('uuid')
        for q in qids:
            question = self.questions.find_one({'domain': self.domain, 'uuid': q})
            ips = self.answers.find({'domain': self.domain, 'uuid': q}).distinct('env.REMOTE_ADDR')
            res[q] = {}
            for i in ips:
                answers = self.answers.find({'domain': self.domain, 'uuid': q,'env.REMOTE_ADDR': i})
                res[q][i] = self.get_stats(answers, question)
 #               print q, i
                if i not in ip_res:
                    ip_res[i] = [0.0, 0.0]
                ip_res[i][0] += res[q][i][0]
                ip_res[i][1] += res[q][i][1]

        for k,v in ip_res.items():
            ip_res[k] = v[1] / v[0]
        
        return ip_res



r = Reporter("CMP1036M")

pprint(r.get_qids())

lecture_7 = [
    'cea8cda7-6bf3-4db8-a3ef-8b09d8bfcb5e',
    'dbf74c44-6d38-40c9-8240-1cc1fd284e44',
    'e0c303dd-be3b-4c51-a42b-b7b55c61d58a',
    'e7f5e26e-dc68-4080-a6a4-7dd8cc9dbfc8',
    'f545cf28-89cb-49b0-85af-c560e19addfa',
    'fc972337-fa62-4ae3-9cad-8484b9d01278'
]

lecture_9 = [
    '038b54aa-ee53-4f61-9355-866899b5b4cb',
    '2ccbd7b2-3474-46f0-86b7-5895144eb3fd',
    '583e4399-6257-45c7-b9eb-f5ce6d44e3d1',
    '6873019e-82d7-4970-a064-0cd5c63b8b55',
    'ac97edea-50f3-4b5e-8933-402ab6308b0d',
    'f6d12ed4-9630-4b46-875a-c4f36421f71c'
]

#pprint(r.get_user_stats(lecture_7))

res = r.get_user_stats(lecture_9)

print res.values()
