#!/usr/bin/env python3
import os
import magic
import logging
from whoosh import index
from whoosh.fields import Schema, ID, TEXT, STORED, KEYWORD

from pyra.frequency_summarizer import FrequencySummarizer
from pyra.rake_keyword_extractor import RakeKeywordExtractor

logger = logging.getLogger(__name__)


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
        logger.debug("Indexing {0}".format(path))
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
            logger.info('Clearing existing index')
            self.clean_index()
        else:
            logger.info('Incremental index')
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
                        logging.debug("{0} has changed".format(indexed_path))
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
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-q', '--quiet', action='count', default=0)

    args = parser.parse_args()

    logging_level = logging.WARN + 10*args.quiet - 10*args.verbose
    logging.basicConfig(level=logging_level)

    ti = TextIndexer(args.index, args.documents, args.summary)
    ti.index(args.clear)

if __name__ == '__main__':
    main()
