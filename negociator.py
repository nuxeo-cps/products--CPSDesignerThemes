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
import logging
import types
import warnings

from zope.interface import implements
from zope.component import adapts
from zope.component import getMultiAdapter
from zope.app.publisher.browser import BrowserView

from Globals import InitializeClass
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import ModuleSecurityInfo
from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import getToolByName
from Products.CPSUtil.text import get_final_encoding

from themecontainer import FSThemeContainer

from OFS.interfaces import IObjectManager
from zope.publisher.interfaces.http import IHTTPRequest
from interfaces import IThemeEngine

security = ModuleSecurityInfo('Products.CPSDesignerThemes.negociator')

logger = logging.getLogger('CPSDesignerThemes.negociator')

_default = object()

CPSSKINS_THEME_COOKIE_ID = 'cpsskins_theme'
CPSDESIGNER_THEME_COOKIE_ID = 'cpsdesigner_theme'
CPSSKINS_LOCAL_THEME_ID = '.cpsskins_theme'
CPSDESIGNER_LOCAL_THEME_ID = '.cps_themes_bindings'

security.declarePublic('adapt')
def adapt(context, request):
    """Bootstrap the adapter request.

    Main interest is to use from restricted code, including TALES expressions
    from non Zope3 style UI parts.

    XXX maybe restore some flexibility by using an optionally named adapter.
    """
    return getMultiAdapter((context, request), IThemeEngine)

class EngineAdapter(object):
    """Some boiler plate logic."""

    adapts(IObjectManager, IHTTPRequest)
    implements(IThemeEngine)

    security = ClassSecurityInfo()

    def __init__(self, context, request):
        # GR don't want to import a constant from CPSDefault here
        self.void = void = getattr(request, '_cps_void_response', _default)
        if void is _default:
            logger.warn("Didn't find marker in request. Void responses "
                        "(302, 304...) quick handling might be broken.")
            void = False

        if isinstance(context, BrowserView): # see #2400
            self.context = context.context
        else:
            self.context = context
        self.request = request
        self.engine = None

        # portal-related stuff
        utool = getToolByName(context, 'portal_url')
        self.cps_base_url = utool.getBaseUrl()
        enc = utool.getPortalObject().default_charset
        if enc == 'unicode':
            # XXX maybe better to introspect zpublisher conf
            # TODO CPSUtil can do that now
            enc = 'utf-8'
        self.encoding = enc

    def getThemeAndPageName(self, editing=False):
        """Return the theme and page that should be rendered.
        Both can be None, meaning that some downstream (container) defaults
        may still apply.

        To be implemented by subclasses."""
        raise NotImplementedError

    security.declarePublic('getStyleSheetUris')
    def getStyleSheetUris(self, **kw):
        return self.getEngine().getStyleSheetUris(**kw)

    def getEngine(self, editing=False):
        """The fallback is up to the container."""
        engine = self.engine
        if engine is not None:
            return engine

        theme, page = self.getThemeAndPageName(editing=editing)

        logger.debug("Requested theme: %r page: %r", theme, page)
        engine = self.engine = self.lookupContainer().getPageEngine(
            theme, page, cps_base_url=self.cps_base_url, fallback=True,
            encoding=self.encoding)
        return engine

    def renderCompat(self, **kw):
        if self.void: # return asap for efficiency (see #2040)
            return ''
        return self.getEngine().renderCompat(context=self.context,
                                             request=self.request, **kw)

    security.declarePublic('effectiveThemeAndPageNames')
    def effectiveThemeAndPageNames(self, editing=False):
        """Return the effective theme and page names"""
        engine = self.getEngine(editing=editing)
        return (engine.theme_name, engine.page_name)

    security.declarePublic('listSlots')
    def listSlots(self):
        """Return the list of all slots known to this engine.
        TODO : still has the side effects of engine's extractSlotElements.
        """
        return [x[0] for x in self.getEngine().extractSlotElements()]

    security.declarePublic('listHiddenSlots')
    def listHiddenSlots(self):
        """List all existing portlet slots that are not used by this engine."""
        ptltool = getToolByName(self.context, 'portal_cpsportlets')
        engine_slots = self.listSlots()
        return [slot for slot in ptltool.listPortletSlots()
                if slot not in engine_slots]

    security.declarePublic('listAllThemes')
    def listAllThemes(self):
        """List all available themes in the same context.

        This includes the resolved theme."""
        return self.lookupContainer().listAllThemes()

    security.declarePublic('listThemePages')
    def listThemePages(self, editing=False):
        """List all available theme pages for negotiated theme."""
        engine = self.getEngine(editing=editing)
        return self.lookupContainer().listAllPagesFor(engine.theme_name)

InitializeClass(EngineAdapter)

class RootContainerFinder:
    """This class uses the first container found at root."""

    def lookupContainer(self):
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        containers = portal.objectValues(['Filesystem Theme Container',
                                          'Theme Container'])
        if not containers:
            raise KeyError('No theme container found')
        return containers[0]

