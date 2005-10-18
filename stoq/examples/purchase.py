#!/usr/bin/env python
# -*- Mode: Python; coding: iso-8859-1 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005 Async Open Source <http://www.async.com.br>
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
## Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
## USA.
##
##  Author(s):      Evandro Vale Miquelito  <evandro@async.com.br>
##
"""
stoq/examples/purchase.py:

    Create purchase objects for an example database.
"""

import datetime

from stoq.domain.purchase import PurchaseOrder, PurchaseItem
from stoq.domain.person import Person
from stoq.domain.interfaces import ISupplier
from stoq.domain.sellable import AbstractSellable
from stoq.lib.runtime import new_transaction


MAX_PURCHASES_NUMBER = 4
SELLABLES_PER_PURCHASE = 2

def create_purchases():
    print 'Creating purchases...'
    conn = new_transaction()

    supplier_table = Person.getAdapterClass(ISupplier)
    suppliers = supplier_table.select(connection=conn)
    if suppliers.count() < MAX_PURCHASES_NUMBER:
        raise ValueError('You must have at least %d suppliers in your '
                         'database at this point.' % MAX_PURCHASES_NUMBER)

    sellables = AbstractSellable.select(connection=conn)
    sellables_total = SELLABLES_PER_PURCHASE * MAX_PURCHASES_NUMBER
    if sellables.count() < sellables_total:
        raise ValueError('You must have at least %d sellables in your '
                         'database at this point.' % sellables_total)

    dates = []
    open_dates = []
    purchaseitem_data = []
    for i in range(sellables_total):
        date = datetime.datetime.now() + datetime.timedelta(i + 7)
        dates.append(date)
        open_date = datetime.datetime.now() + datetime.timedelta(i + 5)
        open_dates.append(open_date)
        purchaseitem_data.append(dict(quantity=i + 10,
                                      quantity_received=i + 5))

    purchase_data = [dict(status=PurchaseOrder.ORDER_QUOTING,
                          salesperson_name='Michael Jackson',
                          discount_value=10.0,
                          open_date=open_dates[0],
                          quote_deadline=dates[0]),
                     dict(status=PurchaseOrder.ORDER_PENDING,
                          salesperson_name='Olivia Palito',
                          open_date=open_dates[1],
                          discount_value=15.50),
                     dict(status=PurchaseOrder.ORDER_CONFIRMED,
                          salesperson_name='Henrique Sabbath',
                          open_date=open_dates[2],
                          expected_receival_date=dates[1],
                          confirm_date=dates[2],
                          charge_value=13.70),
                     dict(status=PurchaseOrder.ORDER_CLOSED,
                          salesperson_name='Johan Lebowski',
                          open_date=open_dates[3],
                          receival_date=dates[3],
                          charge_value=34.32)]

    sellable_index = 0
    for index in range(MAX_PURCHASES_NUMBER):

        supplier = suppliers[index]
        
        purchase_args = purchase_data[index]
        order = PurchaseOrder(connection=conn, supplier=supplier,
                              order_number=index + 1,
                              **purchase_args)


        indexes = sellable_index, sellable_index + 1
        # Increment sellable index in two positions and get exclusive
        # sellable instance in the next loop
        sellable_index += 2
        for index in indexes:
            sellable = sellables[index]
            item_args = purchaseitem_data[index]
            PurchaseItem(connection=conn, cost=sellable.cost,
                         order=order, sellable=sellable,
                         **item_args)
        
    conn.commit()
    print 'done.'


if __name__ == "__main__":
    create_purchases()
