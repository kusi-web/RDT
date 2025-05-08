from odoo import models, fields, api
from datetime import datetime


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    removal_date_transfer = fields.Boolean(
        string='Removal Date Transfers',
        help='If enabled, the system will automatically create transfers for lots that have reached their removal date'
    )

    def _process_removal_date_transfers(self):
        """Process removal date transfers for warehouses where removal_date_transfer is enabled."""
        today = fields.Date.today()
        warehouses = self.search([('removal_date_transfer', '=', True)])
        
        for warehouse in warehouses:
            lots = self.env['stock.lot'].search([
                ('removal_date', '<=', today),
                ('quant_ids.location_id', 'child_of', warehouse.lot_stock_id.id),
                ('quant_ids.quantity', '>', 0),
            ])
            
            for lot in lots:
                quants = lot.quant_ids.filtered(lambda q: 
                    q.location_id.id == warehouse.lot_stock_id.id and 
                    q.quantity > 0
                )
                if not quants:
                    continue
                
                # First unreserve all quants
                for quant in quants:
                    if quant.reserved_quantity > 0:
                        quant._update_reserved_quantity(
                            lot.product_id,
                            quant.location_id,
                            -quant.reserved_quantity,
                            lot_id=lot,
                            strict=False
                        )
                
                # Create internal transfer
                picking = self.env['stock.picking'].create({
                    'picking_type_id': warehouse.int_type_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': warehouse.wh_output_stock_loc_id.id,
                    'origin': f'Removal Date Transfer - {lot.name}',
                    'scheduled_date': fields.Datetime.now(),
                })
                
                move = self.env['stock.move'].create({
                    'name': f'Removal Date Transfer - {lot.name}',
                    'picking_id': picking.id,
                    'product_id': lot.product_id.id,
                    'product_uom_qty': sum(quants.mapped('quantity')),
                    'product_uom': lot.product_id.uom_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': warehouse.wh_output_stock_loc_id.id,
                    'lot_ids': [(4, lot.id)],
                })
                
                picking.action_confirm()

    @api.model
    def _run_scheduler_removal_date_transfers(self):
        """Scheduled action to process removal date transfers."""
        self._process_removal_date_transfers()
        

class StockLot(models.Model):
    _inherit = 'stock.lot'

    removal_date = fields.Date(string='Removal Date')
    best_before = fields.Date(string='Best Before Date')
    alert_date = fields.Date(string='Alert Date')
