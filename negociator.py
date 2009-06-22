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

from zope.interface import implements
from zope.component import adapts

from themecontainer import FSThemeContainer

from OFS.interfaces import IObjectManager
from zope.publisher.interfaces.http import IHTTPRequest

from Products.CMFCore.utils import getToolByName

from interfaces import IThemeEngine

class EngineAdapter(object):
    """Some boiler plate logic."""
    def renderCompat(self, **kw):
        return self.getEngine().renderCompat(context=self.context,
                                             request=self.request, **kw)

class ThemeNegociator(EngineAdapter):
    """General theme negociator.

    For now, filesystem based, no negociation at all. Just one page and theme:
    default/index.html
    """
    adapts(IObjectManager, IHTTPRequest)
    implements(IThemeEngine)

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.cps_base_url = getToolByName(context, 'portal_url').getBaseUrl()

    def lookupContainer(self):
        # For now, the first FS container found at the root
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        containers = portal.objectValues(['Filesystem Theme Container',
                                          'Theme Container'])
        if not containers:
            raise KeyError('No theme container found')
        return containers[0]

    def getEngine(self):
        return self.lookupContainer().getPageEngine(
            'default', 'index', cps_base_url=self.cps_base_url)

