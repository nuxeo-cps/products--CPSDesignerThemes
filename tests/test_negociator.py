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
import unittest
from Testing import ZopeTestCase

from Acquisition import Implicit
from OFS.Folder import Folder
from zExceptions import BadRequest

from Products.CPSDesignerThemes.themecontainer import FSThemeContainer
from Products.CPSDesignerThemes.exceptions import AttackError
from Products.CPSDesignerThemes.negociator import FixedFSThemeEngine
from Products.CPSDesignerThemes.negociator import CPSSkinsThemeNegociator
from Products.CPSDesignerThemes.negociator import (
    CPSSKINS_LOCAL_THEME_ID, CPSSKINS_THEME_COOKIE_ID
    )

from Products.CPSDesignerThemes.interfaces import IThemeContainer

ZopeTestCase.installProduct('CPSDesignerThemes')

class FakeUrlTool(Implicit):
    id = 'portal_url'

    def getPortalObject(self):
        return self.aq_inner.aq_parent

    def getBaseUrl(self):
        return '/'

    def getRelativeContentPath(self, content):
        portal_phy = self.getPortalObject().getPhysicalPath()
        content_phy = content.getPhysicalPath()
        return content_phy[len(portal_phy):]

class FakeTranslationService(Implicit):

    def getSelectedLanguage(self):
        return 'de'

class BaseNegociatorTest(ZopeTestCase.ZopeTestCase):

    def afterSetUp(self):
        self.app.REQUEST.set('_cps_void_response', False)
        self.folder.portal_url = FakeUrlTool().__of__(self.folder)
        self.folder._setOb('translation_service', FakeTranslationService())
        self.folder.default_charset = 'latin-1'
        self.folder._setObject('container', FSThemeContainer('container'))

class TestFixedFSThemeEngine(BaseNegociatorTest):


    def testLookupContainer(self):
        negociator = FixedFSThemeEngine(self.folder, self.app.REQUEST)
        container = negociator.lookupContainer()
        self.assertTrue(IThemeContainer.providedBy(container))
        self.assertEquals(container.getId(), 'container')

    def testCharsetUrl(self):
        negociator = FixedFSThemeEngine(self.folder, self.app.REQUEST)
        self.assertEquals(negociator.cps_base_url, '/')
        self.assertEquals(negociator.encoding, 'latin-1')

        self.folder.default_charset = 'unicode'
        negociator = FixedFSThemeEngine(self.folder, self.app.REQUEST)
        self.assertEquals(negociator.encoding, 'utf-8')

    def testVoidResponse(self):
        request = self.app.REQUEST
        request._cps_void_response = True
        negociator = FixedFSThemeEngine(self.folder, request)
        self.assertEquals(negociator.renderCompat(), '')




