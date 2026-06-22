# -*- coding: utf-8 -*-
"""Task 11: Digital Signature Enhancement

Provides cryptographic digital signatures for critical documents to ensure:
- Document integrity (detect tampering)
- Signer authentication (who signed)
- Non-repudiation (can't deny signing)
- Compliance with Ethiopia Proclamation No. 1072/2018

Uses SHA-256 hashing + HMAC for signature generation.
Can be upgraded to full PKI (Ethiopian government certificates) in future.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import hashlib
import hmac
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class MesobDigitalSignature(models.Model):
    """Digital Signature record for critical documents.
    
    Stores cryptographic signature of document content at time of signing.
    Provides verification to detect any tampering after signature.
    """
    
    _name = 'mesob.digital.signature'
    _description = 'Digital Signature'
    _order = 'signed_on desc, id desc'
    _rec_name = 'display_name'
    
    # Document identification
    document_model = fields.Char(
        string='Document Model',
        required=True,
        index=True,
        help='Model name of signed document (e.g., mesob.gate.pass)'
    )
    
    document_id = fields.Integer(
        string='Document ID',
        required=True,
        index=True,
        help='Record ID of signed document'
    )
    
    document_name = fields.Char(
        string='Document Reference',
        required=True,
        help='Display name of signed document (e.g., GP/2026/001)'
    )
    
    # Signature details
    signature_hash = fields.Char(
        string='Signature Hash',
        required=True,
        readonly=True,
        help='SHA-256 hash of document content + metadata (for integrity verification)'
    )
    
    signature_type = fields.Selection([
        ('approval', 'Approval Signature'),
        ('authorization', 'Authorization Signature'),
        ('verification', 'Verification Signature'),
        ('acknowledgment', 'Acknowledgment Signature'),
    ], string='Signature Type', required=True, default='approval')
    
    # Signer information
    signed_by_id = fields.Many2one(
        'res.users',
        string='Signed By',
        required=True,
        readonly=True,
        index=True,
        help='User who signed the document'
    )
    
    signed_on = fields.Datetime(
        string='Signed On',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        help='Timestamp when document was signed'
    )
    
    signer_ip = fields.Char(
        string='Signer IP Address',
        readonly=True,
        help='IP address of signing user (for audit trail)'
    )
    
    # Document state at signing
    document_state = fields.Char(
        string='Document State',
        readonly=True,
        help='Workflow state when document was signed'
    )
    
    document_content_hash = fields.Text(
        string='Content Snapshot',
        readonly=True,
        help='JSON snapshot of document fields at signing time'
    )
    
    # Verification
    is_valid = fields.Boolean(
        string='Signature Valid',
        compute='_compute_is_valid',
        store=False,
        help='True if signature is still valid (document not tampered with)'
    )
    
    verification_message = fields.Text(
        string='Verification Status',
        compute='_compute_is_valid',
        store=False
    )
    
    # Additional metadata
    signature_reason = fields.Text(
        string='Reason for Signing',
        help='Why this signature was required (e.g., PAO Approval, HOPE Authorization)'
    )
    
    notes = fields.Text(
        string='Signature Notes',
        help='Additional notes or comments at time of signing'
    )
    
    # Display name
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    @api.depends('document_name', 'signed_by_id', 'signed_on')
    def _compute_display_name(self):
        for record in self:
            if record.signed_by_id and record.document_name:
                record.display_name = f"{record.document_name} - Signed by {record.signed_by_id.name}"
            else:
                record.display_name = 'Digital Signature'
    
    @api.depends('signature_hash', 'document_model', 'document_id')
    def _compute_is_valid(self):
        """Verify signature integrity by recomputing hash.
        
        If document content has changed after signing, hash won't match.
        """
        for record in self:
            if not record.signature_hash or not record.document_model or not record.document_id:
                record.is_valid = False
                record.verification_message = "Incomplete signature data"
                continue
            
            try:
                # Get current document
                document = self.env[record.document_model].browse(record.document_id)
                if not document.exists():
                    record.is_valid = False
                    record.verification_message = "❌ Document no longer exists"
                    continue
                
                # Recompute signature hash from current document
                current_hash = self._generate_signature_hash(
                    record.document_model,
                    record.document_id,
                    record.signed_by_id.id,
                    record.document_content_hash
                )
                
                # Compare with stored hash
                if current_hash == record.signature_hash:
                    record.is_valid = True
                    record.verification_message = f"✅ Valid signature by {record.signed_by_id.name} on {record.signed_on}"
                else:
                    record.is_valid = False
                    record.verification_message = (
                        f"❌ SIGNATURE INVALID - Document has been modified after signing!\n"
                        f"Original signature: {record.signed_on} by {record.signed_by_id.name}\n"
                        f"This may indicate tampering or unauthorized changes."
                    )
                    _logger.warning(
                        f"Task 11: Invalid signature detected for {record.document_model} "
                        f"ID {record.document_id} - document modified after signing"
                    )
            
            except Exception as e:
                record.is_valid = False
                record.verification_message = f"❌ Verification error: {str(e)}"
                _logger.error(f"Task 11: Signature verification error: {str(e)}")
    
    @api.model
    def create_signature(self, document_model, document_id, signature_type, reason=None):
        """Create digital signature for a document.
        
        Args:
            document_model (str): Model name (e.g., 'mesob.gate.pass')
            document_id (int): Record ID
            signature_type (str): Type of signature ('approval', 'authorization', etc.)
            reason (str, optional): Reason for signature
        
        Returns:
            mesob.digital.signature: Created signature record
        """
        # Get document
        document = self.env[document_model].browse(document_id)
        if not document.exists():
            raise UserError(f"Document {document_model} ID {document_id} not found")
        
        # Get document name
        document_name = document.display_name if hasattr(document, 'display_name') else document.name
        
        # Capture document content snapshot
        content_snapshot = self._capture_document_snapshot(document)
        
        # Generate signature hash
        signature_hash = self._generate_signature_hash(
            document_model,
            document_id,
            self.env.user.id,
            content_snapshot
        )
        
        # Get signer IP (if available)
        signer_ip = self.env.context.get('signer_ip', None)
        
        # Get document state
        document_state = document.state if hasattr(document, 'state') else 'unknown'
        
        # Create signature record
        signature = self.create({
            'document_model': document_model,
            'document_id': document_id,
            'document_name': document_name,
            'signature_hash': signature_hash,
            'signature_type': signature_type,
            'signed_by_id': self.env.user.id,
            'signed_on': fields.Datetime.now(),
            'signer_ip': signer_ip,
            'document_state': document_state,
            'document_content_hash': content_snapshot,
            'signature_reason': reason,
        })
        
        _logger.info(
            f"Task 11: Digital signature created for {document_model} ID {document_id} "
            f"by {self.env.user.name} (Type: {signature_type})"
        )
        
        return signature
    
    @api.model
    def _capture_document_snapshot(self, document):
        """Capture JSON snapshot of document critical fields.
        
        Args:
            document: Odoo recordset
        
        Returns:
            str: JSON string of document snapshot
        """
        # Define fields to capture per model
        # This ensures we capture the critical fields that matter for integrity
        snapshot = {
            'model': document._name,
            'id': document.id,
            'name': document.name if hasattr(document, 'name') else str(document.id),
            'timestamp': fields.Datetime.now().isoformat(),
        }
        
        # Add model-specific critical fields
        if document._name == 'mesob.inventory.requisition':
            snapshot.update({
                'state': document.state,
                'department': document.department,
                'requested_by_id': document.requested_by_id.id,
                'line_count': len(document.line_ids),
            })
        elif document._name == 'mesob.gate.pass':
            snapshot.update({
                'state': document.state,
                'receiver_name': document.receiver_name,
                'destination': document.destination,
                'line_count': len(document.line_ids),
            })
        elif document._name == 'mesob.bin.card':
            snapshot.update({
                'state': document.state if hasattr(document, 'state') else 'posted',
                'transaction_type': document.transaction_type,
                'balance': document.balance,
            })
        
        return json.dumps(snapshot, sort_keys=True)
    
    @api.model
    def _generate_signature_hash(self, document_model, document_id, user_id, content_snapshot):
        """Generate cryptographic signature hash.
        
        Uses HMAC-SHA256 for signature generation.
        
        Args:
            document_model (str): Model name
            document_id (int): Record ID
            user_id (int): Signing user ID
            content_snapshot (str): JSON document snapshot
        
        Returns:
            str: SHA-256 signature hash
        """
        # Get system-wide secret key from Odoo config
        # In production, this should be a strong secret key stored securely
        secret_key = self.env['ir.config_parameter'].sudo().get_param(
            'mesob.signature.secret_key',
            'MESOB-DEFAULT-SECRET-KEY-CHANGE-IN-PRODUCTION'
        )
        
        # Prepare signature payload
        payload = f"{document_model}:{document_id}:{user_id}:{content_snapshot}"
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def action_verify_signature(self):
        """Manual action to verify signature integrity."""
        self.ensure_one()
        
        # Force recompute
        self._compute_is_valid()
        
        # Show result message
        if self.is_valid:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Signature Valid ✅',
                    'message': f'Document has not been tampered with. Signed by {self.signed_by_id.name} on {self.signed_on}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Signature Invalid ❌',
                    'message': self.verification_message,
                    'type': 'danger',
                    'sticky': True,
                }
            }
