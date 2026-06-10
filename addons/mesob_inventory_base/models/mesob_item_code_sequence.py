from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MesobItemCodeSequence(models.Model):
    """Item Code Sequence Tracker for auto-generating item codes.

    Tracks the last used specific code for each major-sub classification combination.
    Ensures sequential, unique item codes in format MAJOR-SUB-SPECIFIC (e.g., 3345-456-001).
    """

    _name = "mesob.item.code.sequence"
    _description = "Item Code Sequence Tracker"
    _order = "major_code, sub_code"

    _sql_constraints = [
        (
            'major_sub_unique',
            'UNIQUE(major_code, sub_code)',
            'Sequence tracker must be unique per major-sub combination.'
        ),
        (
            'last_code_positive',
            'CHECK(last_specific_code > 0)',
            'Last specific code must be a positive integer.'
        ),
    ]

    major_code = fields.Char(
        string="Major Code",
        required=True,
        size=4,
        index=True,
        help="4-digit major classification code (e.g., 3345).",
    )
    sub_code = fields.Char(
        string="Sub Code",
        required=True,
        size=3,
        index=True,
        help="3-digit sub classification code (e.g., 456).",
    )
    last_specific_code = fields.Integer(
        string="Last Specific Code",
        required=True,
        default=0,
        help="Last used specific code number for this major-sub combination.",
    )

    @api.constrains('major_code', 'sub_code', 'last_specific_code')
    def _check_codes(self):
        """Validate code formats and positivity."""
        for rec in self:
            if rec.major_code and (len(rec.major_code) != 4 or not rec.major_code.isdigit()):
                raise ValidationError(
                    _("Major code must be exactly 4 digits. Got: %s") % rec.major_code
                )
            if rec.sub_code and (len(rec.sub_code) != 3 or not rec.sub_code.isdigit()):
                raise ValidationError(
                    _("Sub code must be exactly 3 digits. Got: %s") % rec.sub_code
                )
            if rec.last_specific_code < 0:
                raise ValidationError(
                    _("Last specific code must be non-negative. Got: %s") % rec.last_specific_code
                )

    def get_next_specific_code(self, major_code, sub_code):
        """Get next available specific code for major-sub combination.

        Args:
            major_code (str): 4-digit major classification code
            sub_code (str): 3-digit sub classification code

        Returns:
            str: 3-digit zero-padded specific code (e.g., "001", "002")

        This method uses database locking to ensure thread-safe sequence generation.
        """
        self.env.cr.execute(
            """
            SELECT id, last_specific_code
            FROM mesob_item_code_sequence
            WHERE major_code = %s AND sub_code = %s
            FOR UPDATE
            """,
            (major_code, sub_code)
        )
        result = self.env.cr.fetchone()

        if result:
            # Existing sequence - increment
            sequence_id, last_code = result
            next_code = last_code + 1
            self.env.cr.execute(
                """
                UPDATE mesob_item_code_sequence
                SET last_specific_code = %s
                WHERE id = %s
                """,
                (next_code, sequence_id)
            )
        else:
            # First item for this major-sub combination
            next_code = 1
            self.env.cr.execute(
                """
                INSERT INTO mesob_item_code_sequence (major_code, sub_code, last_specific_code)
                VALUES (%s, %s, %s)
                """,
                (major_code, sub_code, next_code)
            )

        # Format as 3-digit zero-padded string
        return f"{next_code:03d}"
