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

from TAL.TALInterpreter import TALInterpreter

METAL_SLOT_RECORDER = 'metal:slot-recorder'

class TALSlotRecordingInterpreter(TALInterpreter):
    """A variant on the TAL interpreter that's able to record slot contents.

    Usage: use <metal:slot-recorder> to define the macro.
    for macro definition. When the interpreter processes a call to that macro,
    the contents of fill-slot calls will be recorded and not dumped in the
    output.

    Limitations: behaviour in case in case the macro is called more
    than once in a page template is not specified.
    """

    bytecode_handlers = TALInterpreter.bytecode_handlers.copy()
    bytecode_handlers_tal = TALInterpreter.bytecode_handlers_tal.copy()

    def __init__(self, *args, **kwargs):
        TALInterpreter.__init__(self, *args, **kwargs)
        self._slots_recorded = None
        self.slot_record_level = -1 # initially disabled
        self._current_slot = None

    def getRecordedSlots(self):
        """Return what's been recorded in the slots.

        None means that no <metal:slot-recorder> has been met.
        """
        return self._slots_recorded

    def do_startTag(self, (name, attrList),
                        end=">", endlen=1, _len=len):
        if name.startswith(METAL_SLOT_RECORDER):

            # Level of record specified in the tag name or by value
            level_s = name[len(METAL_SLOT_RECORDER):]
            if level_s:
                srl_offset = int(level_s)
            else:
                srl_offset = 1
            self.slot_record_level = self.level + srl_offset

            self._current_slot = None
            if self._slots_recorded is None:
                self._slots_recorded = {}
        else:
            sll = self.slot_record_level
            if self._current_slot is None and sll != -1 and sll == self.level:
                for attr, v, atype in attrList:
                    if attr in ('metal:fill-slot', 'fill-slot'):
                        self.pushStream(self.StringIO())
                        self._current_slot = v
                        break
        TALInterpreter.do_startTag(self, (name, attrList),
                                   end=end, endlen=endlen, _len=_len)
    bytecode_handlers['startTag'] = do_startTag
    bytecode_handlers_tal['startTag'] = do_startTag

    def triggerSlotsRecording(self, d, attrList=None):
        """Starts slots recording if appropriate."""
        sll = self.slot_record_level
        if self._current_slot is None and sll == -1 or sll != self.level:
            return

        slot = d.get('fill-slot') or d.get('metal:fill-slot')

        if slot:
            self.pushStream(self.StringIO())
            self._current_slot = slot

    def do_beginScope(self, d):
        self.triggerSlotsRecording(d)
        TALInterpreter.do_beginScope(self, d)
    bytecode_handlers['beginScope'] = do_beginScope

    def do_beginScope_tal(self, d):
        self.triggerSlotsRecording(d)
        TALInterpreter.do_beginScope_tal(self, d)
    bytecode_handlers_tal['beginScope'] = do_beginScope_tal

    def interpret(self, program):
        TALInterpreter.interpret(self, program)
        if self.level == self.slot_record_level - 1 and \
               self._current_slot is not None:
            self._slots_recorded[self._current_slot] = self.stream.getvalue()
            self._current_slot = None
            self.popStream()

        if self.level < self.slot_record_level - 1:
            # end of recording, disabling
            self.scope_record_level = -1


