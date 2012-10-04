# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005-2012 Async Open Source <http://www.async.com.br>
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
## Author(s): Stoq Team <stoq-devel@async.com.br>
##
""" Editors definitions for sellable"""

import sys

import gtk
from kiwi.currency import currency
from kiwi.datatypes import ValidationError
from kiwi.ui.forms import PercentageField, TextField
from kiwi.ui.objectlist import Column
from stoqdrivers.enum import TaxType, UnitType

from stoqlib.api import api
from stoqlib.database.exceptions import IntegrityError
from stoqlib.domain.fiscal import CfopData
from stoqlib.domain.person import ClientCategory
from stoqlib.domain.sellable import (SellableCategory, Sellable,
                                     SellableUnit,
                                     SellableTaxConstant,
                                     ClientCategoryPrice)
from stoqlib.gui.base.dialogs import run_dialog
from stoqlib.gui.base.lists import ModelListDialog, ModelListSlave
from stoqlib.gui.databaseform import DatabaseForm
from stoqlib.gui.editors.baseeditor import (BaseEditor,
                                            BaseRelationshipEditorSlave)
from stoqlib.gui.editors.categoryeditor import SellableCategoryEditor
from stoqlib.gui.slaves.commissionslave import CommissionSlave
from stoqlib.gui.slaves.sellableslave import OnSaleInfoSlave
from stoqlib.lib.message import info, yesno, warning
from stoqlib.lib.parameters import sysparam
from stoqlib.lib.translation import stoqlib_gettext
from stoqlib.lib.formatters import get_price_format_str, get_formatted_cost

_ = stoqlib_gettext

_DEMO_BAR_CODES = ['2368694135945', '6234564656756', '6985413595971',
                   '2692149835416', '1595843695465', '8596458216412',
                   '9586249534513', '7826592136954', '5892458629421',
                   '1598756984265', '1598756984265', '']
_DEMO_PRODUCT_LIMIT = 30

#
# Editors
#


class SellableTaxConstantEditor(BaseEditor):
    model_type = SellableTaxConstant
    model_name = _('Taxes and Tax rates')

    fields = dict(
        description=TextField(_('Name'), proxy=True, mandatory=True),
        tax_value=PercentageField(_('Value'), proxy=True, mandatory=True),
        )

    #
    # BaseEditor
    #

    def create_model(self, conn):
        return SellableTaxConstant(tax_type=int(TaxType.CUSTOM),
                                   tax_value=None,
                                   description=u'',
                                   connection=conn)


class SellableTaxConstantsListSlave(ModelListSlave):
    model_type = SellableTaxConstant
    editor_class = SellableTaxConstantEditor
    columns = [
        Column('description', _('Description'), data_type=str, expand=True),
        Column('value', _('Tax rate'), data_type=str, width=150),
    ]

    def selection_changed(self, constant):
        if constant is None:
            return
        is_custom = constant.tax_type == TaxType.CUSTOM
        self.listcontainer.remove_button.set_sensitive(is_custom)
        self.listcontainer.edit_button.set_sensitive(is_custom)

    def delete_model(self, model, trans):
        sellables = Sellable.selectBy(tax_constant=model, connection=trans)
        quantity = sellables.count()
        if quantity > 0:
            msg = _(u"You can't remove this tax, since %d products or "
                    "services are taxed with '%s'.") % (
                    quantity, model.get_description())
            info(msg)
        else:
            SellableTaxConstant.delete(model.id, connection=trans)

    def run_editor(self, trans, model):
        if model and model.tax_type != TaxType.CUSTOM:
            return
        return run_dialog(self.editor_class, conn=trans, model=model)


class SellableTaxConstantsDialog(ModelListDialog):
    list_slave_class = SellableTaxConstantsListSlave
    size = (500, 300)
    title = _("Taxes")


class BasePriceEditor(BaseEditor):
    gladefile = 'SellablePriceEditor'
    proxy_widgets = ('cost', 'markup', 'max_discount', 'price')

    def set_widget_formats(self):
        widgets = (self.markup, self.max_discount)
        for widget in widgets:
            widget.set_data_format(get_price_format_str())

    #
    # BaseEditor hooks
    #

    def get_title(self, *args):
        return _('Price settings')

    def setup_proxies(self):
        self.set_widget_formats()
        self.main_proxy = self.add_proxy(self.model, self.proxy_widgets)
        if self.model.markup is not None:
            return
        sellable = self.model.sellable
        self.model.markup = sellable.get_suggested_markup()
        self.main_proxy.update('markup')

    #
    # Kiwi handlers
    #

    def on_price__validate(self, entry, value):
        if value <= 0:
            return ValidationError(_("Price cannot be zero or negative"))

    def after_price__content_changed(self, entry_box):
        self.handler_block(self.markup, 'changed')
        self.main_proxy.update("markup")
        self.handler_unblock(self.markup, 'changed')

    def after_markup__content_changed(self, spin_button):
        self.handler_block(self.price, 'changed')
        self.main_proxy.update("price")
        self.handler_unblock(self.price, 'changed')


