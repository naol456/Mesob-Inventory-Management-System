from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """Extend res.partner to support FPPA Supplier Registration and Qualification."""

    _inherit = "res.partner"

    is_supplier = fields.Boolean(
        string="Is Supplier",
        default=False,
        help="Check this box to mark this partner as a supplier/vendor.",
    )
    legal_registration_number = fields.Char(
        string="Legal Registration No.",
        help="Federal/Regional trade license registration number.",
    )
    tin = fields.Char(
        string="TIN",
        help="Taxpayer Identification Number (9 digits).",
    )
    supply_category_ids = fields.Many2many(
        "mesob.inventory.major.classification",
        "res_partner_major_classification_rel",
        "partner_id",
        "classification_id",
        string="Supply Categories",
        help="Categories of goods the supplier is registered to supply.",
    )
    registration_expiry_date = fields.Date(
        string="Registration Expiry Date",
        help="Expiry date of trade registration/license.",
    )
    fppa_blacklisted = fields.Boolean(
        string="Blacklisted / Suspended",
        default=False,
        help="Whether the supplier is blacklisted or suspended by FPPA.",
    )
    blacklist_reason = fields.Text(
        string="Blacklist / Suspension Reason",
    )
    performance_score = fields.Float(
        string="Supplier Performance Score",
        compute="_compute_performance_score",
        store=True,
        help="Aggregated performance score (0-100) from purchase/delivery history.",
    )

    @api.constrains("tin")
    def _check_tin_format(self):
        for partner in self:
            if partner.tin and (not partner.tin.isdigit() or len(partner.tin) != 9):
                raise ValidationError("TIN must be exactly 9 digits.")

    @api.depends("fppa_blacklisted", "registration_expiry_date")
    def _compute_performance_score(self):
        for partner in self:
            # Simple aggregate score calculation for demonstration/mocking
            # In a real system, this aggregates delivery on-time rates and rejection rates.
            if partner.fppa_blacklisted:
                partner.performance_score = 0.0
            else:
                partner.performance_score = 85.0
