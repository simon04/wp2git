#!/usr/bin/env python2
from __future__ import print_function

from sys import stderr, stdout
import argparse
import mwclient
import subprocess as sp
import urlparse
import os, locale, time

lang = locale.getdefaultlocale()[0].split('_')[0] or ''

def sanitize(s):
    forbidden = r'?*<>|:\/"'
    for c in forbidden:
        s = s.replace(c, '_')
    return s

def parse_args():
    p = argparse.ArgumentParser(description='Create a git repository with the history of the specified Wikipedia article.')
    p.add_argument('article_name')
    p.add_argument('--no-import', dest='doimport', default=True, action='store_false',
                        help="Don't invoke git fast-import and only generate the fast-import data")
    p.add_argument('-o','--outdir', help='Output directory')
    g=p.add_mutually_exclusive_group()
    g.add_argument('--lang', default=lang, help='Wikipedia language code (default %(default)s)')
    g.add_argument('--site', help='Alternate site (e.g. http://commons.wikimedia.org[/w/])')
    return p, p.parse_args()

def main():
    p, args = parse_args()

    # Connect to site with mwclient
    if args.site is not None:
        scheme, host, path = urlparse.urlparse(args.site, scheme='http')[:3]
        if path=='':
            path = '/w/'
        elif not path.endswith('/'):
            path += '/'
    elif args.lang is not None:
        scheme, host, path = 'http', '%s.wikipedia.org' % args.lang, '/w/'
    else:
        scheme, host, path = 'http', 'wikipedia.org', '/w/'
    site = mwclient.Site((scheme, host), path=path)
    print('Connected to %s://%s%s' % (scheme, host, path), file=stderr)

    # Find the page
    page = site.pages[args.article_name]
    if not page.exists:
        p.error('Page %s does not exist' % s)

    # Create output directory
    fn = sanitize(args.article_name)
    if args.outdir is not None:
        path = args.outdir
    else:
        path = fn

    if os.path.exists(path):
        p.error('Path %s exists' % path)
    os.mkdir(path)
    os.chdir(path)

    # Create fast-import data stream
    with open('fast-import-data', 'wb') as fid:
        fid.write('reset refs/heads/master\n')
        for rev in page.revisions(dir='newer', prop='ids|timestamp|flags|comment|user|content'):
            id = rev['revid']
            text = rev.get('*','').encode('utf8')
            committer = '%s@%s' % (rev['user'].encode('utf8'), site.host[1])
            ts = time.mktime(rev['timestamp'])
            print((" >> Revision %d by %s at %s: %s" % (id, rev['user'], time.ctime(ts), rev['comment'])).encode('ascii','xmlcharrefreplace'), file=stderr)

            summary = '%s\n\nURL: %s://%s%sindex.php?oldid=%d' % (rev['comment'].encode('utf8') or '<blank>', site.host[0], site.host[1], site.path, id)

            fid.write('commit refs/heads/master\n')
            fid.write('committer <%s> %d +0000\n' % (committer, ts))
            fid.write('data %d\n%s\n' % (len(summary), summary))
            fid.write('M 644 inline %s.mw\n' % fn)
            fid.write('data %d\n%s\n' % (len(text), text))
        fid.write('done\n')

    if args.doimport:
        sp.check_call(['git','init','--bare'])
        sp.check_call(['git', 'fast-import','--quiet'], stdin=open(fid.name,"rb"))
        os.unlink('fast-import-data')

if __name__=='__main__':
    main()
