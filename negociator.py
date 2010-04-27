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

from themecontainer import FSThemeContainer

from OFS.interfaces import IObjectManager
from zope.publisher.interfaces.http import IHTTPRequest

from Products.CMFCore.utils import getToolByName
from Products.CPSUtil.text import get_final_encoding

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
        self.encoding = get_final_encoding(utool.getPortalObject())

    def getThemeAndPageName(self):
        """Return the theme and page that should be rendered.
        To be implemented by subclasses."""
        raise NotImplementedError

    def getEngine(self):
        """The fallback is up to the container."""
        theme, page = self.getThemeAndPageName()
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
    """Full negociator that applies CPSSkins rules and uses a root container.
    """

    def getCPSSkinsThemeAndPageName(self):
        """Pure indirection to CPSSkins."""
        thmtool = getToolByName(self.context, 'portal_themes')
        theme, page = thmtool.getRequestedThemeAndPageName(
            context_obj=self.context, no_defaults=True)
        logger.debug('CPSSkinsThemeNegociator: requesting (%s,%s)', theme, page)
        return theme, page

    getThemeAndPageName = getCPSSkinsThemeAndPageName

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

    def getThemeAndPageName(self):
        prop = self.context.getProperty('.cps_designer_theme', None)
        if prop:
            published, themepage = prop.split(':')
            published = published.strip()
        if not prop or (published and published != self.getRequestPublished()):
            theme, page = self.getCPSSkinsThemeAndPageName()
        else:
            theme, page = tuple(s.strip() for s in themepage.split('+'))
        return theme, page




