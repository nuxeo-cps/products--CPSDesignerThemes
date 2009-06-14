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

import re
import unittest
from zope import component
from Testing import ZopeTestCase
from Products.PageTemplates.ZopePageTemplate import ZopePageTemplate

from Products.CPSDesignerThemes.testing import TestingNegociator

ZopeTestCase.installProduct('CPSDesignerThemes')

component.provideAdapter(TestingNegociator)

class TestTal(unittest.TestCase):
    """Low level test case for the TAL patching"""

MACRO_DEF_ID="macro_def"

MACRO_DEF="""
<metal:slot-recorder define-macro="mac">
  Before
  <metal:block define-slot="sl1">SL1</metal:block>
  After
</metal:slot-recorder>
"""

USE1="""
<div>
<metal:block use-macro="here/%s/macros/mac">
  <metal:block fill-slot="sl1"><span tal:content="string:slot contents"/>
  </metal:block>
</metal:block>
</div>
""" % MACRO_DEF_ID

USE2="""
<body metal:use-macro="here/%s/macros/mac">
  <div metal:fill-slot="sl1">
     slot contents
  </div>
</body>
""" % MACRO_DEF_ID

USE3="""
<body metal:use-macro="here/%s/macros/mac">
  <div metal:fill-slot="sl1" tal:define="content string:slot contents">
     <tal:block content="content"/>
  </div>
</body>
""" % MACRO_DEF_ID

STRIP_WT = re.compile(r'[\s\n]+')

class TestZpt(ZopeTestCase.ZopeTestCase):
    """Please see what TestingEngine does."""

    def afterSetUp(self):
        md = ZopePageTemplate(MACRO_DEF_ID, text=MACRO_DEF)
        self.folder._setObject(md.getId(), md)

    def test_use1(self):
        use = ZopePageTemplate('use', text=USE1)
        self.folder._setObject('use', use)
        result = STRIP_WT.sub(' ', self.folder.use()).strip()
        self.assertEquals(result,
                          '<html><body><slot name="sl1">'
                          '<span>slot contents</span> </slot>'
                          '<pt><div> Before After </div></pt>'
                          '</body></html>')

    def test_use2(self):
        use = ZopePageTemplate('use', text=USE2)
        self.folder._setObject('use', use)
        result = STRIP_WT.sub(' ', self.folder.use()).strip()
        self.assertEquals(result,
                          '<html><body><slot name="sl1"><div> '
                          'slot contents '
                          '</div></slot><pt>Before After</pt></body></html>')

    def test_use3(self):
        use = ZopePageTemplate('use', text=USE3)
        self.folder._setObject('use', use)
        result = STRIP_WT.sub(' ', self.folder.use()).strip()
        self.assertEquals(result,
                          '<html><body><slot name="sl1"><div> '
                          'slot contents '
                          '</div></slot><pt>Before After</pt></body></html>')

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestTal),
        unittest.makeSuite(TestZpt),
        ))