class TestCPSSkinsNegociator(BaseNegociatorTest):
    """Adaptation from CPSSkins tests."""

    def afterSetUp(self):
        BaseNegociatorTest.afterSetUp(self)

        self.portal = self.folder
        self.REQUEST = self.portal.REQUEST
        self.REQUEST.SESSION = {}
        self.REQUEST.cookies = {}
        self.REQUEST.form = {}

    def getRequestedThemeAndPageName(self, context_obj=None):
        if context_obj is None:
            context_obj = self.folder

        neg = CPSSkinsThemeNegociator(context_obj, self.REQUEST)
        return neg.getThemeAndPageName()

    def test_printable(self):
        self.REQUEST.form['pp'] = '1'
        theme = self.getRequestedThemeAndPageName()
        self.assert_(theme == ('printable', None))

    def test_form_1(self):
        self.REQUEST.form['theme'] = 'theme'
        theme = self.getRequestedThemeAndPageName()
        self.assert_(theme == ('theme', None))

    def test_form_2(self):
        self.REQUEST.form['theme'] = 'theme+page'
        theme = self.getRequestedThemeAndPageName()
        self.assert_(theme == ('theme', 'page'))

    def test_form_3(self):
        self.REQUEST.form['theme'] = 'theme+page1'
        self.REQUEST.form['page'] = 'page2'
        theme = self.getRequestedThemeAndPageName()
        self.assert_(theme == ('theme', 'page1'))

    def test_cookie_theme_1(self):
        self.REQUEST.cookies[CPSSKINS_THEME_COOKIE_ID] = 'theme'
        theme = self.getRequestedThemeAndPageName()
        self.assert_(theme == ('theme', None))

    def test_cookie_theme_2(self):
        self.REQUEST.cookies[CPSSKINS_THEME_COOKIE_ID] = 'theme+page'
        theme = self.getRequestedThemeAndPageName()
        self.assert_(theme == ('theme', 'page'))

    def test_attack_reraising(self):
        # see #2463, here we test only the exc reraising
        neg = CPSSkinsThemeNegociator(self.folder, self.REQUEST)
        container = neg.lookupContainer()
        def raiser(*a, **kw):
            raise AttackError("We're under attack")
        container.getPageEngine = raiser
        self.assertRaises(BadRequest, neg.getEngine)

    # Deactivated tests related to the themes editor.
    # Maybe will have to do something similar later for the portlets editor.
    def xtest_session_1(self):
        self.tmtool.setViewMode(theme='theme')
        theme = self.tmtool.getRequestedThemeAndPageName(editing=1)
        self.assert_(theme == ('theme', None))

    def xtest_session_2(self):
        self.tmtool.setViewMode(theme='theme', page='page')
        theme = self.tmtool.getRequestedThemeAndPageName(editing=1)
        self.assert_(theme == ('theme', 'page'))

    def xtest_session_3(self):
        self.tmtool.setViewMode(theme='theme+page1', page='page2')
        theme = self.tmtool.getRequestedThemeAndPageName(editing=1)
        self.assert_(theme == ('theme', 'page1'))

    def xtest_session_3(self):
        # the session info is only read in editing mode
        theme = self.tmtool.getRequestedThemeAndPageName()
        self.assert_(theme != ('theme', None))

    def getLocalThemeFolder(self):
        testfolder = self.makeSubFolder(self.portal, 'treeroot')
        return self.makeSubFolder(testfolder, 'fold_two')

    def makeSubFolder(self, folder, new_id):
        sub = Folder(new_id)
        folder._setOb(new_id, sub)
        return getattr(folder, new_id)

    def test_local_theme_1(self):
        folder = self.getLocalThemeFolder()
        value = 'theme'
        folder.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'string')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assert_(theme == ('theme', None))

    def test_local_theme_2(self):
        folder = self.getLocalThemeFolder()
        value = 'theme+page'
        folder.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'string')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assert_(theme == ('theme', 'page'))

    def test_local_theme_3(self):
        folder = self.getLocalThemeFolder()
        subfolder = self.makeSubFolder(folder, 'subfolder')

        value = 'theme'
        folder.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'string')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assert_(theme == ('theme', None))
        theme = self.getRequestedThemeAndPageName(context_obj=subfolder)
        self.assert_(theme == ('theme', None))

    def test_local_theme_4(self):
        folder = self.getLocalThemeFolder()
        subfolder = self.makeSubFolder(folder, 'subfolder')

        value = '1-1:theme'
        folder.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'string')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assertEquals(theme, (None, None))
        theme = self.getRequestedThemeAndPageName(context_obj=subfolder)
        self.assertEquals(theme, ('theme', None))

    def test_local_theme_method_1(self):
        folder = self.getLocalThemeFolder()
        subfolder = self.makeSubFolder(folder, 'subfolder')

        class FakeMethod:
            def __init__(self, mid):
                self.mid = mid
            def getId(self):
                return self.mid

        value = ('folder_view:0-0:other+front', '1-1:theme',
                 'other_view:1-0:other+bar', '0-0:other',)
        folder.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'lines')

        self.REQUEST['PUBLISHED'] = FakeMethod('foo')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assertEquals(theme, ('other', None))

        theme = self.getRequestedThemeAndPageName(context_obj=subfolder)
        self.assertEquals(theme, ('theme', None))

        self.REQUEST['PUBLISHED'] = FakeMethod('folder_view')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assertEquals(theme, ('other', 'front'))

        self.REQUEST['PUBLISHED'] = FakeMethod('folder_view')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assertEquals(theme, ('other', 'front'))

        # one level deeper
        ssubfolder = self.makeSubFolder(subfolder, 'ssubfolder')
        self.REQUEST['PUBLISHED'] = FakeMethod('other_view')
        theme = self.getRequestedThemeAndPageName(context_obj=ssubfolder)
        self.assertEquals(theme, ('other', 'bar'))

        self.REQUEST['PUBLISHED'] = FakeMethod('foo')
        theme = self.getRequestedThemeAndPageName(context_obj=ssubfolder)
        self.assertEquals(theme, ('other', None))

    def test_local_theme_5(self):
        folder = self.getLocalThemeFolder()
        subfolder = self.makeSubFolder(folder, 'subfolder')

        value = ['1-1:theme2', '0-0:theme1']
        folder.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'lines')
        theme = self.getRequestedThemeAndPageName(context_obj=folder)
        self.assert_(theme == ('theme1', None))
        theme = self.getRequestedThemeAndPageName(context_obj=subfolder)
        self.assert_(theme == ('theme2', None))

    def test_local_theme_6(self):

        testfolder = self.getLocalThemeFolder()

        value = ['1-0:theme1+page1']

        portal = self.portal
        portal.manage_addProperty(CPSSKINS_LOCAL_THEME_ID, value, 'lines')
        theme = self.getRequestedThemeAndPageName(context_obj=portal)
        self.assert_(theme == (None, None))
        theme = self.getRequestedThemeAndPageName(context_obj=testfolder)
        self.assert_(theme == ('theme1', 'page1'))

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestFixedFSThemeEngine),
        unittest.makeSuite(TestCPSSkinsNegociator),
        ))
