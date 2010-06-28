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

from Products.PageTemplates.PageTemplate import PageTemplate
from Products.PageTemplates.PageTemplate import PTRuntimeError
from Products.PageTemplates.PageTemplate import PageTemplateTracebackSupplement
from Products.PageTemplates.Expressions import getEngine
from Products.CPSDesignerThemes.negociator import adapt

from talslotrecorder import TALSlotRecordingInterpreter

def pt_render(self, source=0, extra_context={}):
    """Render this Page Template"""
    if not self._v_cooked:
        self._cook()

    __traceback_supplement__ = (PageTemplateTracebackSupplement, self)

    if self._v_errors:
        e = str(self._v_errors)
        raise PTRuntimeError, (
            'Page Template %s has errors: %s' % (self.id, e))
    output = self.StringIO()
    c = self.pt_getContext()
    c.update(extra_context)

    interp = TALSlotRecordingInterpreter(self._v_program, self._v_macros,
                                         getEngine().getContext(c),
                                         output,
                                         tal=not source, strictinsert=0)

    interp()

    slots = interp.getRecordedSlots()
    if slots is not None:
        # We're assuming the sole use of <metal:slot-recorder>
        # is to pass to the rendering theme engine
        engine = adapt(c['context'], c['request'])
        return engine.renderCompat(metal_slots=slots,
                                   pt_output=output.getvalue())

    return output.getvalue()


PageTemplate.pt_render = pt_render
