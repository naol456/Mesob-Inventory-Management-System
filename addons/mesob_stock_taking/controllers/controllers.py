# from odoo import http


# class MesobStockTaking(http.Controller):
#     @http.route('/mesob_stock_taking/mesob_stock_taking', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mesob_stock_taking/mesob_stock_taking/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('mesob_stock_taking.listing', {
#             'root': '/mesob_stock_taking/mesob_stock_taking',
#             'objects': http.request.env['mesob_stock_taking.mesob_stock_taking'].search([]),
#         })

#     @http.route('/mesob_stock_taking/mesob_stock_taking/objects/<model("mesob_stock_taking.mesob_stock_taking"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mesob_stock_taking.object', {
#             'object': obj
#         })

