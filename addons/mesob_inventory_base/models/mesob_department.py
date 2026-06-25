from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MesobDepartment(models.Model):
    """Department Master Data.
    
    Configurable department list for use throughout the system
    instead of hard-coded selection fields.
    """

    _name = "mesob.department"
    _description = "Department"
    _order = "name"
    _rec_name = "name"

    name = fields.Char(
        string="Department Name",
        required=True,
        index=True,
        help="Full name of the department or organization unit.",
    )
    code = fields.Char(
        string="Department Code",
        help="Short code or abbreviation for the department (optional).",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive departments will not appear in selection lists.",
    )
    description = fields.Text(
        string="Description",
        help="Additional information about the department.",
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Department name must be unique!",
        ),
        (
            "code_unique",
            "UNIQUE(code)",
            "Department code must be unique!",
        ),
    ]

    @api.constrains("name")
    def _check_name(self):
        """Ensure department name is not empty."""
        for rec in self:
            if not rec.name or not rec.name.strip():
                raise ValidationError("Department name cannot be empty.")
