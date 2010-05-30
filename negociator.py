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

from zope.interface import implements
from zope.component import adapts
from Acquisition import aq_base, aq_parent, aq_inner

from themecontainer import FSThemeContainer

from OFS.interfaces import IObjectManager
from zope.publisher.interfaces.http import IHTTPRequest

from Products.CMFCore.utils import getToolByName

CPSSKINS_THEME_COOKIE_ID = 'cpsskins_theme'
CPSDESIGNER_THEME_COOKIE_ID = 'cpsdesigner_theme'
CPSSKINS_LOCAL_THEME_ID = '.cpsskins_theme'
CPSDESIGNER_LOCAL_THEME_ID = '.cps_themes_bindings'

from interfaces import IThemeEngine

logger = logging.getLogger('CPSDesignerThemes.negociator')

class EngineAdapter(object):
    """Some boiler plate logic."""

    adapts(IObjectManager, IHTTPRequest)
    implements(IThemeEngine)

    def __init__(self, context, request):
        self.context = context
        self.request = request

        # GR don't want to import a constant from CPSDefault here
        self.void = void = getattr(request, '_cps_void_response', None)
        if void is None:
            logger.warn("Didn't found marker in request. Void responses "
                        "(302, 304...) quick handling might be broken.")

        # portal-related stuff
        utool = getToolByName(context, 'portal_url')
        self.cps_base_url = utool.getBaseUrl()
        enc = utool.getPortalObject().default_charset
        if enc == 'unicode':
            # XXX maybe better to introspect zpublisher conf
            # TODO CPSUtil can do that now
            enc = 'utf-8'
        self.encoding = enc

    def getThemeAndPageName(self):
        """Return the theme and page that should be rendered.
        Both can be None, meaning that some downstream (container) defaults
        may still apply.

        To be implemented by subclasses."""
        raise NotImplementedError

    def getEngine(self):
        """The fallback is up to the container."""
        theme, page = self.getThemeAndPageName()
        logger.debug("Requested theme: %r page: %r", theme, page)
        return self.lookupContainer().getPageEngine(
            theme, page, cps_base_url=self.cps_base_url, fallback=True,
            encoding=self.encoding)

    def renderCompat(self, **kw):
        if self.void: # return asap for efficiency (see #2040)
            return ''
        return self.getEngine().renderCompat(context=self.context,
                                             request=self.request, **kw)
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
           TODO: cleaner to extract this in a common module in CPSUtil
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
            view_mode = self.getViewMode()
            theme = view_mode.get('theme')
            page = view_mode.get('page')
            if (theme is not None) or (page is not None):
                return self._extractThemeAndPageName(theme, page)

        # cookie (theme + page)
        theme = self.getThemeCookie()
        if theme is not None:
            return self._extractThemeAndPageName(theme, None)

        # method themes (theme + page)
        published = REQUEST.get('PUBLISHED')
        if published is not None:
            try:
                published = published.getId()
            except AttributeError:
                pass
            else:
                theme = self.getThemeByMethod(published)  # TODO ADAPT
                if theme is not None:
                    return self._extractThemeAndPageName(theme, None)

        # local theme + page
        theme = self.getLocalThemeName(**kw)
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

           where:
           - 'theme' is the theme id
           - (n, m) is a couple with n <= m that describes the interval
             inside which the theme will be used.
             (0, 0) means the current folder and all subfolders
             (1, 0) means all subfolders below the current folder
             (1, 1) means the subfolders of level 1
             (0, 1) means the folder and the subfolders of level 1
             (n, n) means the subfolders of level n
             ...

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
            if ':' not in l:
                themes.append(((0,0), l))
                continue
            nm, theme = l.split(':')
            if '-' not in nm:
                continue
            n, m = nm.split('-')
            themes.append(((int(n), int(m)), theme))
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
        for (n, m), theme in themes:
            if n > 0 and n > level:
                continue
            if m > 0 and m < level:
                continue
            return theme

        return None


class CherryPickingCPSSkinsThemeNegociator(CPSSkinsThemeNegociator):
    """CPSSKins negociation, overridden by a property on context object only.

    TODO Initiate RST doc about negociators hooking and predefined negociators.

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
        prop = self.context.getProperty('.cps_designer_theme', None)
        if prop:
            published, themepage = prop.split(':')
            published = published.strip()
        if not prop or (published and published != self.getRequestPublished()):
            theme, page = CPSSkinsNegociator.getThemeAndPageName(self)
        else:
            theme, page = tuple(s.strip() for s in themepage.split('+'))
        return theme, page
