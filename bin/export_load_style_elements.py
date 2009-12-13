#!/usr/bin/env python
# (C) Copyright 2009 Georges Racinet
# Author: Georges Racinet <georges@racinet.fr>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id: __init__.py 53654 2009-06-14 13:18:41Z gracinet $
"""Download static *style* ressources from a hierarchy of html and css files."""

import os
import sys
import re
import urllib
import urlparse
import logging

logger = logging.getLogger('load_style_elements')
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

INSPECTED_EXTS = ('html', 'css',)

URI_REGEXPS = dict(css=re.compile(r'url\((.*?)\)'),
                   html=re.compile(r'@import url\((.*?)\)'))

class Downloader(object):

    def __init__(self, base_url, target_base_path):
        self.target_base_path = target_base_path
        self.base_url = base_url
        urllib.urlcleanup()
        self.initFilesToInspect()

    @classmethod
    def isInspectable(self, filename):
        """Return bool, detected file type"""

        split_filename = filename.rsplit('.', 1)
        if len(split_filename) > 1:
            ext = split_filename[1]
        else:
            ext = None

        if ext in INSPECTED_EXTS:
                return True, ext
        if filename == 'renderCSS': # special case in CPSSkins
            return True, 'css'

        return False, None

    def initFilesToInspect(self):
        """Simple crawler, register files that need to be checked."""
        self.to_inspect = to_inspect = []
        for root, dirs, files in os.walk(self.target_base_path):
            for fname in files:
                todo, ftype = self.isInspectable(fname)
                if todo:
                    to_inspect.append((os.path.join(root, fname), ftype))

    def inspectFile(self, fname, ftype):
        """Return the list of needed resources for that stylesheet file.

        Resources are the URIs found in the file
        """
        logger.info("Starting to inspect %s", fname)
        fd = open(fname, 'r')
        res = []
        regexp = URI_REGEXPS[ftype]
        # GR, ok in principle there could be problems if we started from
        # FS root...
        referer = fname[len(self.target_base_path)+1:]
        referer = urllib.pathname2url(referer)

        base_url = self.base_url
        base_url_len = len(base_url)
        
        for line in fd.readlines():
            for uri in regexp.findall(line):
                uri = uri.strip(' \t"')
                if uri.startswith(base_url):
                    uri = uri[base_url_len:]
                logger.debug("(Referer=%s) found URI to check or retrieve: %s",
                             referer, uri)
                self.downloadFile(uri, referer_path=referer)
        fd.close()

    def inspectAll(self):
        i = 0
        while i < len(self.to_inspect): # can grow in the process
            self.inspectFile(*self.to_inspect[i])
            i += 1

    def downloadFile(self, uri, referer_path=None):
        """referer_path has to start with '/'"""

        pr = urlparse.urlparse(uri)
        if pr.scheme:
            logger.info("No download for external URI %s", uri)
            return

        path = pr.path
        if path.startswith('/'):
            url = self.base_url + path
            target_parts = [self.target_base_path]
            target_parts.extend(path[1:].split('/'))
        else:
            if referer_path is None:
                raise RuntimeError("Called for a local URI, with no referer")

            parts = referer_path.split('/')[:-1]
            parts += path.split('/')
            url_parts = [self.base_url]
            url_parts.extend(parts)
            url = '/'.join(url_parts)

            target_parts = [self.target_base_path]
            target_parts.extend(parts)

        target = os.path.join(*target_parts)
        logger.debug("URI %s resolves as %s, to save at %s", uri, url, target)

        # now ensuring existence of target directory
        target_dir = ''
        for part in target_parts[:-1]:
            target_dir = os.path.join(target_dir, part)
            if not os.path.isdir(target_dir):
                os.mkdir(target_dir)

        # if necessary, add the file
        urllib.urlretrieve(url, target)
        logger.info("Retrieved %s -> %s", url, target)

        to_inspect, ftype = self.isInspectable(target_parts[-1])
        if to_inspect:
            self.to_inspect.append((target, ftype))

def main(argv):
    if len(argv) != 2:
        logger.fatal("Usage: %s <BASE_URL>", argv[0])
        sys.exit(1)
    base_url = argv[1]
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    dl = Downloader(base_url, os.getcwd())
    dl.inspectAll()

    #dl.downloadFile('/cps/cpsskins_common-css2.css', 'index.html')



if __name__ == '__main__':
    main(sys.argv)
