# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from odoo import api, SUPERUSER_ID
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Create a payment group for every existint payment (no transfers)
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    # payments = env['account.payment'].search(
    #     [('payment_type', '!=', 'transfer')])
    # on v10, on reconciling from statements, if not partner is choosen, then
    # a payment is created with no partner. We still make partners mandatory
    # on payment groups. So, we dont create payment groups for payments
    # without partner_id
    payments = env['account.payment'].search(
        [('partner_id', '!=', False), ('is_internal_transfer', '=', False)])

    for payment in payments:
        count +=1
        _logger.info('Procesando %s de %s. Creando APG for payment %s, %s' % 
                     (count, total_payments, payment.id, payment.name))
        _state = payment.state in ['sent', 'reconciled'] and 'posted' or payment.state
        _state = _state if _state != 'cancelled' else 'cancel'
        # Here we got line_ids from reconciled_invoice_ids linked in account.payment
        to_pay_move_line_ids = payment.reconciled_invoice_ids.mapped('line_ids').filtered(lambda x: x.account_id.account_type == 'asset_receivable').ids if payment.payment_type == 'inbound' else payment.reconciled_bill_ids.mapped('line_ids').filtered(lambda x: x.account_id.account_type == 'liability_payable').ids
        
        env['account.payment.group'].create({
            'company_id': payment.company_id.id,
            'partner_type': payment.partner_type,
            'partner_id': payment.partner_id.id,
            'payment_date': payment.date,
            'communication': payment.ref,
            'payment_ids': [(4, payment.id, False)],
            'state': _state,
            'to_pay_move_line_ids': [(6, 0, to_pay_move_line_ids)], # To link existing asociated debs  
        })
