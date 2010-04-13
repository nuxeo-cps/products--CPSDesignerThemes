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

import unittest
from Testing import ZopeTestCase

from Acquisition import Implicit

from Products.CPSDesignerThemes.themecontainer import FSThemeContainer
from Products.CPSDesignerThemes.negociator import FixedFSThemeEngine

from Products.CPSDesignerThemes.interfaces import IThemeContainer

ZopeTestCase.installProduct('CPSDesignerThemes')

class FakeUrlTool(Implicit):
    id = 'portal_url'

    def getPortalObject(self):
        return self.aq_inner.aq_parent

    def getBaseUrl(self):
        return '/'

class TestFixedFSThemeEngine(ZopeTestCase.ZopeTestCase):

    def afterSetUp(self):
        self.folder.portal_url = FakeUrlTool().__of__(self.folder)
        self.folder.default_charset = 'latin-1'
        self.folder._setObject('container', FSThemeContainer('container'))

    def testLookupContainer(self):
        negociator = FixedFSThemeEngine(self.folder, self.app.REQUEST)
        container = negociator.lookupContainer()
        self.assertTrue(IThemeContainer.providedBy(container))
        self.assertEquals(container.getId(), 'container')

    def testCharset(self):
        negociator = FixedFSThemeEngine(self.folder, self.app.REQUEST)
        self.assertEquals(negociator.encoding, 'latin-1')

        self.folder.default_charset = 'unicode'
        negociator = FixedFSThemeEngine(self.folder, self.app.REQUEST)
        self.assertEquals(negociator.encoding, 'utf-8')


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestFixedFSThemeEngine),
        ))
