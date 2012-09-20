# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2012 Async Open Source <http://www.async.com.br>
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

import datetime

import mock

from stoqlib.gui.uitestutils import GUITest
from stoqlib.gui.wizards.salereturnwizard import SaleReturnWizard


class TestSaleReturnWizard(GUITest):
    def testCreate(self):
        sale = self.create_sale()
        self.add_product(sale)
        self.add_product(sale, quantity=2)
        self.add_payments(sale)
        sale.order()
        sale.confirm()
        returned_sale = sale.create_sale_return_adapter()
        SaleReturnWizard(self.trans, returned_sale)

        for item in returned_sale.returned_items:
            self.assertTrue(item.will_return)
            self.assertEqual(item.quantity, item.max_quantity)

    @mock.patch('stoqlib.gui.wizards.salereturnwizard.info')
    def testSaleReturnItemsStep(self, info):
        sale = self.create_sale()
        self.add_product(sale)
        self.add_product(sale, quantity=2)
        self.add_payments(sale)
        sale.order()
        sale.confirm()
        returned_sale = sale.create_sale_return_adapter()
        wizard = SaleReturnWizard(self.trans, returned_sale)
        step = wizard.get_current_step()
        objectlist = step.slave.klist

        def _reset_objectlist(objectlist):
            for item in objectlist:
                item.quantity = item.max_quantity
                item.will_return = bool(item.quantity)
                objectlist.update(item)

        self.check_wizard(wizard, 'wizard-sale-return-items-step')
        self.assertSensitive(wizard, ['next_button'])

        # If we don't have anything marked as will_return, wizard's
        # next_button should not be sensiive.
        for item in objectlist:
            item.will_return = False
            objectlist.update(item)
        step.force_validation()
        info.assert_called_once_with(
            "You need to have at least one item to return")
        self.assertNotSensitive(wizard, ['next_button'])

        _reset_objectlist(objectlist)
        step.force_validation()
        self.assertSensitive(wizard, ['next_button'])

        # If we don't have a quantity to return of anything, wizard's
        # next_button should not be sensiive.
        for item in objectlist:
            item.quantity = 0
            objectlist.update(item)
        step.force_validation()
        info.assert_called_once_with(
            "You need to have at least one item to return")
        self.assertNotSensitive(wizard, ['next_button'])

        _reset_objectlist(objectlist)
        step.force_validation()
        self.assertSensitive(wizard, ['next_button'])

        for item in objectlist:
            item.quantity = item.max_quantity + 1
            # If anything is marked to return with more than max_quantity
            # wizard's next_button should not be sensitive
            step.force_validation()
            self.assertNotSensitive(wizard, ['next_button'])
            _reset_objectlist(objectlist)

    def testSaleReturnInvoiceStep(self):
        sale = self.create_sale()
        self.add_product(sale)
        self.add_product(sale, quantity=2)
        self.add_payments(sale)
        sale.order()
        sale.confirm()
        returned_sale = sale.create_sale_return_adapter()
        wizard = SaleReturnWizard(self.trans, returned_sale)
        self.click(wizard.next_button)
        step = wizard.get_current_step()

        self.check_wizard(wizard, 'wizard-sale-return-invoice-step')
        self.assertNotSensitive(wizard, ['next_button'])

        self.assertInvalid(step, ['reason'])
        step.reason.update(
            "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed\n"
            "do eiusmod tempor incididunt ut labore et dolore magna aliqua.")
        self.assertValid(step, ['reason'])
        self.assertNotSensitive(wizard, ['next_button'])

        self.assertInvalid(step, ['invoice_number'])
        step.invoice_number.update(0)
        self.assertInvalid(step, ['invoice_number'])
        self.assertNotSensitive(wizard, ['next_button'])
        step.invoice_number.update(1000000000)
        self.assertInvalid(step, ['invoice_number'])
        self.assertNotSensitive(wizard, ['next_button'])
        step.invoice_number.update(1)
        self.assertValid(step, ['invoice_number'])
        self.assertSensitive(wizard, ['next_button'])

        module = 'stoqlib.domain.base.Domain.check_unique_value_exists'
        with mock.patch(module) as check_unique_value_exists:
            check_unique_value_exists.return_value = True
            step.invoice_number.update(2)
            self.assertInvalid(step, ['invoice_number'])
            self.assertNotSensitive(wizard, ['next_button'])

    @mock.patch('stoqlib.gui.wizards.salereturnwizard.info')
    def testSaleReturnPaymentStepNotPaid(self, info):
        sale = self.create_sale(id_=1234)
        self.add_product(sale, price=50, quantity=6)
        self.add_payments(sale, method_type='check', installments=3,
                          date=datetime.date(2012, 1, 1))
        sale.order()
        sale.confirm()
        returned_sale = sale.create_sale_return_adapter()
        returned_sale.reason = 'reason'
        returned_sale.invoice_number = 1
        returned_sale.returned_items[0].quantity = 1
        wizard = SaleReturnWizard(self.trans, returned_sale)
        self.click(wizard.next_button)
        self.click(wizard.next_button)
        step = wizard.get_current_step()

        info.assert_called_once_with(
            "The client needs to pay some additional amount. Use this "
            "step to edit existing payments and add that amount.")
        self.assertVisible(step.slave, ['remove_button'])
        self.assertEqual(step.slave.total_value.read(),
                         returned_sale.total_amount_abs +
                         returned_sale.paid_total)
        self.check_wizard(wizard,
                          'wizard-sale-return-payment-step-not-paid')

    @mock.patch('stoqlib.gui.wizards.salereturnwizard.info')
    def testSaleReturnPaymentStepPartiallyPaid(self, info):
        sale = self.create_sale(id_=1234)
        self.add_product(sale, price=50, quantity=6)
        payments = self.add_payments(sale, method_type='check', installments=3,
                                     date=datetime.date(2012, 1, 1))
        sale.order()
        sale.confirm()
        payments[0].pay()
        returned_sale = sale.create_sale_return_adapter()
        returned_sale.reason = 'reason'
        returned_sale.invoice_number = 1
        returned_sale.returned_items[0].quantity = 1
        wizard = SaleReturnWizard(self.trans, returned_sale)
        self.click(wizard.next_button)
        self.click(wizard.next_button)
        step = wizard.get_current_step()

        info.assert_called_once_with(
            "The client needs to pay some additional amount. Use this "
            "step to edit existing payments and add that amount.")
        self.assertVisible(step.slave, ['remove_button'])
        self.assertEqual(step.slave.total_value.read(),
                         returned_sale.total_amount_abs +
                         returned_sale.paid_total)
        self.check_wizard(wizard,
                          'wizard-sale-return-payment-step-partially-paid')