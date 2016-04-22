wp2git
======

This program allows you to download and convert any Wikipedia article's history to a `git` repository, for easy browsing and blaming.

### Usage

    $ wp2git.py [--bare] article_name

`wp2git` will create a directory, in which a new `git` repository will be created.
The repository will contain a single file named `article_name.mw`, along with its entire edit history.

Run `wp2git --help` for more options.

### Analyzing using git
* Who last changed this line? `git blame article_name.mw`
* Who introduced this sentence? `git log -p -G "the natural number that succeeds 41"`

### Requirements
* [Python](https://www.python.org/) 2 or 3
* [`git`](https://git-scm.com/) accessible from `PATH`.
* [`mwclient`](http://github.com/mwclient/mwclient) (use `pip install mwclient`).

### Credits
1. [CyberShadow's version](http://github.com/CyberShadow/wp2git) written in the D language.
2. [dlenski's version](http://github.com/CyberShadow/wp2git) written for Python 2 only.
