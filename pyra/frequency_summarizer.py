#!/usr/bin/env python3
import logging
from collections import defaultdict
from heapq import nlargest
from string import punctuation

from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize

logger = logging.getLogger(__name__)


class FrequencySummarizer(object):
    def __init__(self, min_cut=0.1, max_cut=0.9):
        """
         Initilize the text summarizer.
         Words that have a frequency term lower than min_cut
         or higer than max_cut will be ignored.
        """
        self._min_cut = min_cut
        self._max_cut = max_cut
        self._stopwords = set(stopwords.words("english") + list(punctuation))

    def _compute_frequencies(self, word_sent):
        """
            Compute the frequency of each of word.
            Input:
             word_sent, a list of sentences already tokenized.
            Output:
             freq, a dictionary where freq[w] is the frequency of w.
        """
        freq = defaultdict(int)
        for s in word_sent:
            for word in s:
                if word not in self._stopwords:
                    freq[word] += 1
        # frequencies normalization and fitering
        m = float(max(freq.values()))
        new_freq = {}
        for w in freq.keys():
            if freq[w] >= self._max_cut or freq[w] <= self._min_cut:
                continue
            new_freq[w] = freq[w] / m
        return new_freq

    def summarize(self, text, n):
        """
            Return a list of n sentences
            which represent the summary of text.
        """
        sents = sent_tokenize(text)
        if len(sents) < n:
            logging.info("Number of sentences is under {0}".format(n))
            return sents
        assert n <= len(sents)
        word_sent = [word_tokenize(s.lower()) for s in sents]
        self._freq = self._compute_frequencies(word_sent)
        ranking = defaultdict(int)
        for i, sent in enumerate(word_sent):
            for w in sent:
                if w in self._freq:
                    ranking[i] += self._freq[w]
        sents_idx = self._rank(ranking, n)
        logging.debug([sents[j] for j in sents_idx])
        return [sents[j] for j in sents_idx]

    def _rank(self, ranking, n):
        """ return the first n sentences with highest ranking """
        return nlargest(n, ranking, key=ranking.get)
