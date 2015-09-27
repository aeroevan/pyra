#!/usr/bin/env python3
import os
from whoosh.index import open_dir
from whoosh.qparser import QueryParser


def run(args):
    ix = open_dir(args.index)
    with ix.searcher() as searcher:
        if args.content:
            parser = QueryParser("content", ix.schema)
        elif args.summary:
            parser = QueryParser("summary", ix.schema)
        elif args.keywords:
            parser = QueryParser("keywords", ix.schema)
        else:
            raise Exception('Need a field to search')
        query = parser.parse(args.query)
        results = searcher.search(query)
        for result in results:
            print(result)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        'pyra-index', description='Whoosh text searcher',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-i', '--index', help='Index database location',
        default=os.path.expanduser('~/.local/share/pyra-index'))
    parser.add_argument('-c', '--content', help='Search content',
                        action='store_true')
    parser.add_argument('-s', '--summary', help='Search summary',
                        action='store_true')
    parser.add_argument('-k', '--keywords', help='Search keywords',
                        action='store_true', default=True)
    parser.add_argument('-q', '--query', help='query string', required=True)
    args = parser.parse_args()
    run(args)

if __name__ == '__main__':
    main()
