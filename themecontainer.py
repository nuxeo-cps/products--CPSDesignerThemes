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

import os
import re
import logging
import urlparse

from DateTime.DateTime import DateTime
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
import Acquisition
from OFS.Image import Image, File

from zope.interface import implements
from interfaces import IThemeContainer

from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CPSUtil.http import is_modified_since
from Products.CPSUtil.property import PropertiesPostProcessor

from engine import get_engine_class
from utils import rewrite_uri, normalize_uri_path
from constants import NS_URI
from exceptions import AttackError

from interfaces import IResourceTraverser

_marker = object()

IMG_EXTENSIONS = ('gif', 'jpg', 'jpeg', 'png', 'bmp', 'svg')

HTML_PAGE_REGEXP = re.compile(
    r'<(html|HTML)[^>]*xmlns[^=>]*=[\'"]%s[^>]*>' % NS_URI)

EngineClass = get_engine_class()


def add_caching_headers(response, lastmod=None):
    """Does the same thing as DTML directives in, e.g, default.css

    TODO: use of meta_type and Cache policy manager is better, but
    the file classes below are probably temporary anyway."""
    response.setHeader('Cache-Control',
                       'public, max-age=36000, must-revalidate')
    lastmod = DateTime(lastmod).toZone('GMT').rfc822()
    response.setHeader('Last-Modified', lastmod or DateTime())


class TransientFile(File):
    """Circumvent that _p_mtime is not writable for Persistent objects.

    OFS.Image.File inherits from Persistent, of which ``_p_mtime`` is a
    C-level read-only attribute, but adding a regular (even
    class-level) definition for the attribute gives it back to regular Python.

    Previous ways of doing (setting the Last-Modified header after calling
    OFS.Image.File.index_html() did not work for content that writes directly
    to RESPONSE, which happens if the file has several chunks of data, because
    it'd be too late).
    """

    _p_mtime = 0


class TransientImage(TransientFile, Image):
    """Transient Image"""


class OpenFile(object):
    """Wrapper for Zope File/Image objects limitations

    In any case, these resources should be almost always served at the edge by
    some caching proxy. Hence going through mature (implementing all kinds of
    requests) but very inefficient ``OFS.Image`` objects is acceptable.

    On one hand, ``OFS.Image.File`` is not meant for transient objects (cannot
    set _p_mtime on which If-Modified-Since depends) and will create
    subtransactions even it's not attached to the DB.

    On the other hand, ``zope.app.publisher.fileresource`` requires more
    adapting and is less complete (304 ok, 206 is not).

    Finally, ``Products.CMFCore.FSFile`` supports less kinds of HTTP requests.

    To be rechecked on Zope > 2.10
    """

    base_class = TransientFile

    security = ClassSecurityInfo()

    def __init__(self, name, title, path):
        self.name = name
        self.title = title
        self.path = path

    def construct_obj(self):
        f = open(self.path, 'rb')
        obj = self.base_class(self.name, self.title, f)
        f.close()  # ASAP
        obj._p_mtime = os.path.getmtime(self.path)
        return obj

    security.declarePublic('index_html')

    def index_html(self, REQUEST, RESPONSE):
        """Rewrap for caching headers"""
        # avoid reading the file to build a OFS.Image.File object
        # if content is not stale (OFS.Image.File would issue a 304 but
        # it's way faster to do this right away without having to load the
        # data first in a File object).
        lastmod = os.path.getmtime(self.path)
        # Main caching headers must be supplied in all cases
        add_caching_headers(RESPONSE, lastmod=lastmod)
        if not is_modified_since(REQUEST, lastmod):
            return ''

        return self.construct_obj().index_html(REQUEST, RESPONSE)

InitializeClass(OpenFile)


class OpenImage(OpenFile):
    """Same wrapper as OpenFile, but for OFS.Image.Image objects."""
    base_class = TransientImage

InitializeClass(OpenImage)


class StyleSheet(OpenFile):
    """Special case of style sheets, with URI rewriting."""

    security = ClassSecurityInfo()

    links_re = re.compile(r'url\((.*)\)')

    def rewriteUrl(self, match_obj):
        return 'url(%s)' % rewrite_uri(self.theme_base_uri,
                                       self.relative_uri,
                                       cps_base_url=self.cps_base_url,
                                       absolute_rewrite=self.absolute_rewrite,
                                       uri=match_obj.group(1))

    def setUris(self, theme_base='/', relative='main.css', cps_base_url=None):
        self.relative_uri = relative
        self.theme_base_uri = theme_base
        self.cps_base_url = cps_base_url

    def setOptions(self, options):
        self.options = options
        if options is None:
            options = {}
        self.absolute_rewrite = options.get('uri-absolute-path-rewrite', True)

    def construct_obj(self):
        f = open(self.path, 'r')
        rewritten = self.links_re.sub(self.rewriteUrl, f.read())
        f.close()
        return File(self.name, self.title, rewritten, content_type='text/css')


