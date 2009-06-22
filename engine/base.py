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

from Products.CPSDesignerThemes.interfaces import IThemeEngine
from Products.CPSDesignerThemes.constants import NS_URI, ENCODING
from Products.CPSDesignerThemes.utils import rewrite_uri

METAL_HEAD_SLOTS = ( # the passed slots that end up in the <head> element
    'base', 'head_slot', 'style_slot', 'javascript_head_slot')

LINK_HTML_DOCUMENTS = {'img' : 'src',
                       'link'    : 'href',
                       'object'  : 'data',
                       'param' : 'value',
                       }

def find_by_attribute(elt, attr_name, value=None):
    """For subclass."""

    raise NotImplementedError

class BaseEngine(object):
    """Abstract base engine class

    All calls to XML libraries should be done from subclasses (engine actual
    implementations).
    Conversely, all CPS calls should come from here. An immediate benefit is
    that the subclasses can be tested with plain old unittest.
    """

    implements(IThemeEngine)

    logger = logging.getLogger(
        'Products.CPSDesignerThemes.engine.BaseEngine')

    XML_HEADER = '<?xml version="1.0" encoding="%s"?>' % ENCODING

    def __init__(self, theme_base_uri='', page_uri='', cps_base_url=None):
        """Subclasses accept another argument: theme xml source.

        When we'll cache xml parsing and URI rewriting, this constructor will
        take another argument, namely the preprocessed XML tree from cache
        """
        self.theme_base_uri = theme_base_uri
        self.page_uri = page_uri
        self.cps_base_url = cps_base_url
        self.rewriteUris()

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

        head_element, body_element = self.parseHeadBody(pt_output)

        head_content = '\n'.join((metal_slots.get(slot, '')
                                  for slot in METAL_HEAD_SLOTS))

        return self.render(main_content=metal_slots.get('main', ''),
                           head_content=head_content,
                           head_element=head_element,
                           body_element=body_element,
                           context=context, request=None)

    @classmethod
    def parseHeadBody(self, pt_output):
        """Return the head and body elements from an XML string fragment"""
        raise NotImplementedError

    @classmethod
    def parseFragment(self, content, enclosing=None):
        """Convert a string fragment to an xml tree

        If enclosing is None, it is assumed that the fragment has a root element
        otherwise one will be produced, as specified by 'enclosing'
        This is useful for some ZPT outputs.
        """
        raise NotImplementedError

    @classmethod
    def renderPortlets(self, portlets, context=None, request=None):
        return ( (portlet.title_or_id(),
                  portlet.render_cache(context_obj=context))
                for portlet in portlets)

    def render(self, main_content='', head_content='',
               body_element=None, head_element=None,
               context=None, request=None):
        """General rendering method.

        Supposed to be used for compat mode and direct mode."""

        ptool = getToolByName(context, 'portal_cpsportlets')

        # portlet slots
        for slot_name, slot_elt in self.extractSlotElements():
            portlets = ptool.getPortlets(context, slot_name)
            self.logger.debug('Rendering slot %s with portlets %s',
                              slot_name, portlets)
            frame_parent, frame = self.extractSlotFrame(slot_elt)
            rendered = self.renderPortlets(portlets,
                                           context=context, request=request)
            self.mergePortlets(frame_parent, frame, rendered)

        # isolated portlets (should appear mostly in CPSSkins exports)
        for ptl_id, elt in self.extractIsolatedPortletElements():
            portlet = ptool.getPortletById(ptl_id)
            frame_parent, frame = self.extractSlotFrame(elt)
            rendered = self.renderPortlets([portlet],
                                           context=context, request=request)
            self.mergePortlets(frame_parent, frame, rendered)

        if body_element is not None:
            self.mergeBodyElement(from_cps=body_element)
        if main_content:
            self.renderMainContent(main_content)
        self.mergeHeads(head_content=head_content,
                        cps_global=head_element)

        return self.serialize()

    def serialize(self):
        """Produce the final page to be sent over HTTP."""

    def extractSlotElements(self):
        """Return an iterable over pairs (slot name, slot xml element)
        Side effect: cleanup the slot element to make it xhtml compliant
        """
        raise NotImplementedError

    def extractIsolatedPortletsElements(self):
        """Return an iterable over pairs (slot name, slot xml element)
        Side effect: cleanup the slot element to make it xhtml compliant
        """
        raise NotImplementedError

    def mergeBodyElement(self, from_cps=None):
        """Merge the body element issued by CPS' ZPTs in the theme's

        This processes attributes only. Typically, these are onload, class, and
        style. Any attribute defined by the theme takes precedence.
        """
        raise NotImplementedError

    def mergeHeads(self, head_content='', cps_global=None):
        """Merge the contextual head_content with cps' global and the theme's.

        For now, this is stupid concatenation.
        TODO: this should:
          - respect a natural ordering, and in particular put all
            JS scripts towards the end,
          - actually merge cps_global with the theme's head (we should first
            define a policy about this).
        """
        raise NotImplementedError

    def renderMainContent(self, main_content):
        """Insert the main content where it should."""
        raise NotImplementedError

    @classmethod
    def extractSlotFrame(self, slot):
        """Find the frame part in the slot and remove it from the tree.

        Sibling frames (elements bearing 'cps:frame' attribute) are tolerated
        as a convenience for web designers wanting to check their output
        with several portlets TODO: move this to general doc."""

        raise NotImplementedError

    @classmethod
    def mergePortlets(self, frame_parent, frame, portlets_rendered):
        """Merge the portlets in their frame.

        portlets_rendered is a pair (title, body)
        frame's parent is passed because it's needed for frame repetition"""
        raise NotImplementedError

    @classmethod
    def dumpElement(self, elt):
        """Mostly Useful for unit tests"""
        raise NotImplementedError

