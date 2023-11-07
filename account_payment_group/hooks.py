# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from odoo import api, SUPERUSER_ID
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Create a payment group for every existint payment (no transfers)
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Seteamos los vals para talonarios de recibo de cliente y proveedor
    vals_rex = {
        'name': 'Recibos X de Cliente',
        'partner_type': 'customer',
        'sequence_type': 'automatic',
        'document_type_id': env.ref('account_payment_group.dc_recibo_x').id,
    }
    vals_opx = {
        'name': 'Orden de Pago X a Proveedor',
        'partner_type': 'supplier',
        'sequence_type': 'automatic',
        'document_type_id': env.ref('account_payment_group.dc_orden_pago_x').id,
    }

    # Consultamos si tenemos talonarios de recibo y de pago
    rp_rex = env['account.payment.receiptbook'].search([('partner_type','=', 'customer'),
                ('document_type_id','=', env.ref('account_payment_group.dc_recibo_x').id)],
                                                         limit=1)

    rp_opx = env['account.payment.receiptbook'].search([('partner_type','=', 'supplier'),
                ('document_type_id','=', env.ref('account_payment_group.dc_orden_pago_x').id)],
                                                         limit=1)
    
    # Creamos los talonarios en caso de que no existan o tomamos el id de las consultas efectuadas
    rex_id = env['account.payment.receiptbook'].create(vals_rex).id if not rp_rex else rp_rex.id
    opx_id = env['account.payment.receiptbook'].create(vals_opx).id if not rp_opx else rp_opx.id
    ## commit
    
    # Consultamos los registros de pagos asociados con partner, 
    # que no sean transferencias internas y 
    # que no tengan asociado algun grupo de pago
    payments = env['account.payment'].search(
        [('partner_id', '!=', False), 
         ('is_internal_transfer', '=', False),
         ('payment_group_id', '=', False)],
        order='date asc')
    total_payments = len(payments)
    count = 0
    # Create a payment group for every existint payment (no transfers) and without a.p.g
    for payment in payments:
        count +=1
        _logger.info('Procesando payment %s de %s. Creando APG for payment %s, %s' % 
                     (count, total_payments, payment.id, payment.name))
        _state = payment.state in ['sent', 'reconciled'] and 'posted' or payment.state
        _state = _state if _state != 'cancelled' else 'cancel'
        # Here we got line_ids from reconciled_invoice_ids linked in account.payment
        to_pay_move_line_ids = payment.reconciled_invoice_ids.mapped('line_ids').filtered(lambda x: x.account_id.account_type == 'asset_receivable').ids if payment.payment_type == 'inbound' else payment.reconciled_bill_ids.mapped('line_ids').filtered(lambda x: x.account_id.account_type == 'liability_payable').ids
        
        apg = env['account.payment.group'].create({
            'company_id': payment.company_id.id,
            'partner_type': payment.partner_type,
            'partner_id': payment.partner_id.id,
            'payment_date': payment.date,
            'communication': payment.ref,
            'payment_ids': [(4, payment.id, False)],
            'state': _state,
            'to_pay_move_line_ids': [(6, 0, to_pay_move_line_ids)], # To link existing asociated debs  
        })

        # Asociamos el talonario y luego asignamos el número de recibo o pago
        apg.receiptbook_id = rex_id if payment.payment_type == 'inbound' else opx_id            
        apg.document_number = (apg.receiptbook_id.with_context(ir_sequence_date=apg.payment_date).sequence_id.next_by_id())
        apg.name = "%s %s" % (apg.document_type_id.doc_code_prefix, apg.document_number)
