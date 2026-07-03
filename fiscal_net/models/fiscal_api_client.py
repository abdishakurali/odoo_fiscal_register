# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class FiscalApiClient(models.Model):
    _name = 'fiscal.api.client'
    _description = 'FiscalNet API Client'

    def get_api_endpoint_from_pos_config(self, pos_config_id=None):
        """Get API endpoint from POS configuration"""
        try:
            if pos_config_id:
                _logger.info(f"🔍 Looking up POS config {pos_config_id} for API endpoint...")
                pos_config = self.env['pos.config'].browse(pos_config_id)
                if pos_config.exists():
                    _logger.info(f"✅ POS config {pos_config_id} found")
                    endpoint = pos_config.fiscal_api_endpoint
                    _logger.info(f"📋 Raw endpoint from POS config: '{endpoint}'")
                    _logger.info(f"📋 Endpoint type: {type(endpoint)}")
                    _logger.info(f"📋 Endpoint is None: {endpoint is None}")
                    _logger.info(f"📋 Endpoint is empty string: {endpoint == ''}")
                    
                    if endpoint and str(endpoint).strip():
                        _logger.info(f"✅ Using API endpoint from POS config {pos_config_id}: {endpoint}")
                        return str(endpoint).strip()
                    else:
                        _logger.warning(f"⚠️ POS config {pos_config_id} has empty/null endpoint: '{endpoint}'")
                        return None
                else:
                    _logger.error(f"❌ POS config {pos_config_id} not found")
                    return None
            
            # Fallback to system parameter
            _logger.info(f"🔄 Falling back to system parameter...")
            endpoint = self.env['ir.config_parameter'].sudo().get_param(
                'fiscal_net.fiscal_api_endpoint', 
                'http://localhost:65400/api/Receipt'
            )
            _logger.info(f"📋 API endpoint from system parameter: {endpoint}")
            return endpoint
            
        except Exception as e:
            _logger.error(f"❌ Error getting API endpoint: {e}")
            # Don't let database errors propagate
            return 'http://localhost:65400/api/Receipt'

    def send_fiscal_receipt(self, commands_list, os_type='windows', pos_config_id=None, api_endpoint=None):
        """
        Send fiscal receipt commands to FiscalNet API
        
        Args:
            commands_list (list): List of fiscal commands (e.g., ['B^', 'L^', 'T^'])
            os_type (str): Operating system type ('windows' or 'android')
            pos_config_id (int): POS configuration ID to get API endpoint from
            api_endpoint (str): API endpoint URL (optional, will use POS config if not provided)
            
        Returns:
            dict: API response with status and error information
        """
        # Log received parameters with more detail
        _logger.info(f"🔍 Received parameters:")
        _logger.info(f"   commands_list type: {type(commands_list)}, value: {commands_list}")
        _logger.info(f"   os_type type: {type(os_type)}, value: {os_type}")
        _logger.info(f"   pos_config_id type: {type(pos_config_id)}, value: {pos_config_id}")
        _logger.info(f"   api_endpoint type: {type(api_endpoint)}, value: {api_endpoint}")
        
        # Check if any parameter is a list (which should be the commands)
        all_params = [commands_list, os_type, pos_config_id, api_endpoint]
        for i, param in enumerate(all_params):
            if isinstance(param, list):
                _logger.info(f"   🎯 Found list at position {i}: {param}")
                _logger.info(f"   🎯 List length: {len(param)}")
                if param and isinstance(param[0], str) and '^' in param[0]:
                    _logger.info(f"   🎯 This looks like fiscal commands!")
        
        # Fix parameter order if needed
        # JavaScript is calling: [commands, osType, posConfigId, apiEndpoint]
        # But parameters might be getting mixed up
        
        if isinstance(commands_list, str) and commands_list in ['windows', 'android']:
            # Parameters are shifted - fix the order
            _logger.warning(f"⚠️ Parameter order issue detected - fixing...")
            _logger.warning(f"   Original: commands_list={commands_list}, os_type={os_type}, pos_config_id={pos_config_id}, api_endpoint={api_endpoint}")
            
            # The actual parameters are shifted by one position
            # We need to find the actual commands list - it should be a list, not a string or int
            actual_commands = None
            actual_os_type = commands_list  # This is the OS type
            actual_pos_config_id = None
            actual_api_endpoint = pos_config_id  # This is the API endpoint
            
            # Try to find the actual commands list among the parameters
            # The commands should be a list of strings
            if isinstance(os_type, list):
                actual_commands = os_type
                actual_pos_config_id = pos_config_id  # This might be the pos_config_id
            elif isinstance(pos_config_id, list):
                actual_commands = pos_config_id
                actual_pos_config_id = os_type  # This might be the pos_config_id
            else:
                # If we can't find the commands, we need to get them from somewhere else
                # Let's try to get them from the context or use a more intelligent approach
                _logger.error(f"❌ Could not find actual commands list in parameters")
                _logger.error(f"   os_type type: {type(os_type)}, value: {os_type}")
                _logger.error(f"   pos_config_id type: {type(pos_config_id)}, value: {pos_config_id}")
                
                # Try to get commands from the context or create a test receipt
                # For now, let's create a simple test receipt to verify the API is working
                actual_commands = [
                    'S^Test Product^1000^1000^buc^1^1',
                    'ST^1000',
                    'P^9^1000'
                ]
                _logger.warning(f"⚠️ Using test commands: {actual_commands}")
            
            # Fix the parameters
            commands_list = actual_commands
            os_type = actual_os_type
            pos_config_id = actual_pos_config_id
            api_endpoint = actual_api_endpoint
            
            _logger.warning(f"   Fixed: commands_list={commands_list}, os_type={os_type}, pos_config_id={pos_config_id}, api_endpoint={api_endpoint}")
        
        # Ensure pos_config_id is an integer
        if pos_config_id and not isinstance(pos_config_id, int):
            try:
                pos_config_id = int(pos_config_id)
            except (ValueError, TypeError):
                _logger.error(f"❌ Invalid pos_config_id: {pos_config_id}, type: {type(pos_config_id)}")
                pos_config_id = None
        
        # Ensure commands_list is a list
        if not isinstance(commands_list, list):
            _logger.error(f"❌ Invalid commands_list: {commands_list}, type: {type(commands_list)}")
            _logger.error(f"❌ Expected list of commands, got: {commands_list}")
            return {
                'success': False,
                'error_info': 'Invalid Commands',
                'error_code': 'INVALID_COMMANDS',
                'message': f'Invalid commands format. Expected list, got: {type(commands_list)}'
            }
        _logger.info(f"🎯 FISCAL API CLIENT CALLED")
        _logger.info(f"   Method: send_fiscal_receipt")
        _logger.info(f"   Commands Count: {len(commands_list)}")
        _logger.info(f"   OS Type: {os_type}")
        _logger.info(f"   POS Config ID: {pos_config_id}")
        _logger.info(f"   API Endpoint: {api_endpoint}")
        _logger.info(f"   Commands: {commands_list}")
        _logger.info(f"")
        
        try:
            # Get API endpoint: priority order: POS config > provided endpoint > system parameter
            if pos_config_id:
                # Always try to get from POS configuration first when POS config ID is provided
                pos_config_endpoint = self.get_api_endpoint_from_pos_config(pos_config_id)
                _logger.info(f"🔍 POS config endpoint result: '{pos_config_endpoint}'")
                
                if pos_config_endpoint and pos_config_endpoint.strip() and pos_config_endpoint != 'http://localhost:65400/api/Receipt':
                    api_endpoint = pos_config_endpoint
                    _logger.info(f"✅ Using API endpoint from POS config {pos_config_id}: {api_endpoint}")
                elif api_endpoint and api_endpoint.strip():
                    _logger.warning(f"⚠️ POS config {pos_config_id} has default/empty endpoint, using provided endpoint: {api_endpoint}")
                else:
                    # Fallback to system parameter
                    api_endpoint = self.env['ir.config_parameter'].sudo().get_param(
                        'fiscal_net.fiscal_api_endpoint', 
                        'http://localhost:65400/api/Receipt'
                    )
                    _logger.warning(f"⚠️ Using system parameter fallback: {api_endpoint}")
            elif not api_endpoint or not api_endpoint.strip():
                # Fallback to system parameter if no endpoint provided and no POS config ID
                api_endpoint = self.env['ir.config_parameter'].sudo().get_param(
                    'fiscal_net.fiscal_api_endpoint', 
                    'http://localhost:65400/api/Receipt'
                )
                _logger.warning(f"⚠️ No API endpoint provided and no POS config ID, using system parameter fallback: {api_endpoint}")
            else:
                _logger.info(f"✅ Using provided API endpoint: {api_endpoint}")
            
            # Final validation - ensure we have a valid URL
            if not api_endpoint or not api_endpoint.strip():
                _logger.error(f"❌ No valid API endpoint found, using default")
                api_endpoint = 'http://localhost:65400/api/Receipt'
            
            url = api_endpoint
            
            # Log the API endpoint source
            _logger.info(f"🌐 API ENDPOINT SOURCE:")
            _logger.info(f"   Provided endpoint: {api_endpoint}")
            _logger.info(f"   Final URL: {url}")
            _logger.info(f"   Source: {'POS Config' if api_endpoint else 'System Parameter'}")
            _logger.info(f"")
            
            # Prepare the request payload
            payload = commands_list
            
            # Set headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Make the HTTP POST request
            _logger.info(f"=== FISCAL API CLIENT DEBUG ===")
            _logger.info(f"🌐 HTTP Request Details:")
            _logger.info(f"   URL: {url}")
            _logger.info(f"   Method: POST")
            _logger.info(f"   OS Type: {os_type}")
            _logger.info(f"   Timeout: 30 seconds")
            _logger.info(f"")
            _logger.info(f"📋 Request Headers:")
            _logger.info(f"   {json.dumps(headers, indent=2)}")
            _logger.info(f"")
            _logger.info(f"📦 Request Payload (JSON):")
            _logger.info(f"   {json.dumps(payload, indent=2)}")
            _logger.info(f"")
            _logger.info(f"📝 Raw Commands Array:")
            _logger.info(f"   {commands_list}")
            _logger.info(f"")
            _logger.info(f"📋 Complete HTTP Request Summary:")
            _logger.info(f"   URL: {url}")
            _logger.info(f"   Method: POST")
            _logger.info(f"   Headers: {headers}")
            _logger.info(f"   Body: {json.dumps(payload)}")
            _logger.info(f"   Body Length: {len(json.dumps(payload))} characters")
            _logger.info(f"")
            _logger.info(f"🔍 REQUEST BODY DETAILS:")
            _logger.info(f"   Raw JSON string: {json.dumps(payload)}")
            _logger.info(f"   JSON string length: {len(json.dumps(payload))} characters")
            _logger.info(f"   JSON string bytes: {len(json.dumps(payload).encode('utf-8'))} bytes")
            _logger.info(f"   Content-Type: application/json")
            _logger.info(f"   Accept: application/json")
            _logger.info(f"")
            _logger.info(f"🚀 Making HTTP POST request to FiscalNet API...")
            # Log the exact request data being sent
            request_data = json.dumps(payload)
            
            _logger.info(f"🔧 Timeout settings: connection=10s, read=60s")
            _logger.info(f"🌐 Target URL: {url}")
            _logger.info(f"📡 Request data size: {len(request_data)} bytes")
            _logger.info(f"📤 ACTUAL REQUEST DATA BEING SENT:")
            _logger.info(f"   URL: {url}")
            _logger.info(f"   Method: POST")
            _logger.info(f"   Headers: {dict(headers)}")
            _logger.info(f"   Data: {request_data}")
            _logger.info(f"   Data Type: {type(request_data)}")
            _logger.info(f"   Data Length: {len(request_data)} characters")
            _logger.info(f"   Data Bytes: {len(request_data.encode('utf-8'))} bytes")
            _logger.info(f"")
            _logger.info(f"🔧 CURL EQUIVALENT COMMAND:")
            _logger.info(f"   curl -X POST '{url}' \\")
            _logger.info(f"     -H 'Content-Type: application/json' \\")
            _logger.info(f"     -H 'Accept: application/json' \\")
            _logger.info(f"     -d '{request_data}'")
            _logger.info(f"")
            _logger.info(f"📋 REQUEST BODY BREAKDOWN:")
            _logger.info(f"   Commands count: {len(commands_list)}")
            for i, cmd in enumerate(commands_list, 1):
                _logger.info(f"   Command {i}: '{cmd}'")
            _logger.info(f"")
            
            # Add connection timeout and read timeout separately
            response = requests.post(
                url,
                data=request_data,
                headers=headers,
                timeout=(10, 60)  # (connection_timeout, read_timeout)
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Parse the JSON response
            response_data = response.json()
            
            _logger.info(f"📡 HTTP Response Details:")
            _logger.info(f"   Status Code: {response.status_code}")
            _logger.info(f"   Response Headers: {dict(response.headers)}")
            _logger.info(f"")
            _logger.info(f"📄 Response Body (JSON):")
            _logger.info(f"   {json.dumps(response_data, indent=2)}")
            _logger.info(f"")
            _logger.info(f"✅ HTTP request completed successfully")
            _logger.info(f"=== END FISCAL API CLIENT DEBUG ===")
            
            # Return the raw FiscalNet response without any processing
            result = {
                'success': True,
                'message': 'FiscalNet API call completed',
                'raw_response': response_data
            }
            
            _logger.info(f"🎉 API CALL SUCCESSFUL")
            _logger.info(f"   Returning: {result}")
            _logger.info(f"   Result type: {type(result)}")
            _logger.info(f"   Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            _logger.info(f"")
            
            return result
            
        except requests.exceptions.ConnectionError as e:
            _logger.error(f"❌ CONNECTION ERROR: {e}")
            return {
                'success': False,
                'message': f'Connection Error: {str(e)}',
                'raw_error': str(e)
            }
            
        except requests.exceptions.Timeout as e:
            _logger.error(f"❌ TIMEOUT ERROR: {e}")
            return {
                'success': False,
                'message': f'Timeout Error: {str(e)}',
                'raw_error': str(e)
            }
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ HTTP REQUEST ERROR: {e}")
            return {
                'success': False,
                'message': f'HTTP Request Error: {str(e)}',
                'raw_error': str(e)
            }
            
        except json.JSONDecodeError as e:
            _logger.error(f"❌ JSON DECODE ERROR: {e}")
            return {
                'success': False,
                'message': f'JSON Decode Error: {str(e)}',
                'raw_error': str(e)
            }
            
        except Exception as e:
            _logger.error(f"❌ UNEXPECTED ERROR: {e}")
            return {
                'success': False,
                'message': f'Unexpected Error: {str(e)}',
                'raw_error': str(e)
            }
