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
from zope.testing import doctest
import os
import re

from Products.CPSDesignerThemes.engine.etreeengine import ElementTreeEngine
from Products.CPSDesignerThemes.engine.lxmlengine import LxmlEngine
from Products.CPSDesignerThemes.constants import NS_XHTML

THEMES_PATH = os.path.join(INSTANCE_HOME, 'Products', 'CPSDesignerThemes',
                           'tests')

class FakePortlet:
    def __init__(self, title, rendered):
        self.title = title
        self.rendered = rendered

    def getId(self):
        return self.title

    def Title(self):
        return self.title

    def title_or_id(self):
        return self.title

    def render_cache(self, **kw):
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
                                 page_uri='/'+page)

    def findTag(self, engine, tag):
        raise NotImplementedError

    def test_entities(self):
        engine = self.getEngine('theme1', 'simple_slot.html')
        slot_name, slot = engine.extractSlotElements().next()
        frame_parent, frame = engine.extractSlotFrame(slot)
        portlet = FakePortlet('entity_portlet', '<spoon>&nbsp;</spoon>')
        engine.mergePortlets(frame_parent, frame, [portlet])

        rendered = WT_REGEXP.sub('', engine.dumpElement(slot))
        expected = WT_REGEXP.sub(
            '', '<div xmlns="%s"><p>'
            '<span>%s</span><div>%s</div>'
            '</p></div>' % (NS_XHTML,
                            portlet.title_or_id(),
                            portlet.render_cache()))
        expected = expected.replace('&nbsp;', '&#160;')
        self.assertEquals(rendered, expected)

    def test_uri_rewrite(self):
        # engine must accept a missing cps:portlet="body"
        engine = self.getEngine('theme1', 'uris.html')
        img = self.findTag(engine, 'img')
        self.assertEquals(img.attrib['src'], '/thm_base/pretty.png')


class TestElementTreeEngine(EngineTestCase):

    EngineClass = ElementTreeEngine

    @classmethod
    def findTag(self, engine, tag):
        return engine.root.find('.//{%s}%s' % (NS_XHTML, tag))

class TestLxmlEngine(TestElementTreeEngine):

    EngineClass = LxmlEngine


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestElementTreeEngine),
        unittest.makeSuite(TestLxmlEngine),
        doctest.DocFileTest('engine/doctest.txt',
                            package='Products.CPSDesignerThemes',
                            optionflags=doctest.ELLIPSIS,
                            globs=dict(PageEngine=ElementTreeEngine)),
        doctest.DocFileTest('engine/doctest.txt',
                            package='Products.CPSDesignerThemes',
                            optionflags=doctest.ELLIPSIS,
                            globs=dict(PageEngine=LxmlEngine)),
        ))
