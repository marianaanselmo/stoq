# -*- Mode: Python; coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005-2012 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##
""" Main gui definition for inventory application. """

import datetime

import gtk
from kiwi.ui.objectlist import Column

from stoqlib.api import api
from stoqlib.domain.inventory import Inventory
from stoqlib.domain.person import Branch
from stoqlib.domain.product import ProductStockItem
from stoqlib.enums import SearchFilterPosition
from stoqlib.exceptions import DatabaseInconsistency
from stoqlib.gui.columns import IdentifierColumn, SearchColumn
from stoqlib.gui.dialogs.openinventorydialog import OpenInventoryDialog
from stoqlib.gui.dialogs.productadjustmentdialog import ProductsAdjustmentDialog
from stoqlib.gui.dialogs.productcountingdialog import ProductCountingDialog
from stoqlib.gui.keybindings import get_accels
from stoqlib.gui.search.searchfilters import ComboSearchFilter
from stoqlib.lib.message import warning, yesno
from stoqlib.lib.translation import stoqlib_gettext as _
from stoqlib.reporting.product import ProductCountingReport
from stoqlib.reporting.inventory import InventoryReport

from stoq.gui.shell.shellapp import ShellApp


class InventoryApp(ShellApp):

    # TODO: Change all widget.set_sensitive to self.set_sensitive([widget])

    app_title = _('Inventory')
    gladefile = "inventory"
    search_spec = Inventory
    search_labels = _('Matching:')
    report_table = InventoryReport

    #
    # Application
    #

    def create_actions(self):
        group = get_accels('app.inventory')
        actions = [
            # File
            ('NewInventory', None, _('Inventory...'),
             group.get('new_inventory'),
             _('Create a new inventory for product counting')),

            # Inventory
            ('InventoryMenu', None, _('Inventory')),
            ('CountingAction', gtk.STOCK_INDEX, _('_Count...'),
             group.get('inventory_count'),
             _('Register the actual stock of products in the selected '
               'inventory')),
            ('AdjustAction', gtk.STOCK_CONVERT, _('_Adjust...'),
             group.get('inventory_adjust'),
             _('Adjust the stock accordingly to the counting in the selected '
               'inventory')),
            ('Cancel', gtk.STOCK_CANCEL, _('Cancel...'),
             group.get('inventory_cancel'),
             _('Cancel the selected inventory')),
            ('PrintProductListing', gtk.STOCK_PRINT,
             _('Print product listing...'),
             group.get('inventory_print'),
             _('Print the product listing for this inventory'))
        ]
        self.inventory_ui = self.add_ui_actions('', actions,
                                                filename='inventory.xml')
        self.set_help_section(_("Inventory help"), 'app-inventory')

        self.AdjustAction.set_short_label(_("Adjust"))
        self.CountingAction.set_short_label(_("Count"))
        self.Cancel.set_short_label(_("Cancel"))
        self.AdjustAction.props.is_important = True
        self.CountingAction.props.is_important = True
        self.Cancel.props.is_important = True

    def create_ui(self):
        self.popup = self.uimanager.get_widget('/InventorySelection')

        self.window.add_new_items([self.NewInventory])
        self.window.Print.set_tooltip(
            _("Print a report of these inventories"))

    def activate(self, params):
        # Avoid letting this sensitive if has-rows is never emitted
        self.search.refresh()
        self._update_widgets()
        self.window.SearchToolItem.set_sensitive(False)

    def deactivate(self):
        self.uimanager.remove_ui(self.inventory_ui)
        self.window.SearchToolItem.set_sensitive(True)

    def new_activate(self):
        if not self.NewInventory.get_sensitive():
            warning(_("You cannot open an inventory without having a "
                      "branch with stock in it."))
            return
        self._open_inventory()

    def create_filters(self):
        # Disable string search right now, until we use a proper Viewable
        # for this application
        self.search.disable_search_entry()
        self.branch_filter = ComboSearchFilter(
            _('Show inventories at:'), self._get_branches_for_filter())
        self.add_filter(self.branch_filter,
                        position=SearchFilterPosition.TOP,
                        columns=["branch_id"])

    def get_columns(self):
        return [IdentifierColumn('identifier', title=_('Code'),
                                 sorted=True, order=gtk.SORT_DESCENDING),
                SearchColumn('status_str', title=_('Status'),
                             data_type=str, width=100,
                             valid_values=self._get_status_values(),
                             search_attribute='status'),
                Column('branch.person.name', title=_('Branch'),
                       data_type=str, expand=True),
                SearchColumn('open_date', title=_('Opened'),
                             long_title=_('Date Opened'),
                             data_type=datetime.date, width=120),
                SearchColumn('close_date', title=_('Closed'),
                             long_title=_('Date Closed'),
                             data_type=datetime.date, width=120)]

    #
    # Private API
    #

    def _get_status_values(self):
        values = [(v, k) for k, v in Inventory.statuses.items()]
        values.insert(0, (_("Any"), None))
        return values

    def _get_branches(self):
        return self.store.find(Branch)

    def _get_branches_for_filter(self):
        items = [(b.person.name, b.id) for b in self._get_branches()]
        if not items:
            raise DatabaseInconsistency('You should have at least one '
                                        'branch on your database.'
                                        'Found zero')
        items.insert(0, [_('All branches'), None])
        return items

    def _update_widgets(self):
        has_open = False
        all_counted = False
        has_adjusted = False
        selected = self.results.get_selected()
        if selected:
            all_counted = selected.all_items_counted()
            has_open = selected.is_open()
            has_adjusted = selected.has_adjusted_items()

        self.set_sensitive([self.PrintProductListing], bool(selected))
        self.set_sensitive([self.Cancel], has_open and not has_adjusted)
        self.set_sensitive([self.NewInventory], self._can_open())
        self.set_sensitive([self.CountingAction], has_open)
        self.set_sensitive([self.AdjustAction], has_open and all_counted)
        self.window.set_new_menu_sensitive(self._can_open())

    def _get_available_branches_to_inventory(self):
        """Returns a list of branches where we can open an inventory.
        Note that we can open a inventory if:
            - There's no inventory opened yet (in the same branch)
            - The branch must have some stock
        """
        available_branches = []
        for branch in self._get_branches():
            has_open_inventory = Inventory.has_open(self.store, branch)
            if not has_open_inventory:
                stock = self.store.find(ProductStockItem, branch=branch)
                if stock.count() > 0:
                    available_branches.append(branch)

        return available_branches

    def _can_open(self):
        # we can open an inventory if we have at least one branch
        # available
        return bool(self._get_available_branches_to_inventory())

    def _open_inventory(self):
        store = api.new_store()
        branches = self._get_available_branches_to_inventory()
        model = self.run_dialog(OpenInventoryDialog, store, branches)
        store.confirm(model)
        store.close()
        self.refresh()
        self._update_widgets()

    def _cancel_inventory(self):
        if not yesno(_('Are you sure you want to cancel this inventory ?'),
                     gtk.RESPONSE_NO, _("Cancel inventory"), _("Don't cancel")):
            return

        store = api.new_store()
        inventory = store.fetch(self.results.get_selected())
        inventory.cancel()
        store.commit()
        store.close()
        self.refresh()
        self._update_widgets()

    def _register_product_counting(self):
        store = api.new_store()
        inventory = store.fetch(self.results.get_selected())
        model = self.run_dialog(ProductCountingDialog, store, inventory)
        store.confirm(model)
        store.close()
        self.refresh()
        self._update_widgets()

    def _adjust_product_quantities(self):
        store = api.new_store()
        inventory = store.fetch(self.results.get_selected())
        model = self.run_dialog(ProductsAdjustmentDialog, store, inventory)
        store.confirm(model)
        store.close()
        self.refresh()
        self._update_widgets()

    def _update_filter_slave(self, slave):
        self.refresh()

    def _get_sellables_by_inventory(self, inventory):
        for item in inventory.get_items():
            yield item.product.sellable

    #
    # Callbacks
    #

    def on_NewInventory__activate(self, action):
        self._open_inventory()

    def on_CountingAction__activate(self, action):
        self._register_product_counting()

    def on_AdjustAction__activate(self, action):
        self._adjust_product_quantities()

    def on_results__selection_changed(self, results, product):
        self._update_widgets()

    def on_results__right_click(self, results, result, event):
        self.popup.popup(None, None, None, event.button, event.time)

    def on_Cancel__activate(self, widget):
        self._cancel_inventory()

    def on_PrintProductListing__activate(self, button):
        selected = self.results.get_selected()
        sellables = list(self._get_sellables_by_inventory(selected))
        if not sellables:
            warning(_("No products found in the inventory."))
            return
        self.print_report(ProductCountingReport, sellables)
