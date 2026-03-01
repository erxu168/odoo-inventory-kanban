# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class InventoryCountStandalone(http.Controller):
    """
    Serves the standalone inventory count app at /inventory-count.
    Follows the same pattern as pos_self_order's self_order controller.
    """

    @http.route('/inventory-count', type='http', auth='user', website=False)
    def inventory_count_app(self, **kwargs):
        """Main entry point — renders the shell HTML that bootstraps the OWL app."""
        # Validate the user has stock access
        if not request.env.user.has_group('stock.group_stock_user'):
            return request.redirect('/web/login')

        return request.render(
            'inventory_count_standalone.standalone_index',
            {
                'session_info': request.env['ir.http'].get_frontend_session_info(),
                'user_name': request.env.user.name,
            }
        )

    @http.route('/inventory-count/items', type='json', auth='user')
    def get_items(self, location_id=None, limit=500):
        """Returns stock.quant records for inventory counting."""
        domain = [('location_id.usage', '=', 'internal')]
        if location_id:
            domain.append(('location_id', 'child_of', location_id))

        quants = request.env['stock.quant'].search_read(
            domain,
            fields=[
                'id', 'product_id', 'location_id', 'lot_id',
                'quantity', 'inventory_quantity', 'inventory_quantity_set',
                'product_uom_id',
            ],
            limit=limit,
            order='location_id, product_id',
        )
        return quants

    @http.route('/inventory-count/set_count', type='json', auth='user')
    def set_count(self, quant_id, qty):
        """Sets the counted quantity for a single stock.quant record."""
        quant = request.env['stock.quant'].browse(int(quant_id))
        if not quant.exists():
            return {'error': 'Record not found'}

        quant.inventory_quantity = float(qty)
        quant.inventory_quantity_set = True

        diff = quant.inventory_quantity - quant.quantity
        if abs(diff) < 0.005:
            state = 'match'
        elif diff > 0:
            state = 'over'
        else:
            state = 'short'

        return {
            'id': quant.id,
            'inventory_quantity': quant.inventory_quantity,
            'inventory_quantity_set': True,
            'diff': diff,
            'diff_state': state,
        }

    @http.route('/inventory-count/validate', type='json', auth='user')
    def validate_inventory(self):
        """Validates (applies) the inventory adjustment. Requires stock manager access."""
        if not request.env.user.has_group('stock.group_stock_manager'):
            return {'error': 'Access denied. Only stock managers can validate inventory.'}

        try:
            # Search for quants that have been counted, not an empty recordset
            quants = request.env['stock.quant'].search([
                ('location_id.usage', '=', 'internal'),
                ('inventory_quantity_set', '=', True),
            ])
            if not quants:
                return {'error': 'No inventory adjustments to apply.'}

            quants.action_apply_inventory()
            return {'success': True}
        except Exception as e:
            return {'error': str(e)}

    @http.route('/inventory-count/locations', type='json', auth='user')
    def get_locations(self):
        """Returns internal locations for the location filter."""
        locations = request.env['stock.location'].search_read(
            [('usage', '=', 'internal'), ('active', '=', True)],
            fields=['id', 'display_name'],
            limit=100,
        )
        return locations
