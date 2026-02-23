from odoo import http
from odoo.http import request


class MobileInventoryController(http.Controller):

    @http.route('/mobile_inventory/get_quants', type='json', auth='user')
    def get_quants(self, location_id=None, product_id=None, search='', offset=0, limit=20):
        """Fetch stock quants for mobile inventory view."""
        domain = [('location_id.usage', '=', 'internal')]
        
        if location_id:
            domain.append(('location_id', '=', int(location_id)))
        if product_id:
            domain.append(('product_id', '=', int(product_id)))
        if search:
            domain.append(('product_id.name', 'ilike', search))

        quants = request.env['stock.quant'].search(
            domain, offset=int(offset), limit=int(limit),
            order='product_id asc'
        )
        total = request.env['stock.quant'].search_count(domain)

        result = []
        for q in quants:
            # Clean product name: use product_tmpl name + variant separately
            # This avoids the messy "[REF] Name (Variant)" display_name format
            product = q.product_id
            tmpl = product.product_tmpl_id

            # Clean base name from template (no reference code mixed in)
            base_name = tmpl.name or product.name or ''

            # Variant attributes e.g. "Red, XL"
            variant_name = product.product_template_attribute_value_ids\
                .mapped('name')
            variant_str = ', '.join(variant_name) if variant_name else ''

            # Full clean name
            clean_name = base_name
            if variant_str:
                clean_name = f"{base_name} ({variant_str})"

            # Reference code — prefer product-level, fall back to template
            ref_code = product.default_code or tmpl.default_code or ''

            # Category
            category = tmpl.categ_id.name if tmpl.categ_id else ''

            result.append({
                'id': q.id,
                'product_id': product.id,
                'product_name': clean_name,
                'product_default_code': ref_code,
                'product_category': category,
                'product_variant': variant_str,
                'product_uom': q.product_uom_id.name,
                'location_id': q.location_id.id,
                'location_name': q.location_id.display_name,
                'lot_name': q.lot_id.name if q.lot_id else '',
                'quantity': q.quantity,
                'inventory_quantity': q.inventory_quantity,
                'inventory_diff_quantity': q.inventory_diff_quantity,
                'inventory_date': q.inventory_date.strftime('%Y-%m-%d %H:%M:%S') if q.inventory_date else False,
            })

        return {'quants': result, 'total': total}

    @http.route('/mobile_inventory/set_quantity', type='json', auth='user')
    def set_quantity(self, quant_id, quantity):
        """Set inventory quantity for a quant."""
        quant = request.env['stock.quant'].browse(int(quant_id))
        if not quant.exists():
            return {'success': False, 'error': 'Quant not found'}
        try:
            quant.inventory_quantity = float(quantity)
            return {
                'success': True,
                'inventory_quantity': quant.inventory_quantity,
                'inventory_diff_quantity': quant.inventory_diff_quantity,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/mobile_inventory/apply_all', type='json', auth='user')
    def apply_all(self, location_id=None):
        """Apply all inventory adjustments."""
        domain = [('location_id.usage', '=', 'internal')]
        if location_id:
            domain.append(('location_id', '=', int(location_id)))
        quants = request.env['stock.quant'].search(domain)
        try:
            quants.action_apply_inventory()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/mobile_inventory/get_locations', type='json', auth='user')
    def get_locations(self, search=''):
        """Get internal locations for filter dropdown."""
        domain = [('usage', '=', 'internal'), ('active', '=', True)]
        if search:
            domain.append(('complete_name', 'ilike', search))
        locations = request.env['stock.location'].search(domain, limit=50, order='complete_name asc')
        return [{'id': l.id, 'name': l.display_name} for l in locations]

    @http.route('/mobile_inventory/create_quant', type='json', auth='user')
    def create_quant(self, product_id, location_id, quantity):
        """Create a new quant entry for inventory."""
        try:
            existing = request.env['stock.quant'].search([
                ('product_id', '=', int(product_id)),
                ('location_id', '=', int(location_id)),
            ], limit=1)
            if existing:
                existing.inventory_quantity = float(quantity)
                return {'success': True, 'quant_id': existing.id}
            else:
                quant = request.env['stock.quant'].create({
                    'product_id': int(product_id),
                    'location_id': int(location_id),
                    'inventory_quantity': float(quantity),
                })
                return {'success': True, 'quant_id': quant.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
