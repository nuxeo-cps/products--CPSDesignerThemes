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

import logging
from copy import deepcopy
from StringIO import StringIO # use TAL's faster StringIO ?

try:
    import cElementTree as ET
except ImportError:
        import elementtree.ElementTree as ET
import patchetree

from zope.interface import implements

from Products.CMFCore.utils import getToolByName

from Products.CPSDesignerThemes.interfaces import IThemeEngine
from Products.CPSDesignerThemes.constants import NS_URI, NS_XHTML, ENCODING
from Products.CPSDesignerThemes.utils import rewrite_uri
from base import BaseEngine

def ns_prefix(name):
    return '{%s}%s' % (NS_URI, name)

HEAD = '{%s}head' % NS_XHTML
BODY = '{%s}body' % NS_XHTML

PORTLET_ATTR = ns_prefix('portlet')
SLOT_ATTR = ns_prefix('slot')
MAIN_CONTENT_ATTR = ns_prefix('main-content')
METAL_HEAD_SLOTS = ( # the passed slots that end up in the <head> element
    'base', 'head_slot', 'style_slot', 'javascript_head_slot')

def find_by_attribute(elt, attr_name, value=None):
    """Shameless implementation of search by attribute.

    Workaround the fact that attribute xpath expressions are supported
    with elementtree >= 1.3, which is unreleased and unavailable for me."""

    presence = value is None
    all = elt.findall('.//*')

    if presence:
        return (e for e in all if attr_name in e.keys())
    else:
        return (e for e in all if e.get(attr_name) == value)

LINK_HTML_DOCUMENTS = {'img' : 'src',
                       'link'    : 'href',
                       'object'  : 'data',
                       'param' : 'value',
                       }

