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

from zope.interface import implements
from zope.component import adapts

from negociator import EngineAdapter

from OFS.interfaces import IObjectManager
from zope.publisher.interfaces.http import IHTTPRequest
from interfaces import IThemeEngine

class TestingEngine(object):
    """Dummy engine for unit tests."""

    def renderCompat(self, metal_slots=None, pt_output='', **kw):
        if metal_slots is None:
            return ''
        pt_output = pt_output.strip()

        res = ['<html><body>']
        for slot, contents in metal_slots.items():
            res.extend(('<slot name="%s">' % slot, contents, '</slot>'))
        if pt_output:
            res.extend(('<pt>', pt_output,'</pt>'))
        res.append('</body></html>')

        return ''.join(res)

class TestingNegociator(EngineAdapter):
    """Leverages TestingEngine."""

    adapts(IObjectManager, IHTTPRequest)
    implements(IThemeEngine)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def getEngine(self):
        return TestingEngine()

