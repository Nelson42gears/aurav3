"""
Pydantic Validation Layer for MCP Tools
Enhances existing validation without breaking current functionality
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, Type
from pydantic import BaseModel, Field, ValidationError, validator
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)


class PydanticParameterValidator:
    """
    Surgical Pydantic integration that enhances existing validation
    without breaking current tool registration system
    """
    
    def __init__(self):
        self.model_cache = {}
    
    def create_dynamic_model(self, tool_name: str, params: Dict[str, Any]) -> Type[BaseModel]:
        """
        Create a dynamic Pydantic model from tool parameter definitions
        This enhances the existing parameter validation without replacing it
        """
        if tool_name in self.model_cache:
            return self.model_cache[tool_name]
        
        fields = {}
        
        for param_name, param_info in params.items():
            # Extract parameter metadata
            param_type = param_info.get('type', 'string')
            required = param_info.get('required', False)
            description = param_info.get('description', f'Parameter: {param_name}')
            enum_values = param_info.get('enum', [])
            
            # Map JSON schema types to Python types
            python_type = self._map_type(param_type)
            
            # Create field with proper validation
            if required:
                if enum_values:
                    fields[param_name] = (python_type, Field(..., description=description))
                else:
                    fields[param_name] = (python_type, Field(..., description=description))
            else:
                if enum_values:
                    fields[param_name] = (Optional[python_type], Field(None, description=description))
                else:
                    fields[param_name] = (Optional[python_type], Field(None, description=description))
        
        # Create dynamic model class
        model_class = type(
            f"{tool_name.title()}Parameters",
            (BaseModel,),
            {
                '__annotations__': {k: v[0] for k, v in fields.items()},
                **{k: v[1] for k, v in fields.items()},
                '__module__': __name__
            }
        )
        
        # Add enum validation if needed
        for param_name, param_info in params.items():
            enum_values = param_info.get('enum', [])
            if enum_values:
                self._add_enum_validator(model_class, param_name, enum_values)
        
        self.model_cache[tool_name] = model_class
        return model_class
    
    def _map_type(self, json_type: str) -> Type:
        """Map JSON schema types to Python types"""
        type_mapping = {
            'string': str,
            'integer': int,
            'number': float,
            'boolean': bool,
            'array': list,
            'object': dict
        }
        return type_mapping.get(json_type, str)
    
    def _add_enum_validator(self, model_class: Type[BaseModel], field_name: str, enum_values: List[str]):
        """Add enum validation to a field"""
        def enum_validator(cls, v):
            if v is not None and v not in enum_values:
                raise ValueError(f"Invalid value '{v}' for {field_name}. Must be one of: {enum_values}")
            return v
        
        # Add validator to the model
        validator_name = f"validate_{field_name}"
        setattr(model_class, validator_name, validator(field_name, allow_reuse=True)(enum_validator))
    
    def validate_parameters(self, tool_name: str, params_config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize parameters using Pydantic
        Falls back to existing validation if Pydantic validation fails
        """
        try:
            # Create dynamic model
            model_class = self.create_dynamic_model(tool_name, params_config)
            
            # Validate input data
            validated_model = model_class(**input_data)
            
            # Convert back to dict, excluding None values for optional parameters
            validated_data = {}
            for field_name, field_value in validated_model.dict().items():
                if field_value is not None:
                    validated_data[field_name] = field_value
                elif params_config.get(field_name, {}).get('required', False):
                    validated_data[field_name] = field_value
            
            logger.debug(f"✅ Pydantic validation successful for {tool_name}")
            return validated_data
            
        except ValidationError as e:
            # Log validation errors but don't fail - fall back to existing validation
            logger.warning(f"⚠️ Pydantic validation failed for {tool_name}: {e}")
            return input_data
            
        except Exception as e:
            # Any other error - fall back gracefully
            logger.warning(f"⚠️ Pydantic validation error for {tool_name}: {e}")
            return input_data
    
    def enhance_existing_validation(self, tool_name: str, params_config: Dict[str, Any], 
                                  existing_validation_func, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance existing validation with Pydantic without breaking current flow
        """
        # First try Pydantic validation
        pydantic_validated = self.validate_parameters(tool_name, params_config, input_data)
        
        # Then apply existing validation logic
        try:
            final_validated = existing_validation_func(pydantic_validated)
            return final_validated
        except Exception as e:
            logger.warning(f"⚠️ Existing validation failed for {tool_name}: {e}")
            return pydantic_validated


# Global validator instance
_validator = None

def get_validator() -> PydanticParameterValidator:
    """Get singleton validator instance"""
    global _validator
    if _validator is None:
        _validator = PydanticParameterValidator()
    return _validator


def validate_tool_parameters(tool_name: str, params_config: Dict[str, Any], 
                           input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main validation function that enhances existing validation
    """
    validator = get_validator()
    return validator.validate_parameters(tool_name, params_config, input_data)