class ElementTreeEngine(BaseEngine):
    """An engine based on ElementTree API

    http://effbot.org/zone/element-index.htm
    GR: can't afford the effort to build lxml on my box.

    This is a starting point implementation. XML format is still
    likely to change at this point. There's room for optimisation, like
    avoiding parsing the templates all over again. Therefore, in the future
    a given engine could persist in memory and be used for several
    context/request pairs.

    On the other hand, this is already really fast.
    """

    implements(IThemeEngine)

    logger = logging.getLogger(
        'Products.CPSDesignerThemes.engine.ElementTreeEngine')

    XML_HEADER = '<?xml version="1.0" encoding="%s"?>' % ENCODING

    def __init__(self, html_file=None, theme_base_uri='', page_uri=''):
        self.tree = ET.parse(html_file)
        self.root = self.tree.getroot()
        BaseEngine.__init__(self, theme_base_uri=theme_base_uri,
                            page_uri=page_uri)

    #
    # Internal engine API implementation. For docstrings, see BaseEngine
    #

    def rewriteUris(self):
        for tag, attr in LINK_HTML_DOCUMENTS.items():
            for elt in self.root.findall('.//{%s}%s' % (NS_XHTML, tag)):
                uri = elt.attrib[attr]
                try:
                    new_uri = rewrite_uri(uri=uri,
                        absolute_base=self.theme_base_uri,
                        referer_uri=self.page_uri)
                except KeyError:
                    raise ValueError(
                        "Missing attribute %s on <%s> element" % (attr, tag))
                elt.attrib[attr] = new_uri
                self.logger.debug("URI Rewrite %s -> %s" % (uri, new_uri))

    def extractSlotElements(self):
        return ((slot.attrib.pop(SLOT_ATTR), slot)
                for slot in find_by_attribute(self.root, SLOT_ATTR))

    @classmethod
    def parseHeadBody(self, pt_output):
        parsed = self.parseFragment(pt_output)
        return (parsed.find('.//' + elt) for elt in (HEAD, BODY))

    @classmethod
    def parseFragment(self, content, enclosing=None):
        # TODO GR: this works around the fact that entity support in
        # my ElementTree version doesn't work as advertised
        content = content.replace('&nbsp;', ' ')

        parser = ET.XMLParser()
        # TODO load all entities, and do it just once
        parser.entity['nbsp'] = unichr(160)
        parser.feed(self.XML_HEADER)

        # We always need an enclosing tag to bear the xhtml namespace
        if enclosing is None:
            enclosing = 'default-document'
            remove_enclosing = True
        else:
            remove_enclosing = False
        parser.feed('<%s xmlns="%s">' % (enclosing, NS_XHTML))
        parser.feed(content)
        parser.feed("</%s>" % enclosing)

        try:
            parsed = parser.close()
        except SyntaxError, e:
            self.logger.error("Problematic xml snippet:\n", content)

        return remove_enclosing and parsed[0] or parsed

    def mergeBodyElement(self, from_cps=None):
        """Merge the body element issued by CPS' ZPTs in the theme's

        This processes attributes only. Typically, these are onload, class, and
        style. Any attribute defined by the theme takes precedence.
        """
        body = self.tree.find(BODY)
        for k, v in from_cps.attrib.items():
            if k not in body.attrib:
                body.attrib[k] = v

    def mergeHeads(self, head_content='', cps_global=None):
        """Merge the contextual head_content with cps' global and the theme's.

        For now, this is stupid concatenation.
        TODO: this should:
          - respect a natural ordering, and in particular put all
            JS scripts towards the end,
          - actually merge cps_global with the theme's head (we should first
            define a policy about this).
        """
        in_theme = self.tree.find(HEAD)
        parsed = self.parseFragment(head_content, enclosing='head')

        if cps_global is not None:
            if cps_global.text:
                in_theme[-1].tail += cps_global.text
            for child in cps_global:
                in_theme.append(child)

        if parsed.text:
            in_theme[-1].tail += parsed.text
        for child in parsed:
            in_theme.append(child)

    def renderMainContent(self, main_content):
        main_elt = find_by_attribute(self.root, MAIN_CONTENT_ATTR).next()
        # TODO make main-content element not mandatory

        # cleaning up
        del main_elt.attrib[ns_prefix('main-content')]
        for child in main_elt:
            main_elt.remove(child)

        parsed_main = self.parseFragment(main_content, enclosing='main-content')
        main_elt.text = parsed_main.text
        for child in parsed_main:
            main_elt.append(child)

    @classmethod
    def extractSlotFrame(self, slot):
        """Find the frame part in the slot and remove it from the tree.

        Sibling frames (elements bearing 'cps:frame' attribute) are tolerated
        as a convenience for web designers wanting to check their output
        with several portlets TODO: move this to general doc."""

        frame = None
        for child in slot:
            if child.get(PORTLET_ATTR) == 'frame':
                if frame is None:
                    del child.attrib[PORTLET_ATTR]
                    frame = child
                    frame_parent = slot
                slot.remove(child)
        if frame is None:
            # same below
            # XXX awful style
            for elt in slot.findall('.//*'):
                for child in elt:
                    if child.get(ns_prefix('portlet')) == 'frame':
                        if frame is None:
                            frame = child
                        elt.remove(child)
                        break
                else:
                    continue
            frame_parent = elt
        return frame_parent, frame

    @classmethod
    def mergePortlets(self, frame_parent, frame, portlets):
        # now merging the portlets
        for portlet in portlets:
            rendered = portlet.render_cache().strip()
            if not rendered:
                continue
            ptl_elt = deepcopy(frame)

            elts = tuple(find_by_attribute(ptl_elt, PORTLET_ATTR,
                                           value='title'))
            if elts:
                title_elt = elts[0]
                del title_elt.attrib[PORTLET_ATTR]
                title_elt.text = portlet.title_or_id() # TODO i18n title etc.

            elts = tuple(find_by_attribute(ptl_elt, PORTLET_ATTR,
                                             value='body'))

            if elts:
                body_elt = elts[0]
                del body_elt.attrib[PORTLET_ATTR]
                body_elt.text = ''
                for child in body_elt:
                    body_elt.remove(child)
                body_elt.append(self.parseFragment(portlet.render_cache()))

            frame_parent.append(ptl_elt)

    def protectEmptyElements(self, *tags):
        # maybe lxml can do this better
        # there's also a recent option in ElementTree, but not in my version
        for tag in tags:
            for elt in self.root.findall('.//{%s}%s' % (NS_XHTML, tag)):
                if not elt.text:
                    elt.text = ' '

    def serialize(self):
        self.protectEmptyElements('script', 'div', 'textarea')

        out = StringIO()
        self.tree.write(out, default_namespace=NS_XHTML)
        return out.getvalue()

    @classmethod
    def dumpElement(self, elt):
        tree = ET.ElementTree(elt)
        out = StringIO()
        tree.write(out, default_namespace=NS_XHTML)
        return out.getvalue()
