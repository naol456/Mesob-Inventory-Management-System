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
    manager_id = fields.Many2one(
        "res.users",
        string="Department Head",
        help="User who manages this department (Department Head).",
    )
    dept_head_ids = fields.Many2many(
        "res.users",
        compute="_compute_dept_head_ids",
        string="Available Department Heads",
        help="Technical field: users with Department Head role.",
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

    def _compute_dept_head_ids(self):
        """Compute list of users who have Department Head role."""
        dept_head_group = self.env.ref('mesob_inventory_base.group_mesob_dept_head', raise_if_not_found=False)
        if dept_head_group:
            # Access users through the res_groups_users_rel table
            self.env.cr.execute("""
                SELECT uid FROM res_groups_users_rel 
                WHERE gid = %s
            """, (dept_head_group.id,))
            user_ids = [row[0] for row in self.env.cr.fetchall()]
            dept_heads = self.env['res.users'].browse(user_ids)
            for record in self:
                record.dept_head_ids = dept_heads
        else:
            for record in self:
                record.dept_head_ids = False

    @api.constrains("name")
    def _check_name(self):
        """Ensure department name is not empty."""
        for rec in self:
            if not rec.name or not rec.name.strip():
                raise ValidationError("Department name cannot be empty.")
