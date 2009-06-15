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

from zope.interface import implements

from Products.CMFCore.utils import getToolByName

from interfaces import IThemeEngine
from constants import NS_URI, ENCODING
from utils import rewrite_uri

try:
    import cElementTree as ET
except ImportError:
        import elementtree.ElementTree as ET

def ns_prefix(name):
    return '{%s}%s' % (NS_URI, name)

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

class ElementTreeEngine(object):
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
        self.theme_base_uri = theme_base_uri
        self.page_uri = page_uri

        self.rewriteUris()

    def rewriteUris(self):
        for tag, attr in LINK_HTML_DOCUMENTS.items():
            for elt in self.tree.findall('//%s' % tag):
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

    def renderCompat(self, metal_slots=None, pt_output='',
                     context=None, request=None):
        """Rendering method for compat mode.

        Receives the what the callers page templates of the main_template's
        master macro have put in the slots, and the main output of said macro.

        pt_output is supposed to be xml looking like this:
          <cpsdesigner-themes-compat>
            <head>...</head>
            <body onload="..."/>
          </cpsdesigner-themes-compat>

        This is used to reproduced what CPSSkins main template used to do
        (simplified extract):
          <head>
            <metal:block use-macro="here/header_lib_header/macros/header">
              <metal:block fill-slot="head_slot">
                <metal:block define-slot="head_slot"</metal:block>
              </metal:block>
            </metal:block>
          </head>

        The slot recording hack does not work for these nested macro calls,
        and it would be much trickier to do so.
        Therefore we have our main template render the part that's supposed to
        be called from there directly in the output, define the slots in the
        simplest manner near top level, and this method merges all of this."""

        parsed = self.parseFragment(pt_output)
        head_element = parsed.find('.//head')
        body_element = parsed.find('.//body')

        head_content = '\n'.join((metal_slots.get(slot, '')
                                  for slot in METAL_HEAD_SLOTS))

        return self.render(main_content=metal_slots.get('main', ''),
                           head_content=head_content,
                           head_element=head_element,
                           body_element=body_element,
                           context=context, request=None)


    @classmethod
    def parseFragment(self, content, enclosing='pt-slot'):
        # TODO GR: this works around the fact that entity support in
        # my ElementTree version doesn't work as advertised
        content = content.replace('&nbsp;', ' ')

        parser = ET.XMLParser()
        # TODO load all entities, and do it just once
        parser.entity['nbsp'] = unichr(160)
        parser.feed(self.XML_HEADER)
        parser.feed("<%s>" % enclosing)
        parser.feed(content)
        parser.feed("</%s>" % enclosing)
        try:
            return parser.close()
        except SyntaxError, e:
            self.logger.error("Problematic xml snippet:\n", content)

    def render(self, main_content='', head_content='',
               body_element=None, head_element=None,
               context=None, request=None):
        """General rendering method.

        Supposed to be used for compat mode and direct mode."""

        ptool = getToolByName(context, 'portal_cpsportlets')

        # portlet slots
        for slot in find_by_attribute(self.root, SLOT_ATTR):
            slot_name = slot.attrib.pop(SLOT_ATTR)
            portlets = ptool.getPortlets(context, slot_name)
            self.logger.debug('Rendering slot %s with portlets %s',
                              slot_name, portlets)
            frame_parent, frame = self.extractSlotFrame(slot)
            self.mergePortlets(frame_parent, frame, portlets)

        if body_element is not None:
            self.mergeBodyElement(from_cps=body_element)
        if main_content:
            self.renderMainContent(main_content)
        self.mergeHeads(head_content=head_content,
                        cps_global=head_element)

        # XXX hack avoiding the empty textarea and script traps (sigh)
        self.protectEmptyElements('textarea', 'script')

        out = StringIO()
        self.tree.write(out)
        return out.getvalue()

    def mergeBodyElement(self, from_cps=None):
        """Merge the body element issued by CPS' ZPTs in the theme's

        This processes attributes only. Typically, these are onload, class, and
        style. Any attribute defined by the theme takes precedence.
        """
        body = self.tree.find('//body')
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
        in_theme = self.tree.find('//head')
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

            body_elt = find_by_attribute(
                ptl_elt, PORTLET_ATTR, value='body').next()
            del body_elt.attrib[PORTLET_ATTR]
            body_elt.text = ''
            for child in body_elt:
                body_elt.remove(child)
            body_elt.append(ET.fromstring(
                self.XML_HEADER + portlet.render_cache()))

            frame_parent.append(ptl_elt)

    def protectEmptyElements(self, *tags):
        # maybe lxml can do this better
        # there's also a recent option in ElementTree, but not in my version
        for tag in tags:
            for elt in self.root.findall('.//%s' % tag):
                if not elt.text:
                    elt.text = ' '

