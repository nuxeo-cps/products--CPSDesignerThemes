# (C) Copyright 2008 Georges Racinet
#               2010 CPS-CMS Community <http://cps-cms.org/>
# Author: Georges Racinet <georges@racinet.fr>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
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

"""Intercept all page templates renderings to feed them to the themes engine.

In the current state of implementation, this still relies on the old location
of the PageTemplate package.
Another improvement would be to limit this systematic interception to those
templates for which it is meaningful, ie those that call a macro chain than
ends with the main template
"""

import re
from Products.PageTemplates.PageTemplate import PageTemplate
from Products.PageTemplates.PageTemplate import PTRuntimeError
from Products.PageTemplates.PageTemplate import PageTemplateTracebackSupplement
from Products.PageTemplates.Expressions import getEngine
from Products.CPSDesignerThemes.negociator import adapt

SLOTS_REGEXP=re.compile(r'<cps-designer-themes slot="(.*?)">(.*?)'
                        '</cps-designer-themes>', re.DOTALL)
STARTER_REGEXP = re.compile(r'\s*<cpsdesigner-themes-compat>')
ENDER = '</cpsdesigner-themes-compat>'

orig_pt_render = PageTemplate.pt_render

def slots_record(matchobj, slots):
    """Remove matches and record them in slots dict."""
    slots[matchobj.group(1)] = matchobj.group(2)
    return ''

def pt_render(self, *args, **kwargs):
    pt_output = orig_pt_render(self, *args, **kwargs)
    match = STARTER_REGEXP.match(pt_output)
    if match is None:
        return pt_output
    pt_output = pt_output[match.end():pt_output.rfind(ENDER)]

    slots = {}
    def record(matchobj):
        return slots_record(matchobj, slots)

    pt_output = SLOTS_REGEXP.sub(record, pt_output)
    if not slots:
        return pt_output

    c = self.pt_getContext()
    engine = adapt(c['context'], c['request'])
    return engine.renderCompat(metal_slots=slots,
                               pt_output=pt_output)

PageTemplate.pt_render = pt_render
