#!/usr/bin/env python3

from sys import stderr, stdout, platform
import argparse
import mwclient
import subprocess as sp
import urllib.parse
import os
import locale
import time

lang = locale.getdefaultlocale()[0].split('_')[0] or ''


def sanitize(s):
    forbidden = r'?*<>|:\/"'
    for c in forbidden:
        s = s.replace(c, '_')
    return s


def parse_args():
    p = argparse.ArgumentParser(
        description='Create a git repository with the history of the specified Wikipedia article.')
    p.add_argument('article_name')
    g2 = p.add_argument_group('Output options')
    g = g2.add_mutually_exclusive_group()
    g.add_argument('-n', '--no-import', dest='doimport', default=True, action='store_false',
                   help='Don\'t invoke git fast-import; only generate fast-import data stream')
    g.add_argument('-b', '--bare', action='store_true',
                   help='Import to a bare repository (no working tree)')
    g2.add_argument('-o', '--out',
                    help='Output directory or fast-import stream file')
    g2 = p.add_argument_group('MediaWiki site selection')
    g = g2.add_mutually_exclusive_group()
    g.add_argument('--lang', default=lang,
                   help='Wikipedia language code (default %(default)s)')
    g.add_argument(
        '--site', help='Alternate MediaWiki site (e.g. http://commons.wikimedia.org[/w/])')

    args = p.parse_args()
    if not args.doimport:
        if args.out is None:
            # http://stackoverflow.com/a/2374507/20789
            if platform == 'win32':
                import os
                import msvcrt
                msvcrt.setmode(stdout.fileno(), os.O_BINARY)
            args.out = stdout.buffer
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
        scheme, host, path = urllib.parse.urlparse(args.site, scheme='http')[:3]
        if path == '':
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
        p.error('Page %s does not exist' % args.article_name)
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
            sp.check_call(['git', 'init'] + (['--bare'] if args.bare else []))
            pipe = sp.Popen(['git', 'fast-import', '--quiet', '--done'], stdin=sp.PIPE)
            fid = pipe.stdin
    else:
        fid = args.out

    # Output fast-import data stream to file or git pipe
    with fid:
        def write_bytes_of_string(s):
            fid.write(s.encode())
        write_bytes_of_string('reset refs/heads/master\n')
        prop = 'ids|timestamp|flags|comment|user|userid|content|tags'
        for rev in page.revisions(dir='newer', prop=prop):
            id = rev['revid']
            text = rev.get('*', '')
            user = rev.get('user', '')
            user_ = user.replace(' ', '_')
            comment = rev.get('comment', '') or '<blank>'
            tags = (['minor'] if 'minor' in rev else []) + rev['tags']
            ts = time.mktime(rev['timestamp'])

            if rev['userid']:
                committer = '%s <%s@%s>' % (user, user_, host)
            else:
                committer = '%s <>' % user

            msg = ' >> {minor}Revision {id} by {user} at {time}: {comment}'.format(
                minor='Minor ' if 'minor' in rev else '',
                id=id, user=user, time=ts, comment=comment)
            print(msg, file=stderr)

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
            write_bytes_of_string('data %d\n%s\n' % (len(summary.encode()), summary))
            write_bytes_of_string('M 644 inline %s.mw\n' % fn)
            write_bytes_of_string('data %d\n%s\n' % (len(text.encode()), text))
        write_bytes_of_string('done\n')

    if args.doimport:
        pipe.communicate()
        if not args.bare:
            sp.check_call(['git', 'checkout'])

if __name__ == '__main__':
    main()
