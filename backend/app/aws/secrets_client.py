import json
import logging
import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)

# Global cache for the Gemini API Key
_cached_gemini_api_key = None

def get_gemini_api_key() -> str:
    """
    Retrieves the Gemini API Key.
    In 'production' environment, it retrieves the secret from AWS Secrets Manager
    with in-memory caching.
    In other environments (or if Secrets Manager fails), it falls back to the .env value.
    """
    global _cached_gemini_api_key

    # Return cached key if already fetched
    if _cached_gemini_api_key is not None:
        return _cached_gemini_api_key

    # Check if we are running in local/dev mode
    if settings.ENVIRONMENT != "production":
        logger.info("Using local Gemini API key from environment configuration.")
        _cached_gemini_api_key = settings.GEMINI_API_KEY
        return _cached_gemini_api_key

    # Production flow: fetch from Secrets Manager
    secret_name = "docuextract/gemini-key"
    region_name = settings.AWS_REGION

    # Configure session parameters
    session_params = {}
    if settings.AWS_ACCESS_KEY_ID:
        session_params["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
    if settings.AWS_SECRET_ACCESS_KEY:
        session_params["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    session = boto3.Session(**session_params)
    
    client_params = {"region_name": region_name}
    if settings.AWS_ENDPOINT_URL:
        client_params["endpoint_url"] = settings.AWS_ENDPOINT_URL

    client = session.client(service_name="secretsmanager", **client_params)

    try:
        logger.info(f"Fetching Gemini API key from Secrets Manager: {secret_name}")
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.error(f"Failed to retrieve secret '{secret_name}' from Secrets Manager: {e}")
        # Fallback to local settings even in production to prevent complete lockout if configured
        if settings.GEMINI_API_KEY:
            logger.warning("Falling back to local GEMINI_API_KEY environment variable.")
            _cached_gemini_api_key = settings.GEMINI_API_KEY
            return _cached_gemini_api_key
        raise e

    # Decrypts secret using the associated KMS key.
    if "SecretString" in get_secret_value_response:
        secret = get_secret_value_response["SecretString"]
        # The secret could be a raw string or a JSON object
        try:
            secret_json = json.loads(secret)
            if isinstance(secret_json, dict):
                # Try common keys
                for key in ["GEMINI_API_KEY", "api_key", "gemini_key"]:
                    if key in secret_json:
                        _cached_gemini_api_key = secret_json[key]
                        return _cached_gemini_api_key
                # If it's a dict but has none of the keys, just use first value or the whole string
                if secret_json:
                    _cached_gemini_api_key = next(iter(secret_json.values()))
                    return _cached_gemini_api_key
        except json.JSONDecodeError:
            # It's a raw string, not a JSON
            _cached_gemini_api_key = secret
            return _cached_gemini_api_key
    else:
        # Binary secrets are not supported for simple API keys, but handle just in case
        logger.error("Secret format not supported (binary).")
        if settings.GEMINI_API_KEY:
            _cached_gemini_api_key = settings.GEMINI_API_KEY
            return _cached_gemini_api_key
        raise ValueError("SecretString not present in Secrets Manager response.")

    _cached_gemini_api_key = secret
    return _cached_gemini_api_key

def clear_secrets_cache():
    """Utility to clear the cache, mostly useful for unit testing."""
    global _cached_gemini_api_key
    _cached_gemini_api_key = None
