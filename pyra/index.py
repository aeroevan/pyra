#!/usr/bin/env python3
import os
from whoosh import index
from whoosh.fields import Schema, ID, TEXT, STORED, KEYWORD
import magic
import nltk
import string
import operator
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from collections import defaultdict
from string import punctuation
from heapq import nlargest


class FrequencySummarizer(object):
    def __init__(self, min_cut=0.1, max_cut=0.9):
        """
         Initilize the text summarizer.
         Words that have a frequency term lower than min_cut
         or higer than max_cut will be ignored.
        """
        self._min_cut = min_cut
        self._max_cut = max_cut
        self._stopwords = set(stopwords.words('english') + list(punctuation))

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
        for w in freq.keys():
            freq[w] = freq[w]/m
            if freq[w] >= self._max_cut or freq[w] <= self._min_cut:
                del freq[w]
        return freq

    def summarize(self, text, n):
        """
            Return a list of n sentences
            which represent the summary of text.
        """
        sents = sent_tokenize(text)
        if (len(sents) < n):
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
        return [sents[j] for j in sents_idx]

    def _rank(self, ranking, n):
        """ return the first n sentences with highest ranking """
        return nlargest(n, ranking, key=ranking.get)


def isPunct(word):
    return len(word) == 1 and word in string.punctuation


def isNumeric(word):
    try:
        float(word) if '.' in word else int(word)
        return True
    except ValueError:
        return False


class RakeKeywordExtractor(object):
    def __init__(self):
        self.stopwords = set(nltk.corpus.stopwords.words())
        self.top_fraction = 1  # consider top third candidate keywords by score

    def _generate_candidate_keywords(self, sentences):
        phrase_list = []
        for sentence in sentences:
            words = map(lambda x: "|" if x in self.stopwords else x,
                        nltk.word_tokenize(sentence.lower()))
            phrase = []
            for word in words:
                if word == "|" or isPunct(word):
                    if len(phrase) > 0:
                        phrase_list.append(phrase)
                        phrase = []
                else:
                    phrase.append(word)
        return phrase_list

    def _calculate_word_scores(self, phrase_list):
        word_freq = nltk.FreqDist()
        word_degree = nltk.FreqDist()
        for phrase in phrase_list:
            degree = len(list(filter(lambda x: not isNumeric(x), phrase))) - 1
            for word in phrase:
                word_freq[word] += 1
                word_degree[word] += degree  # other words
        for word in word_freq.keys():
            word_degree[word] = word_degree[word] + word_freq[word]  # itself
        # word score = deg(w) / freq(w)
        word_scores = {}
        for word in word_freq.keys():
            word_scores[word] = word_degree[word] / word_freq[word]
        return word_scores

    def _calculate_phrase_scores(self, phrase_list, word_scores):
        phrase_scores = {}
        for phrase in phrase_list:
            phrase_score = 0
            for word in phrase:
                phrase_score += word_scores[word]
            phrase_scores[" ".join(phrase)] = phrase_score
        return phrase_scores

    def extract(self, text, incl_scores=False):
        sentences = nltk.sent_tokenize(text)
        phrase_list = self._generate_candidate_keywords(sentences)
        word_scores = self._calculate_word_scores(phrase_list)
        phrase_scores = self._calculate_phrase_scores(
            phrase_list, word_scores)
        sorted_phrase_scores = sorted(phrase_scores.items(),
                                      key=operator.itemgetter(1), reverse=True)
        n_phrases = len(sorted_phrase_scores)
        if incl_scores:
            return sorted_phrase_scores[0:int(n_phrases/self.top_fraction)]
        else:
            return map(lambda x: x[0],
                       sorted_phrase_scores[0:int(n_phrases/self.top_fraction)])


class TextIndexer(object):
    def __init__(self, index_location, base_path, summary_size):
        self._fs = FrequencySummarizer()
        self._rake = RakeKeywordExtractor()
        self._index_location = index_location
        self._base_path = base_path
        self._summary_size = summary_size

    def _my_docs(self):
        for root, dirnames, filenames in os.walk(self._base_path):
            for filename in filenames:
                fullpath = os.path.join(root, filename)
                if magic.from_file(fullpath, mime=True) == b'text/plain':
                    yield fullpath

    def _add_doc(self, writer, path):
        fileobj = open(path, "rt")
        content = fileobj.read()
        summary = "\n".join(self._fs.summarize(content, self._summary_size))
        keywords = ','.join(self._rake.extract(content))
        fileobj.close()
        modtime = os.path.getmtime(path)
        writer.add_document(path=path, time=modtime, keywords=keywords,
                            summary=summary, content=content)

    def _get_schema(self):
        return Schema(path=ID(unique=True, stored=True),
                      time=STORED,
                      keywords=KEYWORD(lowercase=True, commas=True,
                                       stored=True),
                      summary=TEXT(stored=True),
                      content=TEXT)

    def clean_index(self):
        # Always create the index from scratch
        ix = index.create_in(self._index_location,
                             schema=self._get_schema())
        writer = ix.writer()

        # Assume we have a function that gathers the filenames of the
        # documents to be indexed
        for path in self._my_docs():
            self._add_doc(writer, path)

        writer.commit()

    def index(self, clean=False):
        if clean:
            self.clean_index()
        else:
            self.incremental_index()

    def incremental_index(self):
        ix = index.open_dir(self._index_location)

        # The set of all paths in the index
        indexed_paths = set()
        # The set of all paths we need to re-index
        to_index = set()

        with ix.searcher() as searcher:
            writer = ix.writer()

            # Loop over the stored fields in the index
            for fields in searcher.all_stored_fields():
                indexed_path = fields['path']
                indexed_paths.add(indexed_path)

                if not os.path.exists(indexed_path):
                    # This file was deleted since it was indexed
                    writer.delete_by_term('path', indexed_path)

                else:
                    # Check if this file was changed since it
                    # was indexed
                    indexed_time = fields['time']
                    mtime = os.path.getmtime(indexed_path)
                    if mtime > indexed_time:
                        # The file has changed, delete it and add it to the list
                        # of files to reindex
                        writer.delete_by_term('path', indexed_path)
                        to_index.add(indexed_path)

            # Loop over the files in the filesystem
            # Assume we have a function that gathers the filenames of the
            # documents to be indexed
            for path in self._my_docs():
                if path in to_index or path not in indexed_paths:
                    # This is either a file that's changed, or a new file
                    # that wasn't indexed before. So index it!
                    self._add_doc(writer, path)

            writer.commit()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        'pyra-index', description='Whoosh text indexer',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-i', '--index', help='Index database location',
        default=os.path.expanduser('~/.local/share/pyra-index'))
    parser.add_argument(
        '-d', '--documents', help='Folder of text documents to index',
        default=os.path.expanduser('~/ownCloud/Documents'))
    parser.add_argument(
        '-s', '--summary', help='Number of summary sentences',
        default=3, type=int)
    parser.add_argument('-c', '--clear',
                        help='Clear and reindex',
                        action='store_true')
    args = parser.parse_args()
    ti = TextIndexer(args.index, args.documents, args.summary)
    ti.index(args.clear)

if __name__ == '__main__':
    main()
