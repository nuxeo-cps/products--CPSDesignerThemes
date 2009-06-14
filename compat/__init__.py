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

"""This module provides compatibility for old page templates.

Namely, it makes it possible for ZPTs to be based on invocation of the
'master' macro that normally sits in
CPSDefault/skins/cps_default/content_lib_master.pt
and still workk with CPSDesigner themes.

It does this currently by using an altered TAL interpretor that turns
'metal:fill-slot' calls into recorders.
The slot contents are in turn fed to the themes machinery instead of being
streamlined right away. This works for first level fill-slots that occur
within a metal:slot-recorder tag and a special version of 'master' leveraging
that. It is very unlikely that another macro could be affected expect on
purpose.

Later Zope versions could be supported in a different way.
This module's contract includes to choose the right compatibility method
given the environment, so that ensuring compatibility is done by importing
it (and possibly a profile) and forget about it.
"""

import patchzpts