class FixedFSThemeEngine(RootContainerFinder, EngineAdapter):
    """For unit tests only"""

    def getEngine(self):
        """XXX this method is never called and would not work. Leftover ?"""
        theme, page = self.getRequestedThemeAndPageName()
        return self.lookupContainer().getPageEngine(
            'default', 'index', cps_base_url=self.cps_base_url, fallback=True)

class CPSSkinsThemeNegociator(RootContainerFinder, EngineAdapter):
    """Negociator with same rules as CPSSkins with a root container.
    """

    def getThemeAndPageName(self, **kw):
        """Gets the name of the requested theme and page by checking a series
           of URL parameters, variables, folder attributes, cookies, ...

           If no_defaults is True, don't lookup the default theme, return
           None, None for further treatment instead (used by CPSDesignerThemes)
        """

        REQUEST = self.request
        FORM = REQUEST.form
        # selected by writing ?pp=1 in the URL
        if FORM.get('pp') == '1':
            return 'printable', None

        # selected by writing ?theme=... in the URL
        # (+page)
        theme = FORM.get('theme')
        page = FORM.get('page')
        if (theme is not None) or (page is not None):
            return self._extractThemeAndPageName(theme, page)

        if int(kw.get('editing', 0)) == 1:
            # session variable (used in edition mode)
            cpsskins = getToolByName(self.context, 'portal_themes')
            view_mode = cpsskins.getViewMode()
            theme = view_mode.get('theme')
            page = view_mode.get('page')
            if (theme is not None) or (page is not None):
                return self._extractThemeAndPageName(theme, page)

        # cookie (theme + page)
        theme = self.getThemeCookie()
        if theme is not None:
            return self._extractThemeAndPageName(theme, None)

        # local and method themes (theme + page)
        theme = self.getLocalThemeName()
        if theme is not None:
            return self._extractThemeAndPageName(theme, None)

        # nothing requested, it's up to downstream code to handle that
        return None, None

    @classmethod
    def _extractThemeAndPageName(self, theme=None, page=None):
        """Extract the theme and page from the short notation
        """
        theme_id = theme
        page_id = page
        if theme and '+' in theme:
            theme_id, page_id = theme.split('+')
        return theme_id, page_id

    def getThemeCookie(self):
        """Read a theme from cookies. Return None if none found"""
        cookies = self.request.cookies
        theme = cookies.get(CPSDESIGNER_THEME_COOKIE_ID)
        if theme is None:
            theme = cookies.get(CPSSKINS_THEME_COOKIE_ID)
        return theme

    def getRequestPublished(self):
        # borrowed from CPSPortlets
        published_obj = self.request.get('PUBLISHED')
        if published_obj is None:
            return
        try:
            if isinstance(published_obj, types.MethodType):
                # z3 view?
                if published_obj.im_func.func_name == 'view_html':
                    # Convention for default view method name
                    # XXX Could check request['URL'] too
                    ob = request['PARENTS'][1]
                    return ob.getTypeInfo().queryMethodID('view', '')
            else:
                return published_obj.getId()
        except AttributeError:
            pass

    #
    # Local theme bindings resolution
    #

    @classmethod
    def bottomMostFolder(self, startobj):
        """Find the bottom-most-folder above startobj.

        Adapted from CPSSkins themes tool.
        """
        obj = startobj

        while 1:
            if obj.isPrincipiaFolderish and not obj.getId().startswith('.'):
                return obj
            parent = aq_parent(aq_inner(obj))
            if obj is None or parent == obj:
                return startobj
            obj = parent

    def getLocalThemeName(self, **kw):
        """Return the name of a local theme in a given context.

           Adapted from CPSSkins themes tool

           Local themes are obtained from folder attributes, i.e.
           - as the property of a folder (one theme per line)
           - as an object located in the folder that is callable and
             that returns a tuple.

           Local themes are computed by collecting all theme information
           from the portal to the context folder.

           The format for describing themes is:
           - simply a string containing the theme id.

           - 'n-m:theme'

           - 'method:n-m:theme'

           where:
           - 'theme' is the theme id
           - (n, m) is a couple with n <= m that describes the interval
             inside which the theme will be used, m=0 being an exception.
             (0, 0) means the current folder and all subfolders
             (1, 0) means all subfolders below the current folder
             (1, 1) means the subfolders of level 1
             (0, 1) means the folder and the subfolders of level 1
             (n, n) means the subfolders of level n
             ...
           - method is the id of the method called by zope publisher

           Examples:
           * with a folder property called '.cpsdesigner_theme' or (BBB)
           '.cpsskins_theme':

             - lines with intervals:

               0-1:theme1
               2-4:theme2
               6-0:theme3

             - string with interval:

               0-1:theme1

             - string without interval:

               theme1

             - fully specified with method:
               folder_view:0-0:theme1

           * with a script called '.cpsdesigner_theme.py' or (BBB)
           '.cpsskins_theme.py' placed in a folder:

             - tuple with intervals:

               return ('0-1:theme1', '2-4:theme2', '6-0:theme3')

             - string with interval:

               return '0-1:theme'

             - string without interval:

               return 'theme'

        """

        context = self.context
        bmf = self.bottomMostFolder(context)

        # get themes from the root to current path
        utool = getToolByName(self.context, 'portal_url')
        portal = utool.getPortalObject()
        level = len(utool.getRelativeContentPath(bmf))

        ob = bmf
        objs = [ob]
        while True:
            # move to the parent
            ob = aq_parent(aq_inner(ob))
            if ob is None:
                break
            objs.append(ob)
            if ob is portal:
                break

        # we revert the list since we want to start from the portal and move
        # to the current object, i.e. local themes if they apply to a given
        # folder override the themes set in the folders above.

        # XXX GR I'm convinced there's a faster way of doing (starting from
        # bmf and climbing up). Will check that later if time's available.
        objs.reverse()

        # get the local theme
        localtheme = None
        for obj in objs:
            theme = self.getLocalTheme(folder=obj, level=level)
            level -= 1
            if theme is not None:
                localtheme = theme
            # we continue since the local theme can be still be overriden.
        return localtheme

    @classmethod
    def getRawLocalThemesSpec(self, folder):
        """Return the raw object specifying local themes if folder, or None."""
        folder = aq_base(folder)
        ob = getattr(folder, CPSDESIGNER_LOCAL_THEME_ID, None)
        if ob is None: # BBB
            ob = getattr(folder, CPSSKINS_LOCAL_THEME_ID, None)
        return ob

    @classmethod
    def getLocalThemesSpec(self, folder=None, **kw):
        """Return the list of local themes specifications in a given context.
        """

        if folder is None:
            return []

        theme_obj = self.getRawLocalThemesSpec(folder)

        if theme_obj is not None and callable(theme_obj):
            theme_obj = apply(theme_obj, ())
        if isinstance(theme_obj, basestring):
            theme_obj = (theme_obj, )
        if not isinstance(theme_obj, tuple):
            return []

        themes = []
        for l in theme_obj:
            split = l.split(':')
            if len(split) == 1:
                themes.append(('', (0,0), l))
                continue
            if len(split) == 2:
                nm, theme = split
                meth = ''
            else:
                meth, nm, theme = split
            if '-' not in nm:
                continue
            n, m = nm.split('-')
            themes.append((meth, (int(n), int(m)), theme))
        return themes

    def getLocalTheme(self, folder=None, level=None):
        """ Return the name of the first theme assigned to a given level
            relative to a folder.
        """

        if level is None:
            return None

        themes = self.getLocalThemesSpec(folder=folder)
        if themes is None:
            return None

        level = int(level)
        published = self.getRequestPublished()
        for meth, (n, m), theme in themes:
            if meth and meth != published:
                continue
            if n > 0 and n > level:
                continue
            if m > 0 and m < level:
                continue
            return theme

        return None


