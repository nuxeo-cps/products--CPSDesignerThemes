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

import unittest
from Testing.ZopeTestCase import ZopeTestCase
from ZPublisher.HTTPResponse import HTTPResponse
from Products.CPSDesignerThemes.themecontainer import FSThemeContainer

class LoggerResponse(HTTPResponse):

    out_data = ''

    def write(self, s):
        self.out_data += s

class TestFsContainer(ZopeTestCase):

    def afterSetUp(self):
        cont = FSThemeContainer('container')
        cont.manage_changeProperties(
            relative_path='Products/CPSDesignerThemes/tests')
        self.folder._setObject(cont.getId(), cont)
        self.container = self.folder.container
        self.container_path = self.container.absolute_url_path()
        self.app.REQUEST.RESPONSE = LoggerResponse()

    def testSecurity(self):
        self.assertRaises(ValueError, self.container.manage_changeProperties,
                    relative_path='../htaccess')

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


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestFsContainer),
        ))
