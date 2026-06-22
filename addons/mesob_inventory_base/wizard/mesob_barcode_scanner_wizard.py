# -*- coding: utf-8 -*-
"""Task 9: QR/Barcode Scanner Wizard

This wizard provides a unified interface for scanning QR codes to:
- Look up items by item code
- Find requisitions by requisition number
- Locate bin cards by location
- Verify gate passes by gate pass number

The wizard parses the QR code format and redirects to the appropriate record.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobBarcodeScannerWizard(models.TransientModel):
    """QR/Barcode Scanner for quick record lookup."""
    
    _name = 'mesob.barcode.scanner.wizard'
    _description = 'QR/Barcode Scanner'
    
    scanned_code = fields.Char(
        string='Scan or Enter Code',
        required=True,
        help='Scan QR code or manually enter item code, requisition number, or location'
    )
    
    scan_mode = fields.Selection([
        ('auto', 'Auto-Detect'),
        ('item', 'Item Lookup'),
        ('requisition', 'Requisition Lookup'),
        ('bin_card', 'Bin Location Lookup'),
        ('gate_pass', 'Gate Pass Lookup'),
    ], string='Scan Mode', default='auto', required=True,
        help='Auto-detect will parse the QR code and determine the record type')
    
    result_message = fields.Html(
        string='Scan Result',
        readonly=True,
        help='Displays information about the scanned record'
    )
    
    # Result fields
    found_record_model = fields.Char(readonly=True)
    found_record_id = fields.Integer(readonly=True)
    
    def action_scan(self):
        """Process scanned code and open the corresponding record."""
        self.ensure_one()
        
        if not self.scanned_code:
            raise UserError("Please scan or enter a code.")
        
        scanned = self.scanned_code.strip()
        
        # Parse QR code format
        if scanned.startswith('MESOB-'):
            return self._process_mesob_qr_code(scanned)
        else:
            # Manual entry - try to detect by scan mode
            return self._process_manual_entry(scanned)
    
    def _process_mesob_qr_code(self, qr_code):
        """Parse MESOB QR code format and open record.
        
        Supported formats:
        - MESOB-ITEM:item_code:name
        - MESOB-REQ:req_number|DEPT:dept|DATE:date
        - MESOB-BIN:location|SUB:sub_code-name|MAJ:major_code
        - MESOB-GP:gp_number|DATE:date|TO:receiver|DEST:destination
        """
        self.ensure_one()
        
        try:
            # Determine QR code type
            if qr_code.startswith('MESOB-ITEM:'):
                return self._open_item(qr_code)
            elif qr_code.startswith('MESOB-REQ:'):
                return self._open_requisition(qr_code)
            elif qr_code.startswith('MESOB-BIN:'):
                return self._open_bin_card(qr_code)
            elif qr_code.startswith('MESOB-GP:'):
                return self._open_gate_pass(qr_code)
            else:
                raise ValidationError(
                    f"Unknown QR code format: {qr_code[:50]}...\n\n"
                    "Expected MESOB-ITEM, MESOB-REQ, MESOB-BIN, or MESOB-GP"
                )
        
        except Exception as e:
            _logger.error(f"Task 9: QR scan error: {str(e)}")
            raise UserError(
                f"Failed to process QR code.\n\n"
                f"Error: {str(e)}\n\n"
                f"Scanned code: {qr_code[:100]}"
            )
    
    def _process_manual_entry(self, code):
        """Process manually entered code based on scan mode."""
        self.ensure_one()
        
        if self.scan_mode == 'item':
            # Try to find item by item_code
            item = self.env['mesob.inventory.item'].search([
                ('item_code', '=', code)
            ], limit=1)
            
            if not item:
                raise UserError(f"Item not found: {code}")
            
            return self._open_record('mesob.inventory.item', item.id, item.display_name)
        
        elif self.scan_mode == 'requisition':
            # Try to find requisition by name
            requisition = self.env['mesob.inventory.requisition'].search([
                ('name', '=', code)
            ], limit=1)
            
            if not requisition:
                raise UserError(f"Requisition not found: {code}")
            
            return self._open_record('mesob.inventory.requisition', requisition.id, requisition.name)
        
        elif self.scan_mode == 'bin_card':
            # Try to find bin card by location
            bin_card = self.env['mesob.bin.card'].search([
                ('location', '=', code)
            ], limit=1, order='date desc')
            
            if not bin_card:
                raise UserError(f"Bin location not found: {code}")
            
            return self._open_record('mesob.bin.card', bin_card.id, bin_card.display_name)
        
        elif self.scan_mode == 'gate_pass':
            # Try to find gate pass by name
            gate_pass = self.env['mesob.gate.pass'].search([
                ('name', '=', code)
            ], limit=1)
            
            if not gate_pass:
                raise UserError(f"Gate Pass not found: {code}")
            
            return self._open_record('mesob.gate.pass', gate_pass.id, gate_pass.name)
        
        else:  # auto mode
            # Try all models in order
            for model, field, label in [
                ('mesob.inventory.item', 'item_code', 'Item'),
                ('mesob.inventory.requisition', 'name', 'Requisition'),
                ('mesob.gate.pass', 'name', 'Gate Pass'),
                ('mesob.bin.card', 'location', 'Bin Location'),
            ]:
                record = self.env[model].search([(field, '=', code)], limit=1)
                if record:
                    display = getattr(record, 'display_name', getattr(record, 'name', code))
                    return self._open_record(model, record.id, f"{label}: {display}")
            
            raise UserError(
                f"No records found for code: {code}\n\n"
                "Try selecting a specific scan mode (Item, Requisition, Bin Location, Gate Pass)"
            )
    
    def _open_item(self, qr_code):
        """Parse MESOB-ITEM QR code and open item record."""
        # Format: MESOB-ITEM:item_code:name
        parts = qr_code.split(':', 2)
        if len(parts) < 2:
            raise ValidationError("Invalid item QR code format")
        
        item_code = parts[1]
        item = self.env['mesob.inventory.item'].search([
            ('item_code', '=', item_code)
        ], limit=1)
        
        if not item:
            raise UserError(f"Item not found: {item_code}")
        
        _logger.info(f"Task 9: Scanned item QR - {item_code}")
        return self._open_record('mesob.inventory.item', item.id, item.display_name)
    
    def _open_requisition(self, qr_code):
        """Parse MESOB-REQ QR code and open requisition record."""
        # Format: MESOB-REQ:req_number|DEPT:dept|DATE:date
        parts = qr_code.split('|')
        if len(parts) < 1:
            raise ValidationError("Invalid requisition QR code format")
        
        req_part = parts[0].replace('MESOB-REQ:', '')
        requisition = self.env['mesob.inventory.requisition'].search([
            ('name', '=', req_part)
        ], limit=1)
        
        if not requisition:
            raise UserError(f"Requisition not found: {req_part}")
        
        _logger.info(f"Task 9: Scanned requisition QR - {req_part}")
        return self._open_record('mesob.inventory.requisition', requisition.id, requisition.name)
    
    def _open_bin_card(self, qr_code):
        """Parse MESOB-BIN QR code and open bin card record."""
        # Format: MESOB-BIN:location|SUB:sub_code-name|MAJ:major_code
        parts = qr_code.split('|')
        if len(parts) < 1:
            raise ValidationError("Invalid bin location QR code format")
        
        location = parts[0].replace('MESOB-BIN:', '')
        bin_card = self.env['mesob.bin.card'].search([
            ('location', '=', location)
        ], limit=1, order='date desc')
        
        if not bin_card:
            raise UserError(f"Bin location not found: {location}")
        
        _logger.info(f"Task 9: Scanned bin location QR - {location}")
        return self._open_record('mesob.bin.card', bin_card.id, bin_card.display_name)
    
    def _open_gate_pass(self, qr_code):
        """Parse MESOB-GP QR code and open gate pass record."""
        # Format: MESOB-GP:gp_number|DATE:date|TO:receiver|DEST:destination
        parts = qr_code.split('|')
        if len(parts) < 1:
            raise ValidationError("Invalid gate pass QR code format")
        
        gp_part = parts[0].replace('MESOB-GP:', '')
        gate_pass = self.env['mesob.gate.pass'].search([
            ('name', '=', gp_part)
        ], limit=1)
        
        if not gate_pass:
            raise UserError(f"Gate Pass not found: {gp_part}")
        
        _logger.info(f"Task 9: Scanned gate pass QR - {gp_part}")
        return self._open_record('mesob.gate.pass', gate_pass.id, gate_pass.name)
    
    def _open_record(self, model, record_id, display_name):
        """Open the found record in form view."""
        self.ensure_one()
        
        _logger.info(f"Task 9: Opening {model} record ID {record_id}")
        
        return {
            'name': f'Scanned: {display_name}',
            'type': 'ir.actions.act_window',
            'res_model': model,
            'res_id': record_id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_scan_another(self):
        """Clear the form and scan another code."""
        self.scanned_code = False
        self.result_message = False
        self.found_record_model = False
        self.found_record_id = False
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.barcode.scanner.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
