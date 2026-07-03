# -*- coding: utf-8 -*-
import json
import logging
import requests
from urllib.parse import urlparse, parse_qs
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class FiscalProxyController(http.Controller):
    """Proxy controller for FiscalNet API requests to bypass mixed content restrictions"""
    
    @http.route('/fiscal/proxy-receipt', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def proxy_receipt(self, **kwargs):
        """
        Proxy endpoint for FiscalNet API requests
        Usage: POST /fiscal/proxy-receipt?target=<encoded_fiscalnet_url>
        """
        try:
            # Get the target URL from query parameters
            target_url = request.httprequest.args.get('target')
            
            if not target_url:
                _logger.error("❌ No target URL provided in proxy request")
                return {
                    'success': False,
                    'message': 'Target URL is required',
                    'error_code': 'MISSING_TARGET'
                }
            
            # Decode the target URL
            try:
                from urllib.parse import unquote
                target_url = unquote(target_url)
            except Exception as e:
                _logger.error(f"❌ Failed to decode target URL: {e}")
                return {
                    'success': False,
                    'message': 'Invalid target URL encoding',
                    'error_code': 'INVALID_TARGET'
                }
            
            _logger.info(f"🔄 Proxying request to: {target_url}")
            
            # Get the request body (fiscal commands)
            request_body = request.jsonrequest
            
            if not request_body:
                _logger.error("❌ No request body provided")
                return {
                    'success': False,
                    'message': 'Request body is required',
                    'error_code': 'MISSING_BODY'
                }
            
            _logger.info(f"📤 Request body: {request_body}")
            
            # Validate target URL
            try:
                parsed_url = urlparse(target_url)
                if not parsed_url.scheme or not parsed_url.netloc:
                    raise ValueError("Invalid URL format")
            except Exception as e:
                _logger.error(f"❌ Invalid target URL format: {e}")
                return {
                    'success': False,
                    'message': 'Invalid target URL format',
                    'error_code': 'INVALID_URL'
                }
            
            # Make the request to the target FiscalNet API
            try:
                _logger.info(f"🚀 Making HTTP POST request to FiscalNet API...")
                _logger.info(f"   Target: {target_url}")
                _logger.info(f"   Body: {request_body}")
                
                # Set timeout to prevent hanging requests
                response = requests.post(
                    target_url,
                    json=request_body,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'User-Agent': 'Odoo-FiscalProxy/1.0'
                    },
                    timeout=30  # 30 second timeout
                )
                
                _logger.info(f"📥 Response received:")
                _logger.info(f"   Status: {response.status_code}")
                _logger.info(f"   Headers: {dict(response.headers)}")
                
                # Check if request was successful
                if response.status_code >= 200 and response.status_code < 300:
                    try:
                        response_data = response.json()
                        _logger.info(f"✅ Successfully proxied request to FiscalNet API")
                        _logger.info(f"   Response: {response_data}")
                        
                        # Return the FiscalNet response with success indicator
                        return {
                            'success': True,
                            'message': 'Request proxied successfully',
                            'fiscal_response': response_data,
                            'status_code': response.status_code
                        }
                        
                    except json.JSONDecodeError:
                        # Response is not JSON, return as text
                        _logger.info(f"📄 Non-JSON response received: {response.text}")
                        return {
                            'success': True,
                            'message': 'Request proxied successfully (non-JSON response)',
                            'fiscal_response': response.text,
                            'status_code': response.status_code
                        }
                        
                else:
                    # HTTP error
                    error_message = f"FiscalNet API returned HTTP {response.status_code}: {response.reason}"
                    _logger.error(f"❌ {error_message}")
                    
                    try:
                        error_data = response.json()
                        return {
                            'success': False,
                            'message': error_message,
                            'error_code': f'HTTP_{response.status_code}',
                            'fiscal_error': error_data
                        }
                    except:
                        return {
                            'success': False,
                            'message': error_message,
                            'error_code': f'HTTP_{response.status_code}',
                            'fiscal_error': response.text
                        }
                        
            except requests.exceptions.Timeout:
                error_message = "FiscalNet API request timed out after 30 seconds"
                _logger.error(f"❌ {error_message}")
                return {
                    'success': False,
                    'message': error_message,
                    'error_code': 'TIMEOUT'
                }
                
            except requests.exceptions.ConnectionError as e:
                error_message = f"Cannot connect to FiscalNet API: {str(e)}"
                _logger.error(f"❌ {error_message}")
                return {
                    'success': False,
                    'message': error_message,
                    'error_code': 'CONNECTION_ERROR'
                }
                
            except requests.exceptions.RequestException as e:
                error_message = f"Request error: {str(e)}"
                _logger.error(f"❌ {error_message}")
                return {
                    'success': False,
                    'message': error_message,
                    'error_code': 'REQUEST_ERROR'
                }
                
        except Exception as e:
            _logger.error(f"❌ Proxy controller error: {e}")
            return {
                'success': False,
                'message': f'Proxy error: {str(e)}',
                'error_code': 'PROXY_ERROR'
            }
    
    @http.route('/fiscal/proxy-status', type='http', auth='user', methods=['GET'])
    def proxy_status(self, **kwargs):
        """Check proxy controller status"""
        return json.dumps({
            'status': 'running',
            'message': 'Fiscal proxy controller is active',
            'endpoint': '/fiscal/proxy-receipt',
            'usage': 'POST /fiscal/proxy-receipt?target=<encoded_fiscalnet_url>'
        })
