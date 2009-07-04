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

"""Two phase engines process the merging of dynamical content in two phases.

The first phase outputs the whole page, with portlets and main content (or
other fragmets) replaced by inclusion markers. It is typically implemented as
a pure XML manipulation. Therefore, the inclusion marker has to be a
self-closing XML tag.

The second phase replaces the inclusion markers by the actual content.

The main motivation, is that the engine has no control of the dynamical
content. There is therefore no guarantee that this would be valid XML.
Even so, the parsing of these fragments is a major liability for the robustness
of the system. Moreover, performance-wise, the cost of XML parsing
and serialization of the dynamical content isn't justified by any XML
manipulation.

This module provides a mixin class with helpers for the final serialization and
creation of inclusion marker tags.

See etreeengine.TwoPhaseElementTreeEngine for an example usage.
"""
import re

class TwoPhaseEngine(object):
    """Mixin class for two phase theme engines."""

    fragment_inclusion_marker = 'CPSDesignerThemes-postponed'

    fragment_re = re.compile(r'<%s>(\d+)</%s>' % (fragment_inclusion_marker,
                                                  fragment_inclusion_marker))

    def computeInclusionMarker(self, fragment):
        """Provide the name of tag to use and store the fragment."""
        postponed = getattr(self, 'postponed_inclusions', None)
        if postponed is None:
            postponed = self.postponed_inclusions = []

        index = len(postponed)
        postponed.append(fragment)
        return self.makeSimpleElement(self.fragment_inclusion_marker,
                                      content=str(index))

    def appendFragment(self, elt, fragment, is_element=False):
        elt.append(self.computeInclusionMarker(fragment))

    def insertFragment(self, index, elt, fragment, is_element=False):
        elt.insert(index, self.computeInclusionMarker(fragment))

    def _doIncludeForMatch(self, match_obj):
        """Perform the inclusion from a regexp match object."""
        return self.postponed_inclusions[int(match_obj.group(1))]

    def secondPhase(self, first_output):
        """Perform the inclusion of all postponed fragments."""
        return self.fragment_re.sub(self._doIncludeForMatch, first_output)

    def dumpElement(self, elt):
        return self.secondPhase(super(TwoPhaseEngine, self).dumpElement(elt))

    def serialize(self):
        return self.secondPhase(super(TwoPhaseEngine, self).serialize())
