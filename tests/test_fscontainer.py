# (C) Copyright 2009 Georges Racinet
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
from zope.testing import doctest
from Testing.ZopeTestCase import ZopeTestCase
import Acquisition
from ZPublisher.HTTPResponse import HTTPResponse
from Products.CPSDesignerThemes.themecontainer import FSThemeContainer
from Products.CPSDesignerThemes.exceptions import AttackError

class LoggerResponse(HTTPResponse):

    out_data = ''

    def write(self, s):
        self.out_data += s

class FakeUrlTool(Acquisition.Implicit):

    def getBaseUrl(self):
        return '/cps_base_url/'

class TestFsContainer(ZopeTestCase):

    def afterSetUp(self):
        cont = FSThemeContainer('container')
        cont.manage_changeProperties(
            relative_path='Products/CPSDesignerThemes/tests',
            default_theme='theme1')
        self.folder._setObject(cont.getId(), cont)
        self.folder.portal_url = FakeUrlTool()
        self.container = self.folder.container
        self.container_path = self.container.absolute_url_path()
        self.app.REQUEST.RESPONSE = LoggerResponse()

    def testSecurity(self):
        attack = os.path.join(os.path.pardir, 'htaccess')
        self.assertRaises(ValueError, self.container.manage_changeProperties,
                    relative_path=attack)

    def testSecurity2(self):
        # see #2463
        parent = os.path.pardir
        attack = os.path.join(parent, parent, 'secret')
        get_engine = self.container.getPageEngine
        self.assertRaises(AttackError, get_engine, attack, None)
        self.assertRaises(AttackError, get_engine, None, attack)
        self.assertRaises(AttackError, get_engine, attack, attack)

    def testListAllThemes(self):
        self.assertEquals(self.container.listAllThemes(), (
            dict(id='theme1', title='theme1', default=True),
            dict(id='theme2', title='theme2', default=False),
            dict(id='theme3', title='theme3', default=False),
            dict(id='xinclude', title='xinclude', default=False),
            ))

    def testListPagesFor(self):
        self.assertEquals(self.container.listAllPagesFor('theme3'), (
            dict(id='page1.html', title='page1.html', default=False),))


    def testCssUriRewrite(self):
        sheet = self.container['theme1']['front.css']
        request = self.app.REQUEST
        res = sheet.index_html(request, request.RESPONSE).split('\n')

        self.assertEquals(
            res[1].strip(),
            'background: url(%s/theme1/bg.gif);' % self.container_path)
        self.assertEquals(
            res[5].strip(),
            'background: url(%s/theme1/images/back.png);' % self.container_path)
        self.assertEquals(
            res[9].strip(),
            'background: url(/cps_base_url/dyn.jpg);')

    def testCssUriRewriteDeep(self):
        sheet = self.container['theme1']['style']['top.css']
        request = self.app.REQUEST
        res = sheet.index_html(request, request.RESPONSE).split('\n')

        self.assertEquals(
            res[1].strip(),
            'background: url(%s/theme1/style/bg.gif);' % self.container_path)
        self.assertEquals(
            res[5].strip(),
            'background: url(%s/theme1/images/back.png);' % self.container_path)

    def testStyleSheetOptions(self):
        # see tests/theme2/stylesheet_options.xml
        sheet = self.container['theme2']['style']['top.css']
        request = self.app.REQUEST
        res = sheet.index_html(request, request.RESPONSE).split('\n')

        # absolute path URI didn't get rewritten
        self.assertEquals(res[5].strip(),
                          'background: url(/images/back.png);')

        # relative path URIs have been treated as usual
        self.assertEquals(
            res[1].strip(),
            'background: url(%s/theme2/style/bg.gif);' % self.container_path)

    def testGetPageEngine(self):
        # See #2137
        e1 = self.container.getPageEngine('theme1', 'two_slots')
        e2 = self.container.getPageEngine('theme1', 'two_slots.html')

        self.assertEquals(e1.page_uri, e2.page_uri)
        self.assertEquals(e1.serialize(), e2.serialize())

        # other exts
        e = self.container.getPageEngine('theme1', 'fs-extension.xhtml')
        self.assertEquals(e.page_uri, '/fs-extension.xhtml')
        self.assertEquals(e.serialize().strip(), '<html>xhtml extension</html>')

        e = self.container.getPageEngine('theme1', 'fs-extension.cpsthm')
        self.assertEquals(e.page_uri, '/fs-extension.cpsthm')
        self.assertEquals(e.serialize().strip(),
                          '<html>cpsthm extension</html>')

        # now wrong theme or path
        self.assertRaises(ValueError, self.container.getPageEngine,
                          'no-such-theme', 'page')
        self.container.manage_changeProperties(relative_path='no-such-dir')
        self.assertRaises(ValueError, self.container.getPageEngine, 'theme',
                          'page')


def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite('Products.CPSDesignerThemes.themecontainer',
                             optionflags=doctest.NORMALIZE_WHITESPACE),
        unittest.makeSuite(TestFsContainer),
        ))
