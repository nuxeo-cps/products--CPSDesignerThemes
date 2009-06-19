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
import os
import re

from Products.CPSDesignerThemes.engine.etreeengine import ElementTreeEngine
from Products.CPSDesignerThemes.constants import NS_XHTML

THEMES_PATH = os.path.join(INSTANCE_HOME, 'Products', 'CPSDesignerThemes',
                           'tests')

class FakePortlet:
    def __init__(self, title, rendered):
        self.title = title
        self.rendered = rendered

    def Title(self):
        return self.title

    def title_or_id(self):
        return self.title

    def render_cache(self):
        return self.rendered

PORTLET1 = FakePortlet('portlet1', '<ul id="portlet1"><li>foo</li></ul>')

WT_REGEXP = re.compile(r'[\n ]*')

class EngineTestCase(unittest.TestCase):
    """Base test case for all engines."""

    EngineClass = None

    def getEngine(self, theme, page='index.html'):
        f = open(os.path.join(THEMES_PATH, theme, page), 'r')
        return self.EngineClass(html_file=f,
                                 theme_base_uri='/thm_base',
                                 page_uri=page)

    def test_no_portlet_title(self):
        # engine must accept a missing cps:portlet="title"
        engine = self.getEngine('theme1', 'no_portlet_title.html')
        slot_name, slot = engine.extractSlotElements().next()
        frame_parent, frame = engine.extractSlotFrame(slot)
        engine.mergePortlets(frame_parent, frame, [PORTLET1])

        rendered = WT_REGEXP.sub('', engine.dumpElement(slot))
        expected = WT_REGEXP.sub('',
                                 '<div xmlns="%s"><p><div>%s</div>'
                                 '</p></div>' % (NS_XHTML,
                                                 PORTLET1.render_cache()))
        self.assertEquals(rendered, expected)

    def test_no_portlet_body(self):
        # engine must accept a missing cps:portlet="body"
        engine = self.getEngine('theme1', 'no_portlet_body.html')
        slot_name, slot = engine.extractSlotElements().next()
        frame_parent, frame = engine.extractSlotFrame(slot)
        engine.mergePortlets(frame_parent, frame, [PORTLET1])

        rendered = WT_REGEXP.sub('', engine.dumpElement(slot))
        self.assertEquals(
            rendered, '<divxmlns="%s"><p><span>portlet1</span></p></div>' % NS_XHTML)

class TestElementTreeEngine(EngineTestCase):

    EngineClass = ElementTreeEngine


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestElementTreeEngine),
        ))
