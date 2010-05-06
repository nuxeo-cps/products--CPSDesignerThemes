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

import os
import re
import logging

from DateTime.DateTime import DateTime
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
import Acquisition
from OFS.Image import Image, File

from zope.interface import implements
from engine import get_engine_class
from interfaces import IThemeContainer

from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.FSImage import FSImage
from Products.CPSUtil.PropertiesPostProcessor import PropertiesPostProcessor

from engine import get_engine_class
from utils import rewrite_uri
from interfaces import IResourceTraverser

_marker = object()

IMG_EXTENSIONS = ('gif', 'jpg', 'jpeg', 'png', 'bmp')

EngineClass = get_engine_class()

def add_caching_headers(response):
    """Does the same thing as DTML directives in, e.g, default.css

    TODO: use of meta_type and Cache policy manager is better, but
    the file classes below are probably temporary anyway."""
    now = DateTime()

    response.setHeader('Cache-Control',
                       'public, max-age=36000, must-revalidate')
    response.setHeader('Last-Modified', (now - 14).toZone('GMT').rfc822())
    response.setHeader('Expires', (now + 1).toZone('GMT').rfc822())



class OpenImage(Image):
    # Just for proof of concept
    security = ClassSecurityInfo()

    security.declarePublic('index_html')
    def index_html(self, REQUEST, RESPONSE):
        """Rewrap for caching headers"""
        add_caching_headers(RESPONSE)
        res = Image.index_html(self, REQUEST, RESPONSE)
        add_caching_headers(RESPONSE)
        return res


InitializeClass(OpenImage)

class OpenFile(File):
    # Just for proof of concept
    security = ClassSecurityInfo()

    security.declarePublic('index_html')
    def index_html(self, REQUEST, RESPONSE):
        """Rewrap for caching headers"""
        add_caching_headers(RESPONSE)
        res = File.index_html(self, REQUEST, RESPONSE)
        add_caching_headers(RESPONSE)
        return res

InitializeClass(OpenFile)

class StyleSheet(File):
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

    security.declarePublic('index_html')
    def index_html(self, REQUEST, RESPONSE):
        """ugly proof of concept by changing self.data on the fly."""
        raw_data = self.data
        self.data = self.links_re.sub(self.rewriteUrl, self.data)
        res = File.index_html(self, REQUEST, RESPONSE)
        add_caching_headers(RESPONSE)
        self.data = raw_data
        return res

class ResourceTraverser(Acquisition.Explicit):
    """To access resources through traversal.

    TODO explore the idea of replacing this by DirectoryView from CMFCore.
    TODO at least use a more modern traversal style"""

    logger = logging.getLogger('Products.CPSDesignerThemes.themecontainer.ResourceTraverser')
    implements(IResourceTraverser)

    def __init__(self, path, theme_base_uri='/', relative_uri='/',
                 cps_base_url=None, stylesheet_options=None):
        self.path = path
        self.theme_base_uri = theme_base_uri
        self.relative_uri=relative_uri
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
                    stylesheet_options=self.parseOptions(ss_opt)
                else:
                    stylesheet_options=None
                return ResourceTraverser(
                    path,
                    cps_base_url=cps_base_url,
                    theme_base_uri='/'.join((self.getBaseUri(), name)),
                    relative_uri='', stylesheet_options=stylesheet_options)
            # general case
            return ResourceTraverser(path, theme_base_uri=self.theme_base_uri,
                                     cps_base_url=self.cps_base_url,
                                     stylesheet_options=self.stylesheet_options,
                                     relative_uri='/'.join((self.relative_uri,
                                                            name)))
        elif os.path.isfile(path):
            self.logger.debug("Traverser : resource path is %s", path)
            ext = name.rsplit('.', 1)[-1]
            # TODO other types
            if ext in IMG_EXTENSIONS:
                # FSimage roots everything in Products
                # return FSImage(name, path)
                f = open(path, 'rb')
                return OpenImage(name, name, f)
            elif ext == 'css':
                f = open(path, 'r')
                ss = StyleSheet(name, name, f)
                ss.setOptions(self.stylesheet_options)
                ss.setUris(theme_base=self.theme_base_uri,
                           cps_base_url=self.cps_base_url,
                           relative='/'.join((self.relative_uri, name)))
                return ss
            else:
                f = open(path, 'rb')
                return OpenFile(name, name, f)

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

    meta_type="Filesystem Theme Container"

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
        return os.path.join(INSTANCE_HOME, self.relative_path)

    def getBaseUri(self):
        return self.absolute_url_path()

    def computePageFileName(self, page):
        """Compute local FS name from page Name"""

        f = page.rfind('.')
        if f == -1:
            return page + '.html'
        return page

    def getPageEngine(self, theme, page, cps_base_url=None, fallback=False,
                      encoding=None):
        if page is None:
            page = self.default_page
        if theme is None:
            theme = self.default_theme
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
            raise ValueError("Could not find suitables themes and page for"
                              " the required %s and %s" % (theme, page))

        PageEngine = get_engine_class()
        return PageEngine(html_file=page_path,
                          theme_base_uri=self.absolute_url_path() + '/' + theme,
                          page_uri='/' + page_rpath,
                          cps_base_url=cps_base_url,
                          encoding=encoding)

    def invalidate(self, theme, page=None):
        """No cache yet."""
        pass


InitializeClass(FSThemeContainer)