class CherryPickingCPSSkinsThemeNegociator(CPSSkinsThemeNegociator):
    """CPSSKins negociation, overridden by a property on context object only.

    This negociated is DEPRECATED. Most of its features can now be handled
    by the (standard) CPSSkins Theme Negociator.

      - local method themes are now part of the syntax. For instance, to apply
      the 'fview' page of 'special' theme to 'folder_view' method to all folders
      below current level, use:
           folder_view:0-0:special+fview
      - applying a rule to the folder on which it is defined only can be done
      if one knows the precedence rules. To perform the same binding but only
      on the folder bearing the definition, while keeping the default page of
      special theme below, use:
           1-0:special
           folder_view:0-1:special+fview
v
    The case of applying a rule to a *document* is not covered by
    CPSSkinsThemeNegociator yet, but will be implemented upon request.

    ORIGINAL DOCSTRING BEFORE DEPRECATION:

    This negociator first reads the property '.cps_designer_theme' on the
    context object *only*. No acquisition or algorithm to apply from an
    ancestor like CPSSkins does.

    The content of the property looks like this:
       <published method>:<theme>+<page>
    Example:
       folder_view:special+front

    If the property doesn't exist, it falls back on what CPSSkinsThemeNegociator
    does.

    Use cases : very simple situations where the fact that CPSSkins lookup is
    based on "bottom most folder" goes in the way.

       - applying a given theme page on a single document, different from
       its parents' or its siblings:
           'cpsdocument_view:special+unique' on that document only.
           (CPSSkins negociation would apply on parent and siblings unless they
           are themselves tuned)
       - applying a given theme page on the folder view, but not on its children
         folder_view:special+front on the folder only.
         This is a local version of CPSSKins' "Method Themes"

    """

    def getThemeAndPageName(self):
        warnings.warn("The Cherry Picking themes negociator is deprecated  "
                      "and will be removed in CPS 3.5.2. "
                      "You can now achieve the same results with "
                      "CPSSkinsThemeNegociator in order")

        prop = self.context.getProperty('.cps_designer_theme', None)
        if prop:
            published, themepage = prop.split(':')
            published = published.strip()
        if not prop or (published and published != self.getRequestPublished()):
            theme, page = CPSSkinsThemeNegociator.getThemeAndPageName(self)
        else:
            theme, page = tuple(s.strip() for s in themepage.split('+'))
        return theme, page
