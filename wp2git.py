#!/usr/bin/env python2
from __future__ import print_function

from sys import stderr, stdout, platform
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
    p.add_argument('-n', '--no-import', dest='doimport', default=True, action='store_false',
                   help="Don't invoke git fast-import; only generate fast-import data stream")
    p.add_argument('-o', '--out', help='Output directory or fast-import stream file')
    g=p.add_mutually_exclusive_group()
    g.add_argument('--lang', default=lang, help='Wikipedia language code (default %(default)s)')
    g.add_argument('--site', help='Alternate site (e.g. http://commons.wikimedia.org[/w/])')

    args = p.parse_args()
    if not args.doimport:
        if args.out is None:
            # http://stackoverflow.com/a/2374507/20789
            if platform == "win32":
                import os, msvcrt
                msvcrt.setmode(stdout.fileno(), os.O_BINARY)
            args.out = stdout
        else:
            try:
                args.out = argparse.FileType('wb')(args.out)
            except argparse.ArgumentTypeError as e:
                p.error(e.args[0])

    return p, args

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
    fn = sanitize(args.article_name)

    if args.doimport:
        # Create output directory and pipe to git
        if args.out is not None:
            path = args.out
        else:
            path = fn

        if os.path.exists(path):
            p.error('path %s exists' % path)
        else:
            os.mkdir(path)
            os.chdir(path)
            sp.check_call(['git','init','--bare'])
            pipe = sp.Popen(['git', 'fast-import','--quiet','--done'], stdin=sp.PIPE)
            fid = pipe.stdin
    else:
        fid = args.out

    # Output fast-import data stream to file or git pipe
    with fid:
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
        pipe.communicate()

if __name__=='__main__':
    main()
