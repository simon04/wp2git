#!/usr/bin/env python3
"""Downloads and imports Wikipedia page histories to a git repository"""

from __future__ import unicode_literals
from sys import stderr, stdout, platform
import argparse
import mwclient
import subprocess as sp
import os
import locale
import time
from six import print_
from six.moves import urllib


def sanitize_filename(string):
    """Sanitizes string in order to be used as filename.

    >>> sanitize_filename('foobar')
    'foobar'
    >>> sanitize_filename('foo/*bar:baz')
    'foo__bar_baz'
    """
    forbidden = r'?*<>|:\/"'
    for char in forbidden:
        string = string.replace(char, '_')
    return string


def parse_args():
    """Parses the command line arguments."""
    p = argparse.ArgumentParser(
        description='Create a git repository with the history of the specified Wikipedia article.')
    p.add_argument('article_name')

    output = p.add_argument_group('Output options')
    g = output.add_mutually_exclusive_group()
    g.add_argument('-n', '--no-import', dest='doimport', default=True, action='store_false',
                   help='Don\'t invoke git fast-import; only generate fast-import data stream')
    g.add_argument('-b', '--bare', action='store_true',
                   help='Import to a bare repository (no working tree)')
    output.add_argument('-o', '--out',
                        help='Output directory or fast-import stream file')

    site = p.add_argument_group('MediaWiki site selection')
    g = site.add_mutually_exclusive_group()
    g.add_argument('--lang', default=locale.getdefaultlocale()[0].split('_')[0] or '',
                   help='Wikipedia language code (default %(default)s)')
    g.add_argument('--site',
                   help='Alternate MediaWiki site (e.g. https://commons.wikimedia.org[/w/])')

    revision = p.add_argument_group('Revision options')
    revision.add_argument('--expandtemplates', action='store_true', help='Expand templates')
    revision.add_argument('--start', help='ISO8601 timestamp to start listing from')
    revision.add_argument('--end', help='ISO8601 timestamp to end listing at')
    revision.add_argument('--user', help='Only list revisions made by this user')
    revision.add_argument('--excludeuser', help='Exclude revisions made by this user')

    args = p.parse_args()
    if not args.doimport:
        if args.out is None:
            # https://stackoverflow.com/a/2374507/20789
            if platform == 'win32':
                import msvcrt
                msvcrt.setmode(stdout.fileno(), os.O_BINARY)
            try:
                args.out = stdout.buffer
            except AttributeError:
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
        scheme, host, path = urllib.urlparse(args.site, scheme='https')[:3]
        if path == '':
            path = '/w/'
        elif not path.endswith('/'):
            path += '/'
    elif args.lang is not None:
        scheme, host, path = 'https', '%s.wikipedia.org' % args.lang, '/w/'
    else:
        scheme, host, path = 'https', 'wikipedia.org', '/w/'
    site = mwclient.Site((scheme, host), path=path)
    print_('Connected to %s://%s%s' % (scheme, host, path), file=stderr)

    # Find the page
    page = site.pages[args.article_name]
    if not page.exists:
        p.error('Page %s does not exist' % args.article_name)
    fn = sanitize_filename(args.article_name)

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
            sp.check_call(['git', 'init'] + (['--bare'] if args.bare else []))
            pipe = sp.Popen(['git', 'fast-import', '--quiet', '--done'], stdin=sp.PIPE)
            fid = pipe.stdin
    else:
        fid = args.out

    # Output fast-import data stream to file or git pipe
    with fid:
        def utf8len(s):
            return len(s.encode('utf-8'))
        def write_bytes_of_string(*args):
            for s in args:
                fid.write(s.encode('utf-8'))
        write_bytes_of_string('reset refs/heads/master\n')
        prop = 'ids|timestamp|flags|comment|user|userid|content|tags'
        for rev in page.revisions(dir='newer', prop=prop, expandtemplates=args.expandtemplates,
                                  start=args.start, end=args.end,
                                  user=args.user, excludeuser=args.excludeuser):
            id = rev['revid']
            text = rev.get('*', '')
            user = rev.get('user', '')
            user_ = user.replace(' ', '_')
            comment = rev.get('comment', '') or '<blank>'
            tags = (['minor'] if 'minor' in rev else []) + rev['tags']
            ts = time.mktime(rev['timestamp'])

            if 'userid' in rev and rev['userid']:
                committer = '%s <%s@%s>' % (user, user_, host)
            else:
                committer = '%s <>' % user

            msg = ' >> {minor}Revision {id} by {user} at {time}: {comment}'.format(
                minor='Minor ' if 'minor' in rev else '',
                id=id, user=user, time=ts, comment=comment)
            print_(msg, file=stderr)

            summary = '\n'.join([
                '{comment}',
                '',
                'URL: {scheme}://{host}{path}index.php?oldid={id:d}',
                'Editor: {scheme}://{host}{path}index.php?title=User:{user_}'
            ]).format(comment=comment, scheme=scheme, host=host, path=path, id=id, user_=user_)

            if tags:
                summary += '\nTags: ' + ', '.join(tags)

            write_bytes_of_string('commit refs/heads/master\n')
            write_bytes_of_string('committer %s %d +0000\n' % (committer, ts))
            write_bytes_of_string('data %d\n%s\n' % (utf8len(summary), summary))
            write_bytes_of_string('M 644 inline %s.mw\n' % fn)
            write_bytes_of_string('data %d\n%s\n' % (utf8len(text), text))
        write_bytes_of_string('done\n')

    if args.doimport:
        pipe.communicate()
        if not args.bare:
            sp.check_call(['git', 'checkout'])

if __name__ == '__main__':
    main()