class SellablePriceEditor(BasePriceEditor):
    model_name = _(u'Product Price')
    model_type = Sellable

    def setup_slaves(self):
        slave = OnSaleInfoSlave(self.conn, self.model)
        self.attach_slave('on_sale_holder', slave)

        commission_slave = CommissionSlave(self.conn, self.model)
        self.attach_slave('on_commission_data_holder', commission_slave)
        if self.model.category:
            desc = self.model.category.description
            label = _('Calculate Commission From: %s') % desc
            commission_slave.change_label(label)


class CategoryPriceEditor(BasePriceEditor):
    model_name = _(u'Category Price')
    model_type = ClientCategoryPrice
    sellable_widgets = ('cost', )
    proxy_widgets = ('markup', 'max_discount', 'price')

    def setup_proxies(self):
        self.sellable_proxy = self.add_proxy(self.model.sellable,
                                             self.sellable_widgets)
        BasePriceEditor.setup_proxies(self)


#
# Slaves
#

class CategoryPriceSlave(BaseRelationshipEditorSlave):
    """A slave for changing the suppliers for a product.
    """
    target_name = _(u'Category')
    editor = CategoryPriceEditor
    model_type = ClientCategoryPrice

    def __init__(self, conn, sellable, visual_mode=False):
        self._sellable = sellable
        BaseRelationshipEditorSlave.__init__(self, conn, visual_mode=visual_mode)

    def get_targets(self):
        cats = ClientCategory.select(connection=self.conn).orderBy('name')
        return [(c.get_description(), c) for c in cats]

    def get_relations(self):
        return self._sellable.get_category_prices()

    def _format_markup(self, obj):
        return '%0.2f%%' % obj

    def get_columns(self):
        return [Column('category_name', title=_(u'Category'),
                       data_type=str, expand=True, sorted=True),
                Column('price', title=_(u'Price'), data_type=currency,
                       format_func=get_formatted_cost, width=150),
                Column('markup', title=_(u'Markup'), data_type=str,
                       width=100, format_func=self._format_markup),
                        ]

    def create_model(self):
        sellable = self._sellable
        category = self.target_combo.get_selected_data()

        if sellable.get_category_price_info(category):
            product_desc = sellable.get_description()
            info(_(u'%s already have a price for category %s') % (product_desc,
                                                      category.get_description()))
            return

        model = ClientCategoryPrice(sellable=sellable,
                                    category=category,
                                    price=sellable.price,
                                    max_discount=sellable.max_discount,
                                    connection=self.conn)
        return model


#
# Editors
#


