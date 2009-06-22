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

def rewrite_uri(absolute_base='', referer_uri='/index.html', uri='',
                cps_base_url=None):
    """Shared URI rewriting logic.


    referer_uri: thinking of the theme as a static site, it would be the
    absolute uri of the current HTTP document within the theme.

    Simplest case
    >>> rewrite_uri(absolute_base='/cps/container/thm', uri='/style.css')
    '/cps/container/thm/style.css'

    Full URLs go through, untouched
    >>> rewrite_uri(absolute_base='/cps/container/thm', uri='http://example.com/style.css')
    'http://example.com/style.css'

    Absolute uri, from a lower level
    >>> rewrite_uri(absolute_base='/cont/thm', referer_uri='/styles/main.css',
    ...             uri='/images/x.png')
    '/cont/thm/images/x.png'

    Relative uri, from a deeper resource
    >>> rewrite_uri(absolute_base='/cont/thm', referer_uri='/graph/main.css',
    ...             uri='x.png')
    '/cont/thm/graph/x.png'

    There is a cps:// url scheme to access content from the cps object
    directly
    >>> rewrite_uri(uri='cps://workspaces/renderCSS.css', cps_base_url='/cps')
    '/cps/workspaces/renderCSS.css'
    >>> rewrite_uri(uri='cps://workspaces/renderCSS.css', cps_base_url='/')
    '/workspaces/renderCSS.css'
    >>> rewrite_uri(uri='cps://sections/renderCSS.css',
    ...             cps_base_url='/deep/virtual/hosting')
    '/deep/virtual/hosting/sections/renderCSS.css'

    You can't use that without providing the current CPS base url
    >>> try: rewrite_uri(uri='cps://workspaces/renderCSS.css')
    ... except ValueError: print 'ValueError'
    ValueError
    """
    # TODO refactor using standard lib

    if uri.startswith('http://'):
        return uri
    if uri.startswith('cps://'):
        if cps_base_url is None:
            raise ValueError("Need the CPS base URL to use the cps:// scheme")
        if cps_base_url == '/':
            return '/' + uri[6:]
        return cps_base_url + '/' + uri[6:]
    if uri.startswith('/'):
        local_base = ''
    else:
        local_base = referer_uri.rsplit('/', 1)[0] + '/'

    return absolute_base + local_base + uri
