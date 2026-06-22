from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MesobStoragePlan(models.Model):
    """Storage Organization and Layout Artifact - FR-STOR-001/002.

    Supports labeling of stocks, shelves, and documenting physical layout plan.
    """

    _name = "mesob.storage.plan"
    _description = "Warehouse Storage Plan"
    _order = "id desc"

    name = fields.Char(string="Storage Plan / Layout Title", required=True)
    description = fields.Text(string="Layout Description")
    aisles = fields.Char(string="Aisles Configuration", help="Aisles mapping, e.g. Aisle A-H")
    gates_count = fields.Integer(string="Number of Gates/Exits", default=2)
    layout_file = fields.Binary(string="Layout Document/Plan", help="Physical schematic or floor plan document.")
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved by PAO")],
        string="Status",
        default="draft",
        required=True,
    )

    def action_approve(self):
        for rec in self:
            rec.state = "approved"


class MesobStorageKeyRegister(models.Model):
    """Key Custody Register with Tamper-evident logging - FR-STOR-003 / NFR-SEC-003."""

    _name = "mesob.storage.key.register"
    _description = "Warehouse Key Custody Register"
    _order = "collected_at desc, id desc"

    name = fields.Char(string="Transaction ID", required=True, copy=False, default="New")
    key_id = fields.Char(string="Key ID / Label", required=True)
    collected_by_id = fields.Many2one("res.users", string="Collected By", required=True)
    collected_at = fields.Datetime(string="Collected Timestamp", default=fields.Datetime.now, required=True)
    deposited_at = fields.Datetime(string="Deposited Timestamp")
    notes = fields.Text(string="Remarks")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.storage.key.register") or "New"
        return super().create(vals_list)

    def action_deposit_keys(self):
        for rec in self:
            rec.deposited_at = fields.Datetime.now()


class MesobStorageVisitorLog(models.Model):
    """Visitor Access Logs - FR-STOR-004."""

    _name = "mesob.storage.visitor.log"
    _description = "Warehouse Visitor Log"
    _order = "entry_time desc"

    name = fields.Char(string="Log Reference", required=True, copy=False, default="New")
    visitor_name = fields.Char(string="Visitor Name", required=True)
    organization = fields.Char(string="Organization / Institution")
    purpose = fields.Text(string="Purpose of Visit", required=True)
    entry_time = fields.Datetime(string="Entry Timestamp", default=fields.Datetime.now, required=True)
    exit_time = fields.Datetime(string="Exit Timestamp")
    security_escort_id = fields.Many2one("res.users", string="Security Officer / Escort")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.storage.visitor.log") or "New"
        return super().create(vals_list)

    def action_exit(self):
        for rec in self:
            rec.exit_time = fields.Datetime.now()


class MesobStorageSafetyChecklist(models.Model):
    """Safety and Fire Precaution Compliance Checklist - FR-STOR-005/006."""

    _name = "mesob.storage.safety.checklist"
    _description = "Warehouse Safety Checklist"
    _order = "date desc, id desc"

    name = fields.Char(string="Checklist Reference", required=True, copy=False, default="New")
    inspector_id = fields.Many2one("res.users", string="Inspector / Officer", default=lambda self: self.env.user, required=True)
    date = fields.Date(string="Inspection Date", default=fields.Date.today, required=True)
    
    has_fire_extinguishers_checked = fields.Boolean(string="Fire Extinguishers Checked & Serviced (FR-STOR-005)", default=False)
    has_ppe_available = fields.Boolean(string="PPE Available & Utilized (FR-STOR-006)", default=False)
    has_first_aid_kit = fields.Boolean(string="First Aid Kit Fully Stocked", default=False)
    has_emergency_exits_clear = fields.Boolean(string="Emergency Communication & Exits Clear", default=False)
    
    remarks = fields.Text(string="Inspection Observations")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.storage.safety.checklist") or "New"
        return super().create(vals_list)
