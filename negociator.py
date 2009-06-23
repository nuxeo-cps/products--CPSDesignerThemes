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

from zope.interface import implements
from zope.component import adapts

from themecontainer import FSThemeContainer

from OFS.interfaces import IObjectManager
from zope.publisher.interfaces.http import IHTTPRequest

from Products.CMFCore.utils import getToolByName

from interfaces import IThemeEngine

logger = logging.getLogger('CPSDesignerThemes.negociator')

class EngineAdapter(object):
    """Some boiler plate logic."""

    adapts(IObjectManager, IHTTPRequest)
    implements(IThemeEngine)

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.cps_base_url = getToolByName(context, 'portal_url').getBaseUrl()

    def renderCompat(self, **kw):
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
    def getEngine(self):
        theme, page = self.getRequestedThemeAndPageName()
        return self.lookupContainer().getPageEngine(
            'default', 'index', cps_base_url=self.cps_base_url, fallback=True)

class CPSSkinsThemeNegociator(RootContainerFinder, EngineAdapter):
    """Full negociator that applies CPSSkins rules and uses a root container.
    """

    def getRequestedThemeAndPageName(self):
        """Pure indirection to CPSSkins."""
        thmtool = getToolByName(self.context, 'portal_themes')
        theme, page = thmtool.getRequestedThemeAndPageName(
            context_obj=self.context)
        logger.debug('CPSSkinsThemeNegociator: requesting (%s,%s)', theme, page)
        return theme, page

    def getEngine(self):
        """The fallback is up to the container."""
        theme, page = self.getRequestedThemeAndPageName()
        return self.lookupContainer().getPageEngine(
            theme, page, cps_base_url=self.cps_base_url, fallback=True)

