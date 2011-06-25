# (C) Copyright 2008 Georges Racinet
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
# $Id$

from urlparse import urlparse, urljoin

def rewrite_uri(absolute_base='', referer_uri='/index.html', uri='',
                cps_base_url=None, absolute_rewrite=True):
    """Shared URI rewriting logic.


    referer_uri: thinking of the theme as a static site, it would be the
    absolute uri of the current HTTP document within the theme.

    Simplest case
    >>> rewrite_uri(absolute_base='/cps/container/thm', uri='/style.css')
    '/cps/container/thm/style.css'

    Full URLs go through, untouched
    >>> rewrite_uri(absolute_base='/cps/container/thm', uri='http://example.com/style.css')
    'http://example.com/style.css'

    Same for relative URI with authority part (terminology of RFC 2396)
    >>> rewrite_uri(absolute_base='/cps/container/thm', uri='//example.com/style.css')
    '//example.com/style.css'

    Same for anchor in current page
    >>> rewrite_uri(absolute_base='/cps/container/thm', uri='#content')
    '#content'

    Absolute uri, from a lower level
    >>> rewrite_uri(absolute_base='/cont/thm', referer_uri='/styles/main.css',
    ...             uri='/images/x.png')
    '/cont/thm/images/x.png'

    Absolute path uri, with no-rewrite option
    >>> rewrite_uri(absolute_base='/cont/thm', referer_uri='/styles/main.css',
    ...             uri='/images/x.png', absolute_rewrite=False)
    '/images/x.png'

    Relative uri, from a deeper resource
    >>> rewrite_uri(absolute_base='/cont/thm', referer_uri='/graph/main.css',
    ...             uri='x.png')
    '/cont/thm/graph/x.png'

    There is a cps:// url scheme to access content from the cps object
    directly
    >>> rewrite_uri(uri='cps://workspaces/renderCSS.css', cps_base_url='/cps/')
    '/cps/workspaces/renderCSS.css'
    >>> rewrite_uri(uri='cps://workspaces/renderCSS.css', cps_base_url='/')
    '/workspaces/renderCSS.css'
    >>> rewrite_uri(uri='cps://sections/renderCSS.css',
    ...             cps_base_url='/deep/virtual/hosting/')
    '/deep/virtual/hosting/sections/renderCSS.css'

    You can't use that without providing the current CPS base url
    >>> try: rewrite_uri(uri='cps://workspaces/renderCSS.css')
    ... except ValueError: print 'ValueError'
    ValueError
    """

    parsed = urlparse(uri)

    scheme = parsed[0]
    if scheme:
        if scheme != 'cps':
            return uri
        elif cps_base_url is None:
            raise ValueError("Need the CPS base URL to use the cps:// scheme")
        return cps_base_url + uri[6:]

    if parsed[1]: # host and no scheme : absolute URI with same scheme
        return uri

    path = parsed[2]
    if not path: # typically, pure fragment URI (#header)
        return uri

    if path.startswith('/'):
        if absolute_rewrite:
            local_base = ''
        else:
            return uri
    else:
        local_base = referer_uri.rsplit('/', 1)[0] + '/'

    return absolute_base + local_base + uri

def normalize_uri_path(p):
    """Normalize a path URI

    Remove .. and prevents climbing higher than the root
    >>> normalize_uri_path('/a/b/../c')
    '/c'
    >>> normalize_uri_path('/a/b')
    '/a/b'

    special cases
    >>> normalize_uri_path('a/../b')
    '../b'
    >>> normalize_uri_path('/a/../b')
    '/../b'
    """
    # TODO brutal implementation
    split = p.split('/../', 1)
    if len(split) == 1:
        return p
    # normalizes as a side effect, would not work with '' as 2nd arg
    return urljoin(split[0], '../'+split[1])