class SellableEditor(BaseEditor):
    """This is a base class for ProductEditor and ServiceEditor and should
    be used when editing sellable objects. Note that sellable objects
    are instances inherited by Sellable."""

    # This must be be properly defined in the child classes
    model_name = None
    model_type = None

    gladefile = 'SellableEditor'
    confirm_widgets = ['description', 'cost', 'price']
    ui_form_name = None
    sellable_tax_widgets = ('tax_constant', 'tax_value', )
    sellable_widgets = ('code',
                        'barcode',
                        'description',
                        'category_combo',
                        'cost',
                        'price',
                        'statuses_combo',
                        'default_sale_cfop',
                        'unit_combo')
    proxy_widgets = (sellable_tax_widgets + sellable_widgets)

    def __init__(self, conn, model=None, visual_mode=False):
        is_new = not model
        self._sellable = None
        self._demo_mode = sysparam(conn).DEMO_MODE
        self._requires_weighing_text = (
            "<b>%s</b>" % api.escape(_("This unit type requires weighing")))

        if self.ui_form_name:
            self.db_form = DatabaseForm(conn, self.ui_form_name)
        else:
            self.db_form = None
        BaseEditor.__init__(self, conn, model, visual_mode)
        self.enable_window_controls()
        if self._demo_mode:
            self._add_demo_warning()

        # code suggestion
        edit_code_product = sysparam(self.conn).EDIT_CODE_PRODUCT
        self.code.set_sensitive(not edit_code_product and not self.visual_mode)
        if not self.code.read():
            code = u'%d' % self._sellable.id
            self.code.update(code)

        self.description.grab_focus()
        self.table.set_focus_chain([self.code,
                                    self.barcode,
                                    self.default_sale_cfop,
                                    self.description,
                                    self.cost_hbox,
                                    self.price_hbox,
                                    self.consignment_box,
                                    self.statuses_combo,
                                    self.category_combo,
                                    self.tax_hbox,
                                    self.unit_combo,
                                    ])
        self.setup_widgets()

        if not is_new and not self.visual_mode:
            if self._sellable.is_closed():
                self._add_reopen_button()
            elif self._sellable.can_close():
                self._add_close_button()

            if self._sellable.can_remove():
                self._add_delete_button()

        self.set_main_tab_label(self.model_name)
        price_slave = CategoryPriceSlave(self.conn, self.model.sellable,
                                         self.visual_mode)
        self.add_extra_tab(_(u'Category Prices'), price_slave)
        self._setup_ui_forms()

    def _add_demo_warning(self):
        self.set_message(
            _("This is a demostration mode of Stoq, you cannot create more than %d products.\n"
              "To avoid this limitation, enable production mode.") % (
            _DEMO_PRODUCT_LIMIT))
        if Sellable.select(connection=self.conn).count() > _DEMO_PRODUCT_LIMIT:
            self.disable_ok()

    def _add_extra_button(self, label, stock=None,
                          callback_func=None, connect_on='clicked'):
        button = self.add_button(label, stock)
        if callback_func:
            button.connect(connect_on, callback_func, label)

    def _add_delete_button(self):
        self._add_extra_button(_('Remove'), gtk.STOCK_DELETE,
                               self._on_delete_button__clicked)

    def _add_close_button(self):
        if self._sellable.product:
            label = _('Close Product')
        else:
            label = _('Close Service')

        self._add_extra_button(label, None,
                               self._on_close_sellable_button__clicked)

    def _add_reopen_button(self):
        if self._sellable.product:
            label = _('Reopen Product')
        else:
            label = _('Reopen Service')

        self._add_extra_button(label, None,
                               self._on_reopen_sellable_button__clicked)

    def _setup_ui_forms(self):
        if not self.db_form:
            return

        self.db_form.update_widget(self.code, other=self.code_lbl)
        self.db_form.update_widget(self.barcode, other=self.barcode_lbl)
        self.db_form.update_widget(self.category_combo,
                                   other=self.category_lbl)

    #
    #  Public API
    #

    def set_main_tab_label(self, tabname):
        self.sellable_notebook.set_tab_label(self.sellable_tab,
                                             gtk.Label(tabname))

    def add_extra_tab(self, tabname, tabslave):
        self.sellable_notebook.set_show_tabs(True)
        self.sellable_notebook.set_show_border(True)

        event_box = gtk.EventBox()
        event_box.show()
        self.sellable_notebook.append_page(event_box, gtk.Label(tabname))
        self.attach_slave(tabname, tabslave, event_box)

    def set_widget_formats(self):
        for widget in (self.cost, self.price):
            widget.set_adjustment(gtk.Adjustment(lower=0, upper=sys.maxint,
                                                 step_incr=1))
        self.requires_weighing_label.set_size("small")
        self.requires_weighing_label.set_text("")
        self.status_unavailable_label.set_size("small")
        self.status_unavailable_label.set_text("")

    def edit_sale_price(self):
        sellable = self.model.sellable
        result = run_dialog(SellablePriceEditor, self, self.conn, sellable)
        if result:
            self.sellable_proxy.update('price')

    def setup_widgets(self):
        raise NotImplementedError

    def update_requires_weighing_label(self):
        unit = self._sellable.unit
        if unit and unit.unit_index == UnitType.WEIGHT:
            self.requires_weighing_label.set_text(self._requires_weighing_text)
        else:
            self.requires_weighing_label.set_text("")

    def _update_tax_value(self):
        if not hasattr(self, 'tax_proxy'):
            return
        self.tax_proxy.update('tax_constant.tax_value')

    def get_taxes(self):
        """Subclasses may override this method to provide a custom
        tax selection.

        :returns: a list of tuples containing the tax description and a
            :class:`stoqlib.domain.sellable.SellableTaxConstant` object.
        """
        return []

    def _fill_categories(self):
        categories = SellableCategory.select(connection=self.conn)
        self.category_combo.prefill(api.for_combo(categories,
                                                  attr='full_description'))

    #
    # BaseEditor hooks
    #

    def update_visual_mode(self):
        self.add_category.set_sensitive(False)
        self.sale_price_button.set_sensitive(False)

    def setup_sellable_combos(self):
        self._fill_categories()
        self.edit_category.set_sensitive(False)

        self.statuses_combo.prefill(
                    [(v, k) for k, v in Sellable.statuses.items()])
        self.statuses_combo.set_sensitive(False)

        cfops = CfopData.select(connection=self.conn)
        self.default_sale_cfop.prefill(api.for_combo(cfops, empty=''))

        self.setup_unit_combo()

    def setup_unit_combo(self):
        units = SellableUnit.select(connection=self.conn)
        self.unit_combo.prefill(api.for_combo(units, empty=_('No units')))

    def setup_tax_constants(self):
        taxes = self.get_taxes()
        self.tax_constant.prefill(taxes)

    def setup_proxies(self):
        self.set_widget_formats()
        self._sellable = self.model.sellable

        self.add_category.set_tooltip_text(_("Add a new category"))
        self.edit_category.set_tooltip_text(_("Edit the selected category"))
        self.setup_sellable_combos()
        self.setup_tax_constants()
        self.tax_proxy = self.add_proxy(self._sellable,
                                        SellableEditor.sellable_tax_widgets)

        self.sellable_proxy = self.add_proxy(self._sellable,
                                             SellableEditor.sellable_widgets)

        self.update_requires_weighing_label()

    def _run_category_editor(self, category=None):
        # Editing this in a new transaction is causing a deadlock
        model = run_dialog(SellableCategoryEditor, self, self.conn, category)
        if model:
            self._fill_categories()
            self.category_combo.select(model)
    #
    # Kiwi handlers
    #

    def _on_delete_button__clicked(self, button, parent_button_label=None):
        sellable_description = self._sellable.get_description()
        msg = (_("This will delete '%s' from the database. Are you sure?")
                 % sellable_description)
        if not yesno(msg, gtk.RESPONSE_NO, _("Delete"), _("Keep")):
            return

        try:
            self._sellable.remove()
        except IntegrityError, details:
            warning(_("It was not possible to remove '%s'")
                      % sellable_description, str(details))
            return

        self.confirm()

    def _on_close_sellable_button__clicked(self, button,
                                           parent_button_label=None):
        msg = (_("Do you really want to close '%s'?\n"
                 "Please note that when it's closed, you won't be able to "
                 "commercialize it anymore.")
                 % self._sellable.get_description())
        if not yesno(msg, gtk.RESPONSE_NO,
                      parent_button_label, _("Don't close")):
            return

        self._sellable.close()
        self.confirm()

    def _on_reopen_sellable_button__clicked(self, button,
                                            parent_button_label=None):
        msg = (_("Do you really want to reopen '%s'?\n"
                 "Note that when it's opened, you will be able to "
                 "commercialize it again.") % self._sellable.get_description())
        if not yesno(msg, gtk.RESPONSE_NO,
                     parent_button_label, _("Keep closed")):
            return

        self._sellable.set_unavailable()
        self.confirm()

    def on_category_combo__content_changed(self, category):
        self.edit_category.set_sensitive(bool(category.get_selected()))

    def on_tax_constant__changed(self, combo):
        self._update_tax_value()

    def on_unit_combo__changed(self, combo):
        self.update_requires_weighing_label()

    def on_sale_price_button__clicked(self, button):
        self.edit_sale_price()

    def on_add_category__clicked(self, widget):
        self._run_category_editor()

    def on_edit_category__clicked(self, widget):
        self._run_category_editor(self.category_combo.get_selected())

    def on_code__validate(self, widget, value):
        if not value:
            return ValidationError(_(u'The code can not be empty.'))
        if self.model.sellable.check_code_exists(value):
            return ValidationError(_(u'The code %s already exists.') % value)

    def on_barcode__validate(self, widget, value):
        if not value:
            return
        if value and len(value) > 14:
            return ValidationError(_(u'Barcode must have 14 digits or less.'))
        if self.model.sellable.check_barcode_exists(value):
            return ValidationError(_('The barcode %s already exists') % value)
        if self._demo_mode and value not in _DEMO_BAR_CODES:
            return ValidationError(_("Cannot create new barcodes in "
                                     "demonstration mode"))

    def on_price__validate(self, entry, value):
        if value <= 0:
            return ValidationError(_("Price cannot be zero or negative"))

    def on_cost__validate(self, entry, value):
        if value <= 0:
            return ValidationError(_("Cost cannot be zero or negative"))


def test_sellable_tax_constant():  # pragma nocover
    ec = api.prepare_test()
    tax_constant = api.sysparam(ec.trans).DEFAULT_PRODUCT_TAX_CONSTANT
    run_dialog(SellableTaxConstantEditor,
                       parent=None, conn=ec.trans, model=tax_constant)
    print tax_constant


if __name__ == '__main__':  # pragma nocover
    test_sellable_tax_constant()
