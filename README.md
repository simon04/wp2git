wp2git
======

This program allows you to download and convert any Wikipedia article's history to a `git` repository, for easy browsing and blaming.

### Usage

    $ wp2git.py article_name

`wp2git` will create a directory, in which a new bare `git` repository will be created.

Run `wp2git --help` for more options.

### Requirements

`git` should be accessible from `PATH`.

The [`mwclient` package](http://github.com/mwclient/mwclient) must be installed (use `pip install mwclient`).

### Entirely based on

[CyberShadow's version](http://github.com/CyberShadow/wp2git) written in the D language.
