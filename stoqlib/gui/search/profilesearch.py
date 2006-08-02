# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005, 2006 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Bruno Rafael Garcia           <brg@async.com.br>
##
##
""" Search dialogs for profile objects """

from kiwi.ui.widgets.list import Column

from stoqlib.lib.translation import stoqlib_gettext
from stoqlib.gui.base.search import SearchEditor
from stoqlib.domain.profile import UserProfile
from stoqlib.gui.editors.profileeditor import UserProfileEditor
from stoqlib.gui.base.dialogs import run_dialog


_ = stoqlib_gettext


class UserProfileSearch(SearchEditor):
    title = _("User Profile Search")
    table = UserProfile
    editor_class = UserProfileEditor
    size = (465, 390)

    def __init__(self, conn):
        SearchEditor.__init__(self, conn, self.table, self.editor_class,
                              title=self.title)
        self._setup_widgets()

    def _setup_widgets(self):
        self.set_searchbar_labels(_('Profiles Matching:'))
        self.set_result_strings(_('profile'), _('profiles'))

    #
    # SearchDialog Hooks
    #

    def get_columns(self):
        return [Column('name', _('Profile'), data_type=str, sorted=True)]

    def run_editor(self, obj):
        return run_dialog(self.editor_class, self, self.conn, obj)
