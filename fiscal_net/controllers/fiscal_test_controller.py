# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class FiscalTestController(http.Controller):
    """Controler de test pentru simularea API-ului FiscalNet în dezvoltare"""
    
    @http.route('/fiscal/test/api/Receipt', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def test_fiscal_api(self, **kwargs):
        """Endpoint mock API FiscalNet pentru testare"""
        try:
            # Loghează cererea primită
            _logger.info("=== APEL MOCK API FISCALNET ===")
            _logger.info(f"Date cerere: {kwargs}")
            _logger.info(f"Tip cerere: {type(kwargs)}")
            
            # Simulează răspuns de succes
            response = {
                'ReceiptStatus': True,
                'Message': 'Mock API FiscalNet - Bonul a fost procesat cu succes',
                'ReceiptNumber': 'TEST-001',
                'Timestamp': '2025-08-30T10:35:40'
            }
            
            _logger.info(f"Răspuns mock: {response}")
            _logger.info("=== SFÂRȘIT APEL MOCK API FISCALNET ===")
            
            return response
            
        except Exception as e:
            _logger.error(f"Eroare API mock: {e}")
            return {
                'ReceiptStatus': False,
                'ErrorInfo': f'Eroare API Mock: {str(e)}',
                'ErrorCode': 'MOCK_ERROR'
            }
    
    @http.route('/fiscal/test/status', type='http', auth='public', methods=['GET'])
    def test_status(self, **kwargs):
        """Endpoint de test pentru verificarea dacă API-ul mock rulează"""
        return json.dumps({
            'status': 'running',
            'message': 'API Mock FiscalNet rulează',
            'endpoint': '/fiscal/test/api/Receipt'
        })