class ResourceTraverser(Acquisition.Explicit):
    """To access resources through traversal.

    TODO explore the idea of replacing this by DirectoryView from CMFCore.
    TODO at least use a more modern traversal style"""

    logger = logging.getLogger(
        'Products.CPSDesignerThemes.themecontainer.ResourceTraverser')
    implements(IResourceTraverser)

    def __init__(self, path, theme_base_uri='/', relative_uri='/',
                 cps_base_url=None, stylesheet_options=None):
        self.path = path
        self.theme_base_uri = theme_base_uri
        self.relative_uri = relative_uri
        self.cps_base_url = cps_base_url
        self.stylesheet_options = stylesheet_options

    @classmethod
    def isThemeContainer(self):
        return False

    def getFSPath(self):
        return self.path

    def __repr__(self):
        return '<ResourceTraverser at %s>' % self.path

    @classmethod
    def parseOptions(self, xml_file):
        """Parse a options element from xml_file."""
        return EngineClass.parseOptionsFile(xml_file)

    def __getitem__(self, name, default=_marker):
        path = os.path.join(self.getFSPath(), name)
        if os.path.isdir(path):
            # The first traversal from container is the root of theme
            if self.isThemeContainer():
                cps_base_url = getToolByName(self, 'portal_url').getBaseUrl()
                ss_opt = os.path.join(path, 'stylesheet_options.xml')
                if os.path.isfile(ss_opt):
                    stylesheet_options = self.parseOptions(ss_opt)
                else:
                    stylesheet_options = None
                return ResourceTraverser(
                    path,
                    cps_base_url=cps_base_url,
                    theme_base_uri='/'.join((self.getBaseUri(), name)),
                    relative_uri='', stylesheet_options=stylesheet_options)
            # general case
            return ResourceTraverser(
                path, theme_base_uri=self.theme_base_uri,
                cps_base_url=self.cps_base_url,
                stylesheet_options=self.stylesheet_options,
                relative_uri='/'.join((self.relative_uri, name)),
            )
        elif os.path.isfile(path):
            ext = name.rsplit('.', 1)[-1]

            # TODO other types
            if ext in IMG_EXTENSIONS:
                return OpenImage(name, name, path)
            elif ext == 'css':
                ss = StyleSheet(name, name, path)
                ss.setOptions(self.stylesheet_options)
                ss.setUris(theme_base=self.theme_base_uri,
                           cps_base_url=self.cps_base_url,
                           relative='/'.join((self.relative_uri, name)))
                return ss
            else:
                return OpenFile(name, name, path)

        elif default is _marker:
            # ends up normally in 404
            raise KeyError(name)


