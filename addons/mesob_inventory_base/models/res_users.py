# -*- coding: utf-8 -*-
"""User model extension for email and password validation."""

import re
import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extend res.users to add email and password validation."""
    
    _inherit = 'res.users'
    
    # Common weak passwords to reject
    WEAK_PASSWORDS = [
        'password', 'password123', 'admin', 'admin123', '12345678',
        'qwerty', 'letmein', 'welcome', 'monkey', 'dragon',
        '123456789', 'password1', 'abc123', 'iloveyou', 'adobe123',
        'admin@123', 'root', 'toor', 'pass', 'test123'
    ]
    
    @api.constrains('login')
    def _check_email_format(self):
        """Validate email format for login field.
        
        Requirements:
        - Must be a valid email format (user@domain.com)
        - Must have @ symbol
        - Must have domain with at least one dot
        - No spaces or invalid characters
        """
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        for user in self:
            if user.login:
                # Skip validation for admin and system users (they might use non-email logins)
                if user.id in (1, 2) or user.login in ('admin', '__system__'):
                    continue
                
                # Validate email format
                if not re.match(email_regex, user.login):
                    raise ValidationError(
                        f"Invalid email format for login '{user.login}'.\n\n"
                        f"Requirements:\n"
                        f"✓ Must be a valid email address (e.g., user@example.com)\n"
                        f"✓ Must contain @ symbol\n"
                        f"✓ Must have a valid domain (e.g., example.com)\n"
                        f"✓ No spaces or special characters except . _ % + -\n\n"
                        f"Example: john.doe@company.et"
                    )
    
    @api.model
    def create(self, vals):
        """Validate password strength on user creation."""
        if 'password' in vals and vals.get('password'):
            self._validate_password_strength(vals['password'], vals.get('login', 'user'))
        return super(ResUsers, self).create(vals)
    
    def write(self, vals):
        """Validate password strength on password change."""
        if 'password' in vals and vals.get('password'):
            login = vals.get('login') or self.login
            self._validate_password_strength(vals['password'], login)
        return super(ResUsers, self).write(vals)
    
    def _validate_password_strength(self, password, login=None):
        """Validate password meets security requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one uppercase letter (A-Z)
        - At least one lowercase letter (a-z)
        - At least one digit (0-9)
        - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
        - Not in common weak passwords list
        - Not same as or similar to email/login
        
        Args:
            password (str): The password to validate
            login (str): The user's login/email for comparison
            
        Raises:
            ValidationError: If password doesn't meet requirements
        """
        if not password:
            return
        
        errors = []
        
        # Check minimum length
        if len(password) < 8:
            errors.append("✗ Must be at least 8 characters long")
        
        # Check for uppercase letter
        if not re.search(r'[A-Z]', password):
            errors.append("✗ Must contain at least one uppercase letter (A-Z)")
        
        # Check for lowercase letter
        if not re.search(r'[a-z]', password):
            errors.append("✗ Must contain at least one lowercase letter (a-z)")
        
        # Check for digit
        if not re.search(r'\d', password):
            errors.append("✗ Must contain at least one digit (0-9)")
        
        # Check for special character
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            errors.append("✗ Must contain at least one special character (!@#$%^&* etc.)")
        
        # Check against weak passwords
        password_lower = password.lower()
        if password_lower in self.WEAK_PASSWORDS:
            errors.append("✗ This password is too common and easily guessable")
        
        # Check if password contains username/email
        if login:
            username = login.split('@')[0].lower()
            if username in password_lower and len(username) > 3:
                errors.append("✗ Password should not contain your username or email")
        
        # If there are any errors, raise validation error
        if errors:
            error_msg = "Password does not meet security requirements:\n\n"
            error_msg += "\n".join(errors)
            error_msg += "\n\n✓ Example of strong password: SecurePass@123"
            
            _logger.warning(f"Weak password attempt for user: {login}")
            raise ValidationError(error_msg)
        
        _logger.info(f"Password validation passed for user: {login}")
    
    @api.model
    def change_password(self, old_passwd, new_passwd):
        """Override change_password to validate new password."""
        # Validate new password before changing
        self._validate_password_strength(new_passwd, self.env.user.login)
        return super(ResUsers, self).change_password(old_passwd, new_passwd)
