from odoo import models, fields, api
from datetime import datetime


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    removal_date_transfer = fields.Boolean(
        string='Removal Date Transfers',
        help='If enabled, the system will automatically create transfers for lots that have reached their removal date'
    )
    removal_transfer_type_id = fields.Many2one(
        'stock.picking.type',
        string='Transfer Operation Type',
        help='Operation type to use for removal date transfers'
    )

    def _process_removal_date_transfers(self):
        """Process removal date transfers for warehouses where removal_date_transfer is enabled."""
        today = fields.Date.today()
        warehouses = self.search([('removal_date_transfer', '=', True)])
        
        for warehouse in warehouses:
            if not warehouse.removal_transfer_type_id:
                continue

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
                
                # Create transfer using selected operation type
                picking_type = warehouse.removal_transfer_type_id
                picking = self.env['stock.picking'].create({
                    'picking_type_id': picking_type.id,
                    'location_id': picking_type.default_location_src_id.id or warehouse.lot_stock_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id or warehouse.wh_output_stock_loc_id.id,
                    'origin': f'Removal Date Transfer - {lot.name}',
                    'scheduled_date': fields.Datetime.now(),
                })
                
                move = self.env['stock.move'].create({
                    'name': f'Removal Date Transfer - {lot.name}',
                    'picking_id': picking.id,
                    'product_id': lot.product_id.id,
                    'product_uom_qty': sum(quants.mapped('quantity')),
                    'product_uom': lot.product_id.uom_id.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'lot_ids': [(4, lot.id)],
                })
                
                picking.action_confirm()

    @api.model
    def _run_scheduler_removal_date_transfers(self):
        """Scheduled action to process removal date transfers."""
        self._process_removal_date_transfers()

    def test_removal_date_transfer(self):
        """Test method to verify removal date transfer functionality."""
        self.ensure_one()
        self.removal_date_transfer = True
        
        # Create a test product with lot tracking
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'tracking': 'lot',
        })
        
        # Create a lot with today's removal date
        lot = self.env['stock.lot'].create({
            'name': 'TEST/LOT/001',
            'product_id': product.id,
            'company_id': self.company_id.id,
            'removal_date': fields.Datetime.now(),
        })
        
        # Add stock for this lot
        self.env['stock.quant'].create({
            'product_id': product.id,
            'location_id': self.lot_stock_id.id,
            'quantity': 10.0,
            'lot_id': lot.id,
        })
        
        # Process removal date transfers
        self._process_removal_date_transfers()
        
        # Verify transfer was created
        picking = self.env['stock.picking'].search([
            ('origin', '=', f'Removal Date Transfer - {lot.name}'),
            ('picking_type_id', '=', self.int_type_id.id)
        ])
        
        if picking:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test Successful',
                    'message': f'Transfer {picking.name} created successfully for lot {lot.name}',
                    'type': 'success',
                }
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Failed',
                'message': 'No transfer was created',
                'type': 'danger',
            }
        }
        

class StockLot(models.Model):
    _inherit = 'stock.lot'

    use_date = fields.Datetime(string='Best before Date', store=True, readonly=False,
        help='This is the date on which the goods with this Serial Number start deteriorating, without being dangerous yet.')
    removal_date = fields.Datetime(string='Removal Date', readonly=False,
        help='This is the date on which the goods with this Serial Number should be removed from the stock. This date will be used in stock removal transfer strategy.')
    alert_date = fields.Datetime(string='Alert Date', readonly=False,
        help='Date to determine the expired lots and serial numbers using the filter "Expiration Alerts".')