class FSThemeContainer(PropertiesPostProcessor, SimpleItemWithProperties,
                       ResourceTraverser):
    """A non persistent theme container that using a filesystem directory.

    Themes are simply subdirectories.

    TODO: allow a bit more flexibility than INSTANCE_HOME, remembering that
    any absolute path would be a security hole
    """

    meta_type = "Filesystem Theme Container"

    implements(IThemeContainer)

    _properties = (
        dict(id='title', type='string', mode='w', label='Title'),
        dict(id='relative_path', type='string', mode='w',
             label='Path (relative to INSTANCE_HOME)'),
        dict(id='default_theme', type='string', mode='w',
             label='default theme (directory name)'),
        dict(id='default_page', type='string', mode='w',
             label='default page (file name)'),
        )
    # GR. actually, the default_page should be specified per theme, but
    # that's enough for now.

    default_theme = 'default'
    default_page = 'index'

    _propertiesBaseClass = SimpleItemWithProperties

    relative_path = os.path.join('Products', 'CPSDefault', 'themes')
    title = ''

    manage_options = SimpleItemWithProperties.manage_options + (
        {'label': 'Export',
         'action': 'manage_genericSetupExport.html',
         },
        )

    def __repr__(self):
        return SimpleItemWithProperties.__repr__(self)

    def __init__(self, ob_id, **kw):
        self._setId(ob_id)

    @classmethod
    def isThemeContainer(self):
        return True

    def _postProcessProperties(self):
        if '..' in self.relative_path:
            raise ValueError("'..' is forbidden in the path")

    def getFSPath(self):
        """Override: this persistent class musn't store an absolute path.
        See #2045
        """
        return os.path.join(INSTANCE_HOME, self.relative_path)  # noqa

    def getBaseUri(self):
        return self.absolute_url_path()

    def rewriteXincludeUri(self, uri, referer_uri, absolute_for=''):
        """translate local URIs meant for XInclude in a resolvable way.

        This is because default XInclude processing resolves URIs as paths
        on the file system.
        The default behaviour is meant for lxml (or libxml2 derived libraries):
        local paths are interpreted from the current filesystem file (fine),
        while absolute paths have to be re-rooted from the themes and
        escape from the themes dir must be prevented (security).

        >>> fsthm = FSThemeContainer('cont_id')
        >>> rewrite = fsthm.rewriteXincludeUri
        >>> rewrite('/spam.html', '/master.html')
        'spam.html'
        >>> rewrite('/spam.html', '/fragments/frag1.html')
        '../spam.html'
        >>> try: rewrite('../spam.html', '/master.html')
        ... except ValueError, e: print 'ValueError', e
        ValueError forbidden: ../spam.html from /master.html

        if absolute _for is non empty, the behaviour is quite different. This
        is intended for the default ElementTree resolver: this time, URIs will
        be interpreted from the current working directory (os.getcwd()) and
        have to be translated in an absolute manner and the absolute_for kwarg
        must be the current theme name:

        >>> base_path = fsthm.getFSPath()
        >>> res = rewrite('spam.html', '/master.html', absolute_for='thm1')
        >>> res.startswith(base_path), os.path.split(res[len(base_path)+1:])
        (True, ('thm1', 'spam.html'))
        >>> res = rewrite('/spam.html', '/fragment/one.html',
        ...               absolute_for='thm1')
        >>> res.startswith(base_path), os.path.split(res[len(base_path)+1:])
        (True, ('thm1', 'spam.html'))
        """
        if uri.startswith('//'):
            raise ValueError(uri)

        uri = normalize_uri_path(uri)
        if uri.startswith('/'):
            base_uri = normalize_uri_path(referer_uri).split('/')[:-1]
            steps = len(base_uri)
            if base_uri[0] == '':
                steps -= 1
            res = urlparse.urljoin('../' * steps, uri[1:])
        else:
            res = uri

        resolved = urlparse.urljoin(referer_uri, res)
        if resolved.startswith('..') or resolved.startswith('/..'):
            raise ValueError('forbidden: %s from %s' % (uri, referer_uri))

        # GR this was added afterwards in a lazy way. Implementation should be
        # separate and simpler in that case
        if absolute_for:
            if resolved.startswith('/'):
                resolved = resolved[1:]
            return os.path.join(self.getFSPath(), absolute_for,
                                *(resolved.split('/')))
        return res

    def computePageFileName(self, page):
        """Compute local FS name from page Name"""

        f = page.rfind('.')
        if f == -1:
            return page + '.html'
        return page

    def validateThemeAndPageNames(self, theme, page):
        """Forbid attacks such as use of .. """

        pardir = os.path.pardir
        for s in (theme, page):
            if pardir in s:
                raise AttackError('%r is forbidden '
                                  'in a theme or page name' % pardir)

    def getPageEngine(self, theme, page, cps_base_url=None, fallback=False,
                      encoding=None, lang=''):
        if page is None:
            page = self.default_page
        if theme is None:
            theme = self.default_theme

        self.validateThemeAndPageNames(theme, page)

        alternatives = ((theme, page),
                        (theme, self.default_page),
                        (self.default_theme, self.default_page))

        for t, p in alternatives:
            page_rpath = self.computePageFileName(p)
            page_path = os.path.join(self.getFSPath(), t, page_rpath)

            if os.path.exists(page_path):
                break
            else:
                self.logger.debug(
                    "Tried theme '%s', page '%s', but didn't find  %s",
                    theme, p, page_path)
        else:
            raise ValueError("Could not find suitable themes and page for"
                             " the required %s and %s in %s" % (
                                 theme, page, self.getFSPath()))

        PageEngine = get_engine_class()
        return PageEngine(
            html_file=page_path, container=self,
            theme_base_uri=self.absolute_url_path() + '/' + theme,
            page_uri='/' + page_rpath,
            cps_base_url=cps_base_url,
            encoding=encoding,
            theme_name=t,
            page_name=p,
            lang=lang
        )

    def invalidate(self, theme, page=None):
        """No cache yet."""
        pass

    def listAllThemes(self):
        path = self.getFSPath()
        res = []
        for f in os.listdir(self.getFSPath()):
            if f.startswith('.'):
                continue
            if os.path.isdir(os.path.join(path, f)):
                # could use a richer theme descriptor object
                res.append(
                    (f, dict(id=f,
                             title=f,
                             default=(f == self.default_theme),
                             )))
        res.sort()
        return tuple(d for _, d in res)

    @classmethod
    def isPageFile(self, fpath):
        """Tell whether the file with given path is a theme page.

        TODO: currently, a pure static html page wouldn't pass it"""
        if not os.path.isfile(fpath):
            return False
        # lame, but better for now than trying and parse everything
        fobj = open(fpath)
        extract = fobj.read(1000)
        fobj.close()
        return HTML_PAGE_REGEXP.search(extract) is not None

    def listAllPagesFor(self, theme):
        path = os.path.join(self.getFSPath(), theme)
        default_page = self.computePageFileName(self.default_page)
        return tuple(dict(title=f, id=f, default=(f == default_page))
                     for f in os.listdir(path)
                     if self.isPageFile(os.path.join(path, f)))

InitializeClass(FSThemeContainer)
