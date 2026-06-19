# -*- coding: utf-8 -*-
"""Task 11: Signable Document Mixin

Abstract model that adds digital signature capability to any document.
Models can inherit this to enable signing functionality.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MesobSignableMixin(models.AbstractModel):
    """Mixin to add digital signature capability to documents."""
    
    _name = 'mesob.signable.mixin'
    _description = 'Signable Document Mixin'
    
    # Signature tracking
    signature_ids = fields.One2many(
        'mesob.digital.signature',
        compute='_compute_signature_ids',
        string='Digital Signatures',
        help='Digital signatures applied to this document'
    )
    
    signature_count = fields.Integer(
        string='Signature Count',
        compute='_compute_signature_ids',
        help='Number of digital signatures on this document'
    )
    
    is_digitally_signed = fields.Boolean(
        string='Digitally Signed',
        compute='_compute_signature_ids',
        search='_search_is_digitally_signed',
        help='True if document has at least one valid digital signature'
    )
    
    latest_signature_id = fields.Many2one(
        'mesob.digital.signature',
        compute='_compute_signature_ids',
        string='Latest Signature',
        help='Most recent digital signature'
    )
    
    @api.depends('id')
    def _compute_signature_ids(self):
        """Compute signatures for this document."""
        for record in self:
            if not record.id:
                record.signature_ids = False
                record.signature_count = 0
                record.is_digitally_signed = False
                record.latest_signature_id = False
                continue
            
            # Find signatures for this document
            signatures = self.env['mesob.digital.signature'].search([
                ('document_model', '=', record._name),
                ('document_id', '=', record.id)
            ], order='signed_on desc')
            
            record.signature_ids = signatures
            record.signature_count = len(signatures)
            record.is_digitally_signed = len(signatures) > 0
            record.latest_signature_id = signatures[0] if signatures else False
    
    def _search_is_digitally_signed(self, operator, value):
        """Enable searching for signed/unsigned documents."""
        # Get all signatures
        signatures = self.env['mesob.digital.signature'].search([
            ('document_model', '=', self._name)
        ])
        
        # Get unique document IDs
        signed_ids = list(set(signatures.mapped('document_id')))
        
        # Return domain based on operator
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', signed_ids)]
        else:
            return [('id', 'not in', signed_ids)]
    
    def action_create_digital_signature(self, signature_type='approval', reason=None):
        """Create digital signature for this document.
        
        Args:
            signature_type (str): Type of signature
            reason (str, optional): Reason for signing
        
        Returns:
            mesob.digital.signature: Created signature
        """
        self.ensure_one()
        
        # Create signature
        signature = self.env['mesob.digital.signature'].create_signature(
            document_model=self._name,
            document_id=self.id,
            signature_type=signature_type,
            reason=reason
        )
        
        # Log to chatter
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>🖊️ Task 11: Document Digitally Signed</h3>
                <p><strong>Signed By:</strong> {self.env.user.name}</p>
                <p><strong>Signed On:</strong> {signature.signed_on}</p>
                <p><strong>Signature Type:</strong> {dict(signature._fields['signature_type'].selection)[signature_type]}</p>
                {f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''}
                <p><strong>Signature Hash:</strong> <code>{signature.signature_hash[:16]}...</code></p>
                <hr/>
                <p><em>This document is now protected by digital signature. Any modifications after signing will invalidate the signature.</em></p>
            </div>""",
            subject=f'Digital Signature Applied',
            message_type='comment'
        )
        
        _logger.info(
            f"Task 11: Digital signature created for {self._name} ID {self.id} "
            f"by {self.env.user.name}"
        )
        
        return signature
    
    def action_view_signatures(self):
        """Open list of signatures for this document."""
        self.ensure_one()
        
        return {
            'name': f'Signatures: {self.display_name if hasattr(self, "display_name") else self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.digital.signature',
            'view_mode': 'tree,form',
            'domain': [
                ('document_model', '=', self._name),
                ('document_id', '=', self.id)
            ],
            'context': {'default_document_model': self._name, 'default_document_id': self.id},
        }
    
    def action_verify_signatures(self):
        """Verify all signatures on this document."""
        self.ensure_one()
        
        if not self.signature_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Signatures',
                    'message': 'This document has not been digitally signed.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Force verification
        self.signature_ids._compute_is_valid()
        
        # Check if all valid
        valid_count = sum(1 for sig in self.signature_ids if sig.is_valid)
        invalid_count = len(self.signature_ids) - valid_count
        
        if invalid_count == 0:
            message = f'All {valid_count} signature(s) are valid. Document integrity confirmed.'
            msg_type = 'success'
            title = 'All Signatures Valid ✅'
        else:
            message = f'{invalid_count} invalid signature(s) detected! This may indicate tampering. {valid_count} signature(s) remain valid.'
            msg_type = 'danger'
            title = 'Invalid Signatures Detected ❌'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': msg_type,
                'sticky': True,
            }
        }
